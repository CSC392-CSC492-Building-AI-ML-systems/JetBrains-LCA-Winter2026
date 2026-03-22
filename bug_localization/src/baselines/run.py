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

# --- ADDED: Metrics Collector ---
class AgenticMetricsCollector:
    def __init__(self):
        self.total_time_seconds = 0
        self.total_token_usage = 0
        self.total_cost_usd = 0
        self.total_lines_edited = 0
        self.total_bugs_fixed = 0
        self.total_new_bugs_introduced = 0
        self.instance_count = 0

    def add_instance_metrics(self, duration, tokens=0, cost=0, edits=0, fixed=0, bugs=0):
        self.total_time_seconds += duration
        self.total_token_usage += tokens
        self.total_cost_usd += cost
        self.total_lines_edited += edits
        self.total_bugs_fixed += fixed
        self.total_new_bugs_introduced += bugs
        self.instance_count += 1

    def log_agentic_summary(self, logger):
        if self.instance_count == 0:
            return
        logger.info("=" * 40)
        logger.info("AGENTIC PARADIGM COMPARISON SUMMARY")
        logger.info("-" * 40)
        logger.info(f"Instances Evaluated:     {self.instance_count}")
        logger.info(f"Total Time (H:M:S):      {time.strftime('%H:%M:%S', time.gmtime(self.total_time_seconds))}")
        logger.info(f"Avg Time/Instance:       {self.total_time_seconds / self.instance_count:.2f}s")
        logger.info(f"Diagnostic Token Usage:  {self.total_token_usage}")
        logger.info(f"Diagnostic Cost (USD):   ${self.total_cost_usd:.4f}")
        logger.info(f"Lines Edited (Passive):  {self.total_lines_edited}")
        logger.info(f"Bugs Fixed (Passive):    {self.total_bugs_fixed}")
        logger.info(f"Regressions (Passive):   {self.total_new_bugs_introduced}")
        logger.info("=" * 40)
# --------------------------------

@hydra.main(version_base="1.1", config_path=os.path.join(PROJECT_DIR / "configs"), config_name="run.yaml")
def main(cfg: DictConfig) -> None:
    OmegaConf.set_struct(cfg, False)
    os.environ['HYDRA_FULL_ERROR'] = '1'

    # Setup logger for the summary output
    log = logging.getLogger(__name__)

    backbone: BaseBackbone = hydra.utils.instantiate(cfg.backbone)
    data_src: BaseDataSource = hydra.utils.instantiate(cfg.data_source)

    results_dir_path = Path(HydraConfig.get().run.dir)
    os.makedirs(results_dir_path, exist_ok=True)
    results_path = results_dir_path / 'results.jsonl'

    # --- ADDED: Initialize Collector ---
    metrics = AgenticMetricsCollector()

    # Added enumerate to track the number of instances
    for i, dp in enumerate(data_src):
        # Exit the loop after processing 100 instances
        if i >= 100:
            log.info("Reached 100 instances. Stopping run.")
            break

        start_time = time.time()
        results_dict = backbone.localize_bugs(dp)
        end_time = time.time()
        
        duration_seconds = end_time - start_time
        
        results_dict['time_s'] = duration_seconds * 1000000
        results_dict['text_id'] = dp['text_id']

        # --- UPDATED: Inside your metrics loop ---
        tokens = results_dict.get('total_tokens', 0)
        
        # Calculate cost (Approx $0.50 per 1M tokens for GPT-3.5 Turbo)
        instance_cost = (tokens / 1_000_000) * 0.50

        metrics.add_instance_metrics(
            duration=duration_seconds,
            tokens=tokens, 
            cost=instance_cost,  # Pass the calculated cost
            edits=0, 
            fixed=0, 
            bugs=0   
        )

        with open(results_path, 'a', newline='') as f:
            f.write(json.dumps(results_dict) + "\n")

    # --- ADDED: Print Summary at the end ---
    metrics.log_agentic_summary(log)


if __name__ == '__main__':
    main()