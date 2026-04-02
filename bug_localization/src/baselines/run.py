"""
Bug-localisation benchmark runner.

Supports two modes (controlled by ``parallel`` config flag):
"""

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict

import hydra
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf

from src import PROJECT_DIR, logger
from src.baselines.backbone.base_backbone import BaseBackbone
from src.baselines.data_sources.base_data_source import BaseDataSource
from src.baselines.data_sources.hf_data_source import HFDataSource
from src.baselines.data_sources.prompt_cache import PromptCache


class LocalizationMetricsCollector:
    def __init__(self):
        self.total_time_seconds = 0
        self.total_token_usage = 0
        self.total_cost_usd = 0
        self.instance_count = 0
        self.valid_format_count = 0
        self.total_files_predicted = 0
        self.empty_predictions = 0

    def add_instance_metrics(self, duration, tokens, cost, has_valid_json, num_files_predicted):
        self.total_time_seconds += duration
        self.total_token_usage += tokens
        self.total_cost_usd += cost
        self.instance_count += 1

        if has_valid_json:
            self.valid_format_count += 1
            self.total_files_predicted += num_files_predicted
            if num_files_predicted == 0:
                self.empty_predictions += 1

    def log_summary(self, log):
        if self.instance_count == 0:
            return

        avg_time = self.total_time_seconds / self.instance_count
        compliance_rate = (self.valid_format_count / self.instance_count) * 100
        avg_files = self.total_files_predicted / self.valid_format_count if self.valid_format_count > 0 else 0

        log.info("=" * 45)
        log.info("BUG LOCALIZATION (PASSIVE) METRICS SUMMARY")
        log.info("-" * 45)
        log.info(f"Instances Evaluated:       {self.instance_count}")
        log.info(f"Total Time (H:M:S):        {time.strftime('%H:%M:%S', time.gmtime(self.total_time_seconds))}")
        log.info(f"Avg Time/Instance:         {avg_time:.2f}s")
        log.info(f"Total Token Usage:         {self.total_token_usage}")
        log.info(f"Estimated Cost (USD):      ${self.total_cost_usd:.4f}")
        log.info("-" * 45)
        log.info(f"Valid JSON Outputs:        {self.valid_format_count} ({compliance_rate:.1f}%)")
        log.info(f"Avg Files Guessed:         {avg_files:.2f} per valid run")
        log.info(f"Empty Predictions:         {self.empty_predictions}")
        log.info("=" * 45)


def calculate_cost(backbone_name: str, tokens: int) -> float:
    """Estimates cost based on the active model."""
    name_lower = backbone_name.lower()
    if "gpt-3.5" in name_lower:
        rate_per_million = 0.50
    elif "gemini" in name_lower:
        rate_per_million = 0.075
    elif "claude" in name_lower:
        rate_per_million = 0.25
    else:
        rate_per_million = 0.0

    return (tokens / 1_000_000) * rate_per_million


def _load_existing_ids(results_path: Path) -> set:
    """Load text_ids that have already been written to results."""
    existing = set()
    if results_path.exists():
        with open(results_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line.strip())
                    existing.add(data.get('text_id'))
                except json.JSONDecodeError:
                    pass
    return existing


def _process_single(
    backbone: BaseBackbone,
    messages: list,
    text_id: str,
) -> Dict[str, Any]:
    """Send pre-composed messages to the LLM (runs inside a worker thread)."""
    start = time.time()
    result = backbone.call_llm(messages)
    elapsed = time.time() - start
    result['time_s'] = elapsed
    result['text_id'] = text_id
    return result


def _run_sequential(cfg: DictConfig) -> None:
    backbone: BaseBackbone = hydra.utils.instantiate(cfg.backbone)
    data_src: BaseDataSource = hydra.utils.instantiate(cfg.data_source)

    results_dir_path = Path(HydraConfig.get().run.dir)
    results_dir_path.mkdir(parents=True, exist_ok=True)
    results_path = results_dir_path / 'results.jsonl'

    existing_ids = _load_existing_ids(results_path)
    logger.info(f"Resuming — {len(existing_ids)} data points already processed")

    metrics = LocalizationMetricsCollector()
    max_instances = cfg.get('max_instances', 100)
    backbone_model_name = cfg.backbone.model_name

    with open(results_path, 'a', newline='') as f:
        for i, dp in enumerate(data_src):
            if i >= max_instances:
                logger.info(f"Reached {max_instances} instances. Stopping run.")
                break

            if dp['text_id'] in existing_ids:
                logger.info(f"Skipping already-processed {dp['text_id']}")
                continue

            start_time = time.time()
            results_dict = backbone.localize_bugs(dp)
            duration_seconds = time.time() - start_time

            results_dict['time_s'] = duration_seconds
            results_dict['text_id'] = dp['text_id']

            tokens = results_dict.get('total_tokens', 0)
            instance_cost = calculate_cost(backbone_model_name, tokens)

            metrics.add_instance_metrics(
                duration=duration_seconds,
                tokens=tokens,
                cost=instance_cost,
                has_valid_json=results_dict.get('valid_json', False),
                num_files_predicted=results_dict.get('num_predicted_files', 0),
            )

            f.write(json.dumps(results_dict) + "\n")
            f.flush()

    metrics.log_summary(logger)


