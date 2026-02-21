import json
import os
from pathlib import Path
import docker

import hydra
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf
from src.baselines.utils.docker_utils import clean_images, build_env_images, start_container, copy_to_container
from src import PROJECT_DIR, logger
from src.baselines.data_sources.base_data_source import BaseDataSource
from src.baselines.metrics.context_metrics import get_context_metrics
from src.baselines.metrics.quality_metrics import get_quality_metrics


@hydra.main(version_base="1.1", config_path=os.path.join(PROJECT_DIR / "configs"), config_name="eval.yaml")
def main(cfg: DictConfig) -> None:
    OmegaConf.set_struct(cfg, False)
    os.environ['HYDRA_FULL_ERROR'] = '1'

    # look at /home/wu/CSC398/SWE-bench/swebench/harness/utils.py load_swebench_dataset(...) to figure out how to load
    # swe dataset
    data_src: BaseDataSource = hydra.utils.instantiate(cfg.data_source)

    eval_dir_path = Path(HydraConfig.get().run.dir)
    os.makedirs(eval_dir_path, exist_ok=True)
    eval_results_path = eval_dir_path / 'results.jsonl'

    # TO-DOs: need to figure out where the patch file is located
    patch_path = ""
    # os.path.join(cfg.data_path, 'run', cfg.run_id, 'results.jsonl')
    run_by_text_id = {}
    # with open(patch_path, 'r') as f:
    #     for line in f.readlines():
    #         data = json.loads(line.strip())
    #         text_id = data.get('text_id')
            # run_by_text_id[text_id] = data
            
    for patch_filename in os.listdir(patch_path):
        if patch_filename.endswith(".diff"):
            text_id = os.path.splitext(patch_filename)[0]
           
            original_patch_file = Path(patch_path) / patch_filename
           
            # open the patch file
            with open(os.path.join(patch_path, patch_filename), 'r') as f:
                patch_content = f.read()
                
            # store text id with patch content
            run_by_text_id[text_id] = {
                'text_id': text_id,
                'patch_content': patch_content,
                'patch_path': original_patch_file # <-- Save the path here!
            }
            
    # instance_image_tag: str = "latest",
    # env_image_tag: str = "latest",
    client = docker.from_env()
    for dp in data_src:
        run_result = run_by_text_id.get(dp['text_id'])
        if not run_result:
            continue
        if run_result['patch_content']:
            # try:
            #     files = json.loads(run_result['json_completion'])
            # except Exception as e:
            #     files = {'files': []}

            logger.info(f'processing {0}'.format(dp['text_id']))
        
            image_tag = build_env_images(dp, client, run_result['patch_content'])
            container = start_container(client, image_tag)
            container.start()
            local_patch = run_result['patch_path']
            container_patch = Path("/app/patch.diff")
            copy_to_container(container, local_patch, container_patch)
            container.exec_run("git apply patch.diff", workdir="/app")
            # logger.info(len(files['files']))

            # Don't need following as they are for bug localization
            # all_files = [path for path, _ in dp['repo_content'].items()]
            # expected_files = dp['changed_files']
            # actual_files = files['files'] if files else []

            # eval_result = {'text_id': dp['text_id']}

            # quality_metrics = get_quality_metrics(all_files, expected_files, actual_files)
            # logger.info(quality_metrics)
            # eval_result.update(quality_metrics)

            # messages = json.loads(run_result['messages'])
            # context_metrics = get_context_metrics(messages)
            # eval_result.update(context_metrics)

            # with open(eval_results_path, 'a', newline='') as f:
            #     f.write(json.dumps(eval_result) + "\n")
            clean_images(image_tag)

if __name__ == '__main__':
    main()
