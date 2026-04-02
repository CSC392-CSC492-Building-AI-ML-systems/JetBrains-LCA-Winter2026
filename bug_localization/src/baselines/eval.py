import json
import os
from pathlib import Path

import hydra
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf

from src import PROJECT_DIR, logger
from src.baselines.data_sources.base_data_source import BaseDataSource
from src.baselines.data_sources.prompt_cache import PromptCache
from src.baselines.metrics.context_metrics import get_context_metrics
from src.baselines.metrics.quality_metrics import get_quality_metrics

# Citations and Disclaimer:
# Google. (2026, April 2). what metrics can I add here(probably). Gemini. https://gemini.google.com/share/5555b4329945
# Note that I discuss with GEMINI about a lot of stuff and this chat history link contain almost everything for this course
# includes stuff related to the codes I added in here, but I personally cannot remember the specific prompt.
# It is almost impossible to find it in the 4 month chat history log and it took a long time to even open the link,
# so please don't waste time trying to find it, but I am sure it's somewhere in the chat history.

class AccuracyMetricsCollector:
    def __init__(self):
        self.total_instances = 0
        self.sums = {}

    def add_metrics(self, metrics_dict):
        self.total_instances += 1
        for key, value in metrics_dict.items():
            if isinstance(value, (int, float)):
                self.sums[key] = self.sums.get(key, 0) + float(value)

    def print_summary(self, log):
        if self.total_instances == 0:
            log.warning("No matching results found to evaluate.")
            return

        log.info("=" * 45)
        log.info("BUG LOCALIZATION ACCURACY SUMMARY")
        log.info("-" * 45)
        log.info(f"Total Graded Instances: {self.total_instances}")

        for key, total in self.sums.items():
            avg = total / self.total_instances

            if "Count" in key:
                log.info(f"Average {key}: {avg:.2f}")
            else:
                log.info(f"Average {key}: {(avg * 100):.2f}%")

        log.info("=" * 45)


@hydra.main(version_base="1.1", config_path=str(PROJECT_DIR / "configs"), config_name="eval.yaml")
def main(cfg: DictConfig) -> None:
    OmegaConf.set_struct(cfg, False)
    os.environ['HYDRA_FULL_ERROR'] = '1'

    data_src: BaseDataSource = hydra.utils.instantiate(cfg.data_source)

    eval_dir_path = Path(HydraConfig.get().run.dir)
    eval_dir_path.mkdir(parents=True, exist_ok=True)
    eval_results_path = eval_dir_path / 'results.jsonl'

    data_path = Path(hydra.utils.to_absolute_path(cfg.data_path))
    standard_path = data_path / 'run' / cfg.run_id / 'results.jsonl'
    nested_path = data_path / 'run' / cfg.run_id / 'data' / 'run' / cfg.run_id / 'results.jsonl'

    if nested_path.exists():
        run_results_path = nested_path
    elif standard_path.exists():
        run_results_path = standard_path
    else:
        logger.error(f"Could not find results file.\nChecked:\n1. {standard_path}\n2. {nested_path}")
        return

    cache_dir = data_path / 'run' / cfg.run_id / 'prompt_cache'
    composer_dirs = list(cache_dir.glob('*')) if cache_dir.exists() else []
    if composer_dirs:
        prompt_cache = PromptCache(str(composer_dirs[0]))
        logger.info(f"Using prompt cache with {len(prompt_cache)} entries")
    else:
        logger.warning("No prompt cache found - falling back to re-loading dataset")
        prompt_cache = None

    run_by_text_id = {}
    with open(run_results_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            text_id = data.get('text_id')
            run_by_text_id[text_id] = data

    summary_collector = AccuracyMetricsCollector()

    with open(eval_results_path, 'a', encoding='utf-8', newline='') as f:
        if prompt_cache:
            for text_id, run_result in run_by_text_id.items():
                if not run_result.get('json_completion'):
                    continue

                cached_data = prompt_cache.get(text_id)
                if not cached_data:
                    logger.warning(f"No cache entry for {text_id}, skipping")
                    continue

                all_files = cached_data['all_files']
                expected_files = cached_data['changed_files']

                try:
                    files = json.loads(run_result['json_completion'])
                except Exception:
                    files = {'files': []}

                actual_files = files.get('files', []) if isinstance(files, dict) else files
                eval_result = {'text_id': text_id}

                quality_metrics = get_quality_metrics(all_files, expected_files, actual_files)
                eval_result.update(quality_metrics)
                summary_collector.add_metrics(quality_metrics)

                messages_str = run_result.get('messages', '[]')
                try:
                    messages = json.loads(messages_str)
                except json.JSONDecodeError:
                    messages = []

                context_metrics = get_context_metrics(messages)
                eval_result.update(context_metrics)

                f.write(json.dumps(eval_result) + "\n")
        else:
            for dp in data_src:
                run_result = run_by_text_id.get(dp['text_id'])
                if not run_result:
                    continue

                actual_files = []
                json_completion = run_result.get('json_completion')
                if json_completion:
                    try:
                        files_data = json.loads(json_completion)
                        if isinstance(files_data, list):
                            actual_files = files_data
                        elif isinstance(files_data, dict):
                            actual_files = files_data.get('files', [])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON for text_id {dp['text_id']}")

                all_files = list(dp.get('repo_content', {}).keys())
                expected_files = dp.get('changed_files', [])

                eval_result = {'text_id': dp['text_id']}

                quality_metrics = get_quality_metrics(all_files, expected_files, actual_files)
                eval_result.update(quality_metrics)
                summary_collector.add_metrics(quality_metrics)

                messages_str = run_result.get('messages', '[]')
                try:
                    messages = json.loads(messages_str)
                except json.JSONDecodeError:
                    messages = []

                context_metrics = get_context_metrics(messages)
                eval_result.update(context_metrics)

                f.write(json.dumps(eval_result) + "\n")

    summary_collector.print_summary(logger)


if __name__ == '__main__':
    main()