def _run_parallel(cfg: DictConfig) -> None:
    backbone: BaseBackbone = hydra.utils.instantiate(cfg.backbone)

    max_repos: int = cfg.get('max_repos_on_disk', 3)
    max_workers: int = cfg.get('max_api_workers', 4)

    results_dir_path = Path(HydraConfig.get().run.dir)
    os.makedirs(results_dir_path, exist_ok=True)
    results_path = results_dir_path / 'results.jsonl'

    composer_name = cfg.context_composer.get('name', 'default')
    cache_dir = results_dir_path / 'prompt_cache' / composer_name
    prompt_cache = PromptCache(str(cache_dir))
    logger.info(f"Prompt cache: {cache_dir}  ({len(prompt_cache)} entries)")

    existing_ids = _load_existing_ids(results_path)
    logger.info(f"Resuming — {len(existing_ids)} data points already processed")

    ds_cfg = cfg.data_source
    data_src = HFDataSource(
        hub_name=ds_cfg.hub_name,
        repos_dir=ds_cfg.repos_dir,
        configs=list(ds_cfg.get('configs', [])) or None,
        split=ds_cfg.get('split', None),
        cache_dir=ds_cfg.get('cache_dir', None),
        max_repos_on_disk=max_repos,
    )

    model_name = cfg.backbone.model_name
    write_lock = threading.Lock()
    total_submitted = 0
    total_completed = 0
    total_skipped = 0

    with open(results_path, 'a', buffering=1) as results_file:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: Dict[Any, str] = {}

            for config, repo_name, repo_path, datapoints in data_src.iter_repos_with_datapoints():
                logger.info(f"[{config}] Repo '{repo_name}': {len(datapoints)} data points")

                for dp in datapoints:
                    text_id = dp['text_id']

                    if text_id in existing_ids:
                        total_skipped += 1
                        continue

                    if not prompt_cache.has(text_id):
                        messages = backbone.context_composer.compose_chat(dp, model_name)
                        all_files = list(dp['repo_content'].keys())
                        prompt_cache.put(
                            text_id,
                            messages,
                            dp['changed_files'],
                            all_files,
                        )

                    cached = prompt_cache.get(text_id)
                    if cached is None:
                        logger.warning(f"Missing cached prompt for {text_id}, skipping")
                        continue

                    future = executor.submit(
                        _process_single,
                        backbone,
                        cached['messages'],
                        text_id,
                    )
                    futures[future] = text_id
                    total_submitted += 1

                data_src.delete_repo(repo_path)
                logger.info(f"Repo '{repo_name}' deleted.  Submitted so far: {total_submitted}")

            logger.info(f"All repos processed.  Waiting for {len(futures)} API calls to complete …")
            for future in as_completed(futures):
                text_id = futures[future]
                try:
                    result = future.result()
                    with write_lock:
                        results_file.write(json.dumps(result) + "\n")
                        results_file.flush()
                    total_completed += 1
                    if total_completed % 10 == 0:
                        logger.info(f"Completed {total_completed}/{total_submitted}")
                except Exception as e:
                    logger.error(f"API call failed for {text_id}: {e}")

    logger.info(
        f"Done.  submitted={total_submitted}  completed={total_completed}  skipped={total_skipped}"
    )


@hydra.main(
    version_base="1.1",
    config_path=os.path.join(PROJECT_DIR / "configs"),
    config_name="run.yaml",
)
def main(cfg: DictConfig) -> None:
    OmegaConf.set_struct(cfg, False)
    os.environ['HYDRA_FULL_ERROR'] = '1'

    parallel: bool = cfg.get('parallel', False)

    if parallel:
        logger.info("Running in PARALLEL mode")
        _run_parallel(cfg)
    else:
        logger.info("Running in SEQUENTIAL mode")
        _run_sequential(cfg)


if __name__ == '__main__':
    main()