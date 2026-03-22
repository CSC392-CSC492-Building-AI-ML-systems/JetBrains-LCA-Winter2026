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

# --- ADDED: Aggregator to calculate average accuracy ---
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
            
            # --- FIXED: Only multiply by 100 if it is not a raw Count ---
            if "Count" in key:
                log.info(f"Average {key}: {avg:.2f}") 
            else:
                log.info(f"Average {key}: {(avg * 100):.2f}%")
                
        log.info("=" * 45)
# -------------------------------------------------------

@hydra.main(version_base="1.1", config_path=os.path.join(PROJECT_DIR / "configs"), config_name="eval.yaml")
def main(cfg: DictConfig) -> None:
    OmegaConf.set_struct(cfg, False)
    os.environ['HYDRA_FULL_ERROR'] = '1'

    data_src: BaseDataSource = hydra.utils.instantiate(cfg.data_source)

    eval_dir_path = Path(HydraConfig.get().run.dir)
    os.makedirs(eval_dir_path, exist_ok=True)
    eval_results_path = eval_dir_path / 'results.jsonl'

    # Load the predictions you just generated
    # run_results_path = os.path.join(hydra.utils.to_absolute_path(cfg.data_path), 'run', cfg.run_id, 'results.jsonl')
    run_results_path = "/home/wu/CSC398/JetBrains-LCA-Winter2026/bug_localization/data/run/openai-gpt-3.5-turbo-1106_issue_only/data/run/openai-gpt-3.5-turbo-1106_issue_only/results.jsonl"
    run_by_text_id = {}
    
    try:
        with open(run_results_path, 'r') as f:
            for line in f.readlines():
                data = json.loads(line.strip())
                text_id = data.get('text_id')
                run_by_text_id[text_id] = data
    except FileNotFoundError:
        logger.error(f"Could not find results file at: {run_results_path}")
        return

    # --- ADDED: Initialize the collector ---
    summary_collector = AccuracyMetricsCollector()

    for dp in data_src:
        run_result = run_by_text_id.get(dp['text_id'])
        
        # Safely skip the dev instances you didn't process
        if not run_result:
            continue
            
        if run_result.get('json_completion'):
            try:
                files = json.loads(run_result['json_completion'])
                # Failsafe if the LLM output a list instead of a dict
                if isinstance(files, list):
                    files = {'files': files}
            except Exception as e:
                files = {'files': []}
        else:
            files = {'files': []}

        all_files = [path for path, _ in dp['repo_content'].items()]
        expected_files = dp['changed_files']
        actual_files = files.get('files', [])

        eval_result = {'text_id': dp['text_id']}

        # Calculate metrics for this specific bug
        quality_metrics = get_quality_metrics(all_files, expected_files, actual_files)
        eval_result.update(quality_metrics)
        
        # --- ADDED: Add to running total ---
        summary_collector.add_metrics(quality_metrics)

        messages = json.loads(run_result.get('messages', '[]'))
        context_metrics = get_context_metrics(messages)
        eval_result.update(context_metrics)

        with open(eval_results_path, 'a', newline='') as f:
            f.write(json.dumps(eval_result) + "\n")

    # --- ADDED: Print final presentation summary ---
    summary_collector.print_summary(logger)

if __name__ == '__main__':
    main()