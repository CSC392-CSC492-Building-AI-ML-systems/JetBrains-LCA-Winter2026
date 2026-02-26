"""
Bug-localisation benchmark runner.

Supports two modes (controlled by ``parallel`` config flag):

1. **Legacy mode** (``parallel: false``, default):
   Iterates data points sequentially — clone all repos up-front, call
   the LLM one data point at a time.  Identical to the original behaviour.

2. **Parallel mode** (``parallel: true``):
   - Repos are cloned **sequentially**, one at a time, bounded by
     ``max_repos_on_disk`` (default 3).
   - As soon as a repo is ready, all prompts for its data points are
     composed and **cached to disk** via :class:`PromptCache`.
   - The repo is then **deleted** to free space.
   - LLM API calls are dispatched to a thread pool
     (``max_api_workers`` threads) and run **in parallel**.
   - On restart, already-processed ``text_id``s and already-cached
     prompts are skipped automatically (**resumability**).
"""

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List

import hydra
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf

from src import PROJECT_DIR, logger
from src.baselines.backbone.base_backbone import BaseBackbone
from src.baselines.data_sources.base_data_source import BaseDataSource
from src.baselines.data_sources.hf_data_source import HFDataSource
from src.baselines.data_sources.prompt_cache import PromptCache


# ──────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────
#  Legacy (sequential) mode — original behaviour
# ──────────────────────────────────────────────────────────────────────

def _run_sequential(cfg: DictConfig) -> None:
    backbone: BaseBackbone = hydra.utils.instantiate(cfg.backbone)
    data_src: BaseDataSource = hydra.utils.instantiate(cfg.data_source)

    results_dir_path = Path(HydraConfig.get().run.dir)
    os.makedirs(results_dir_path, exist_ok=True)
    results_path = results_dir_path / 'results.jsonl'

    existing_ids = _load_existing_ids(results_path)
    logger.info(f"Resuming — {len(existing_ids)} data points already processed")

    with open(results_path, 'a', buffering=1) as f:
        for dp in data_src:
            if dp['text_id'] in existing_ids:
                logger.info(f"Skipping already-processed {dp['text_id']}")
                continue

            start_time = time.time()
            results_dict = backbone.localize_bugs(dp)
            end_time = time.time()
            results_dict['time_s'] = end_time - start_time
            results_dict['text_id'] = dp['text_id']

            f.write(json.dumps(results_dict) + "\n")
            f.flush()


# ──────────────────────────────────────────────────────────────────────
#  Parallel mode — clone → cache prompts → delete repo → call LLM
# ──────────────────────────────────────────────────────────────────────

def _run_parallel(cfg: DictConfig) -> None:
    backbone: BaseBackbone = hydra.utils.instantiate(cfg.backbone)

    max_repos: int = cfg.get('max_repos_on_disk', 3)
    max_workers: int = cfg.get('max_api_workers', 4)

    results_dir_path = Path(HydraConfig.get().run.dir)
    os.makedirs(results_dir_path, exist_ok=True)
    results_path = results_dir_path / 'results.jsonl'

    # ── Prompt cache (strategy-aware) ─────────────────────────────
    composer_name = cfg.context_composer.get('name', 'default')
    cache_dir = results_dir_path / 'prompt_cache' / composer_name
    prompt_cache = PromptCache(str(cache_dir))
    logger.info(f"Prompt cache: {cache_dir}  ({len(prompt_cache)} entries)")

    # ── Resumability ──────────────────────────────────────────────
    existing_ids = _load_existing_ids(results_path)
    logger.info(f"Resuming — {len(existing_ids)} data points already processed")

    # ── Repo manager ──────────────────────────────────────────────
    ds_cfg = cfg.data_source
    data_src = HFDataSource(
        hub_name=ds_cfg.hub_name,
        repos_dir=ds_cfg.repos_dir,
        configs=list(ds_cfg.get('configs', [])) or None,
        split=ds_cfg.get('split', None),
        cache_dir=ds_cfg.get('cache_dir', None),
        max_repos_on_disk=max_repos,
    )

    # ── Shared state for result writing ───────────────────────────
    write_lock = threading.Lock()
    total_submitted = 0
    total_completed = 0
    total_skipped = 0

    with open(results_path, 'a', buffering=1) as results_file:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: Dict[Any, str] = {}

            # ── Phase 1: stream repos, compose & cache, submit ────
            for config, repo_name, repo_path, datapoints in \
                    data_src.iter_repos_with_datapoints():

                logger.info(
                    f"[{config}] Repo '{repo_name}': "
                    f"{len(datapoints)} data points"
                )

                for dp in datapoints:
                    text_id = dp['text_id']

                    # Already have a final result → skip entirely
                    if text_id in existing_ids:
                        total_skipped += 1
                        continue

                    # Compose and cache prompt (requires repo on disk)
                    if not prompt_cache.has(text_id):
                        messages = backbone.context_composer.compose_chat(
                            dp, backbone.model_name,
                        )
                        all_files = list(dp['repo_content'].keys())
                        prompt_cache.put(
                            text_id, messages,
                            dp['changed_files'], all_files,
                        )

                    # Submit API call using cached prompt
                    cached = prompt_cache.get(text_id)
                    future = executor.submit(
                        _process_single, backbone,
                        cached['messages'], text_id,
                    )
                    futures[future] = text_id
                    total_submitted += 1

                # ── All prompts for this repo are cached → delete ─
                data_src.delete_repo(repo_path)
                logger.info(
                    f"Repo '{repo_name}' deleted.  "
                    f"Submitted so far: {total_submitted}"
                )

            # ── Phase 2: collect results as they complete ─────────
            logger.info(
                f"All repos processed.  Waiting for {len(futures)} "
                f"API calls to complete …"
            )
            for future in as_completed(futures):
                text_id = futures[future]
                try:
                    result = future.result()
                    with write_lock:
                        results_file.write(json.dumps(result) + "\n")
                        results_file.flush()
                    total_completed += 1
                    if total_completed % 10 == 0:
                        logger.info(
                            f"Completed {total_completed}/{total_submitted}"
                        )
                except Exception as e:
                    logger.error(
                        f"API call failed for {text_id}: {e}"
                    )

    logger.info(
        f"Done.  submitted={total_submitted}  completed={total_completed}  "
        f"skipped={total_skipped}"
    )


# ──────────────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────────────

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
        logger.info("Running in SEQUENTIAL (legacy) mode")
        _run_sequential(cfg)


if __name__ == '__main__':
    main()
