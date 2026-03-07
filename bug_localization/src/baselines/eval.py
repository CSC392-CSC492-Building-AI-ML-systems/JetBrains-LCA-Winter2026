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


@hydra.main(version_base="1.1", config_path=os.path.join(PROJECT_DIR / "configs"), config_name="eval.yaml")
def main(cfg: DictConfig) -> None:
    OmegaConf.set_struct(cfg, False)
    os.environ['HYDRA_FULL_ERROR'] = '1'

    eval_dir_path = Path(HydraConfig.get().run.dir)
    os.makedirs(eval_dir_path, exist_ok=True)
    eval_results_path = eval_dir_path / 'results.jsonl'

    data_path = Path(cfg.data_path)
    if not data_path.is_absolute():
        data_path = PROJECT_DIR / data_path
    run_results_path = data_path / 'run' / cfg.run_id / 'results.jsonl'
    
    # Load prompt cache with ground truth data
    cache_dir = data_path / 'run' / cfg.run_id / 'prompt_cache'
    # Find the composer subdirectory
    composer_dirs = list(cache_dir.glob('*')) if cache_dir.exists() else []
    if composer_dirs:
        prompt_cache = PromptCache(str(composer_dirs[0]))
        logger.info(f"Using prompt cache with {len(prompt_cache)} entries")
    else:
        logger.warning("No prompt cache found - falling back to re-loading dataset")
        prompt_cache = None
    
    run_by_text_id = {}
    with open(run_results_path, 'r') as f:
        for line in f.readlines():
            data = json.loads(line.strip())
            text_id = data.get('text_id')
            run_by_text_id[text_id] = data

    for text_id, run_result in run_by_text_id.items():
        if not run_result.get('json_completion'):
            continue
            
        # Get ground truth from cache instead of re-loading repos
        if prompt_cache and prompt_cache.has(text_id):
            cached_data = prompt_cache.get(text_id)
            expected_files = cached_data['changed_files']
            all_files = cached_data['all_files']
        else:
            logger.warning(f"No cache entry for {text_id}, skipping")
            continue

        try:
            files = json.loads(run_result['json_completion'])
        except Exception as e:
            files = {'files': []}

        logger.info(files)
        logger.info(len(files.get('files', [])))

        actual_files = files.get('files', []) if files else []
        eval_result = {'text_id': text_id}

        quality_metrics = get_quality_metrics(all_files, expected_files, actual_files)
        logger.info(quality_metrics)
        eval_result.update(quality_metrics)

        messages = json.loads(run_result['messages'])
        context_metrics = get_context_metrics(messages)
        eval_result.update(context_metrics)

        with open(eval_results_path, 'a', newline='') as f:
            f.write(json.dumps(eval_result) + "\n")


if __name__ == '__main__':
    main()
