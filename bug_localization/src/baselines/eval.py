import json
import os
import logging
from pathlib import Path

import hydra
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf

from src import PROJECT_DIR, logger
from src.baselines.data_sources.base_data_source import BaseDataSource
from src.baselines.metrics.context_metrics import get_context_metrics
from src.baselines.metrics.quality_metrics import get_quality_metrics

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
            
            # Only multiply by 100 if it is a percentage metric
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

    # fix path finding issue
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
        
    run_by_text_id = {}
    with open(run_results_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                text_id = data.get('text_id')
                run_by_text_id[text_id] = data
    summary_collector = AccuracyMetricsCollector()

    with open(eval_results_path, 'a', encoding='utf-8', newline='') as f:
        for dp in data_src:
            run_result = run_by_text_id.get(dp['text_id'])
            
            if not run_result:
                continue
                
            # get complete json
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

            # extract repository's path
            all_files = list(dp.get('repo_content', {}).keys())
            expected_files = dp.get('changed_files', [])

            eval_result = {'text_id': dp['text_id']}

            # get metrics
            quality_metrics = get_quality_metrics(all_files, expected_files, actual_files)
            eval_result.update(quality_metrics)
            
            # add to metrics
            summary_collector.add_metrics(quality_metrics)

            # handle message
            messages_str = run_result.get('messages', '[]')
            try:
                messages = json.loads(messages_str)
            except json.JSONDecodeError:
                messages = []
                
            context_metrics = get_context_metrics(messages)
            eval_result.update(context_metrics)

            f.write(json.dumps(eval_result) + "\n")

    # print the summary
    summary_collector.print_summary(logger)

if __name__ == '__main__':
    main()