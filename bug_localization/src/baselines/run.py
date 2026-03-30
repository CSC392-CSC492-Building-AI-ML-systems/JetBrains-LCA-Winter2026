import json
import os
import time
import logging
from pathlib import Path

import hydra
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf

from src import PROJECT_DIR
from src.baselines.backbone.base_backbone import BaseBackbone
from src.baselines.data_sources.base_data_source import BaseDataSource

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
    # calculate evaluation metrics
    def log_summary(self, logger):
        if self.instance_count == 0:
            return
        
        avg_time = self.total_time_seconds / self.instance_count
        compliance_rate = (self.valid_format_count / self.instance_count) * 100
        avg_files = self.total_files_predicted / self.valid_format_count if self.valid_format_count > 0 else 0

        logger.info("=" * 45)
        logger.info("BUG LOCALIZATION (PASSIVE) METRICS SUMMARY")
        logger.info("-" * 45)
        logger.info(f"Instances Evaluated:       {self.instance_count}")
        logger.info(f"Total Time (H:M:S):        {time.strftime('%H:%M:%S', time.gmtime(self.total_time_seconds))}")
        logger.info(f"Avg Time/Instance:         {avg_time:.2f}s")
        logger.info(f"Total Token Usage:         {self.total_token_usage}")
        logger.info(f"Estimated Cost (USD):      ${self.total_cost_usd:.4f}")
        logger.info("-" * 45)
        logger.info(f"Valid JSON Outputs:        {self.valid_format_count} ({compliance_rate:.1f}%)")
        logger.info(f"Avg Files Guessed:         {avg_files:.2f} per valid run")
        logger.info(f"Empty Predictions:         {self.empty_predictions}")
        logger.info("=" * 45)

# assuming we only run gpt 3.5, gemini 2.5 flash, claude 4.5 haiku
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

@hydra.main(version_base="1.1", config_path=os.path.join(PROJECT_DIR / "configs"), config_name="run.yaml")
def main(cfg: DictConfig) -> None:
    OmegaConf.set_struct(cfg, False)
    os.environ['HYDRA_FULL_ERROR'] = '1'

    log = logging.getLogger(__name__)

    backbone: BaseBackbone = hydra.utils.instantiate(cfg.backbone)
    data_src: BaseDataSource = hydra.utils.instantiate(cfg.data_source)

    results_dir_path = Path(HydraConfig.get().run.dir)
    results_dir_path.mkdir(parents=True, exist_ok=True)
    results_path = results_dir_path / 'results.jsonl'

    metrics = LocalizationMetricsCollector()
    max_instances = cfg.get('max_instances', 100)

    # Open file once outside the loop
    with open(results_path, 'a', newline='') as f:
        for i, dp in enumerate(data_src):
            if i >= max_instances:
                log.info(f"Reached {max_instances} instances. Stopping run.")
                break

            start_time = time.time()
            results_dict = backbone.localize_bugs(dp)
            duration_seconds = time.time() - start_time
            
            # Save time and text id in result dictionary
            results_dict['time_s'] = duration_seconds
            results_dict['text_id'] = dp['text_id']

            tokens = results_dict.get('total_tokens', 0)
            instance_cost = calculate_cost(cfg.backbone._target_, tokens)

            metrics.add_instance_metrics(
                duration=duration_seconds,
                tokens=tokens, 
                cost=instance_cost,
                has_valid_json=results_dict.get('valid_json', False),
                num_files_predicted=results_dict.get('num_predicted_files', 0)
            )

            f.write(json.dumps(results_dict) + "\n")
            f.flush()

    metrics.log_summary(log)

if __name__ == '__main__':
    main()