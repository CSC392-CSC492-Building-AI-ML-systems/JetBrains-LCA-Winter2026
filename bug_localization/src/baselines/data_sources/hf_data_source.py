import os
import shutil
import threading
import zipfile
from collections import defaultdict
from typing import List, Optional, Iterator, Dict, Tuple

import huggingface_hub
from datasets import get_dataset_config_names, load_dataset
from huggingface_hub import hf_hub_download

from src import logger
from src.baselines.data_sources.base_data_source import BaseDataSource
from src.utils.git_utils import get_repo_content_on_commit, get_changed_files_between_commits
from src.utils.hf_utils import HUGGINGFACE_REPO, FEATURES


class HFDataSource(BaseDataSource):
    """
    HuggingFace-backed data source for the bug-localisation benchmark.
    """

    def __init__(
            self,
            hub_name: str,
            repos_dir: str,
            configs: Optional[List[str]] = None,
            split: Optional[str] = None,
            cache_dir: Optional[str] = None,
            max_repos_on_disk: int = 3,
    ):
        self._hub_name = hub_name
        self._cache_dir = cache_dir
        self._repos_dir = repos_dir
        self._max_repos = max_repos_on_disk
        self._semaphore = threading.Semaphore(max_repos_on_disk)

        if configs:
            self._configs = configs
        else:
            self._configs = get_dataset_config_names(self._hub_name)
        self._split = split

        os.makedirs(repos_dir, exist_ok=True)

    # old load repos that downloads at extracts all repos at once
    def _load_repos(self):
        """Download and extract ALL repos referenced by the configs."""
        huggingface_hub.login(token=os.environ['HUGGINGFACE_TOKEN'])
        os.makedirs(self._repos_dir, exist_ok=True)

        # Load json file with repos paths
        paths_json = load_dataset(
            HUGGINGFACE_REPO,
            data_files="repos.json",
            ignore_verifications=True,
            split="train",
            features=FEATURES['repos'],
        )

        local_repo_zips_path = os.path.join(self._repos_dir, "local_repos_zips")

        # Load each repo in .zip format, unzip, delete archive
        for category in self._configs:
            repos = paths_json[category][0]
            for i, repo_zip_path in enumerate(repos):
                logger.info(f"Loading {i}/{len(repos)} {repo_zip_path}")

                repo_name = os.path.basename(repo_zip_path).split('.zip')[0]
                repo_path = os.path.join(self._repos_dir, repo_name)
                if os.path.exists(repo_path):
                    logger.info(f"Repo {repo_zip_path} is already loaded...")
                    continue

                local_repo_zip_path = hf_hub_download(
                    HUGGINGFACE_REPO,
                    filename=repo_zip_path,
                    repo_type='dataset',
                    local_dir=local_repo_zips_path,
                )

                with zipfile.ZipFile(local_repo_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(repo_path)
                os.remove(local_repo_zip_path)

    def __iter__(self):
        """Yield enriched data points one at a time"""
        for config in self._configs:
            dataset = load_dataset(
                self._hub_name, config,
                split=self._split, cache_dir=self._cache_dir,
            )
            self._load_repos()
            for dp in dataset:
                repo_path = os.path.join(
                    self._repos_dir,
                    f"{dp['repo_owner']}__{dp['repo_name']}",
                )
                if not os.path.exists(repo_path):
                    continue
                try:
                    dp['repo_content'] = get_repo_content_on_commit(
                        repo_path, dp['base_sha'],
                        extensions=[config],
                        ignore_tests=True,
                    )
                    dp['changed_files'] = get_changed_files_between_commits(
                        repo_path, dp['base_sha'], dp['head_sha'],
                        extensions=[config],
                        ignore_tests=True,
                    )
                    yield dp
                except Exception as e:
                    logger.warning(
                        f"Failed to get repo content for "
                        f"{dp['repo_owner']}__{dp['repo_name']}: {e}",
                        exc_info=True,
                    )
                    continue

    # extracts one repo at a time, with a limit of repos on disk
    def iter_repos_with_datapoints(
        self,
    ) -> Iterator[Tuple[str, str, str, List[dict]]]:
        huggingface_hub.login(token=os.environ.get('HUGGINGFACE_TOKEN'))

        for config in self._configs:
            logger.info(f"Loading dataset config: {config}")
            dataset = load_dataset(
                self._hub_name, config,
                split=self._split,
                cache_dir=self._cache_dir,
            )

            repo_groups: Dict[str, List[dict]] = defaultdict(list)
            for dp in dataset:
                repo_key = f"{dp['repo_owner']}__{dp['repo_name']}"
                repo_groups[repo_key].append(dp)

            logger.info(
                f"Config '{config}': {len(dataset)} data points across "
                f"{len(repo_groups)} repos"
            )
            
            paths_json = load_dataset(
                HUGGINGFACE_REPO,
                data_files="repos.json",
                ignore_verifications=True,
                split="train",
                features=FEATURES['repos'],
            )
            repo_zip_paths: List[str] = paths_json[config][0]

            # Iterate repos
            for repo_zip_path in repo_zip_paths:
                repo_name = os.path.basename(repo_zip_path).split('.zip')[0]

                if repo_name not in repo_groups:
                    continue  # no data points reference this repo

                dps = repo_groups[repo_name]
                repo_path = os.path.join(self._repos_dir, repo_name)

                # Block until a slot is available
                self._semaphore.acquire()
                logger.info(
                    f"Slot acquired – cloning repo '{repo_name}' "
                    f"({len(dps)} data points)"
                )

                try:
                    # Clone if not already on disk
                    if not os.path.exists(repo_path):
                        self._clone_repo(repo_zip_path, repo_path)

                    # Enrich every data point with repo content
                    enriched: List[dict] = []
                    for dp in dps:
                        try:
                            dp['repo_content'] = get_repo_content_on_commit(
                                repo_path, dp['base_sha'],
                                extensions=[config],
                                ignore_tests=True,
                            )
                            dp['changed_files'] = get_changed_files_between_commits(
                                repo_path, dp['base_sha'], dp['head_sha'],
                                extensions=[config],
                                ignore_tests=True,
                            )
                            enriched.append(dp)
                        except Exception as e:
                            logger.warning(
                                f"Skipping dp text_id={dp.get('text_id')} "
                                f"in repo {repo_name}: {e}"
                            )

                    yield config, repo_name, repo_path, enriched

                except Exception as e:
                    # If cloning / enrichment fails entirely, release
                    # the slot so we don't deadlock.
                    logger.error(f"Failed to process repo {repo_name}: {e}")
                    self._safe_delete(repo_path)
                    self._semaphore.release()

    def delete_repo(self, repo_path: str):
        """
        Delete a repo from disk and release the semaphore slot.

        **Must** be called once per yielded repo from
        :meth:`iter_repos_with_datapoints`.
        """
        self._safe_delete(repo_path)
        self._semaphore.release()
        logger.info(f"Deleted repo and released slot: {repo_path}")

    def _clone_repo(self, repo_zip_path: str, repo_path: str):
        """Download and extract a single repo zip from HuggingFace."""
        logger.info(f"Downloading {repo_zip_path} ...")
        local_zips_dir = os.path.join(self._repos_dir, "_local_repo_zips")

        local_zip = hf_hub_download(
            HUGGINGFACE_REPO,
            filename=repo_zip_path,
            repo_type='dataset',
            local_dir=local_zips_dir,
        )

        logger.info(f"Extracting to {repo_path} ...")
        with zipfile.ZipFile(local_zip, 'r') as zf:
            zf.extractall(repo_path)

        os.remove(local_zip)
        logger.info(f"Repo ready: {repo_path}")

    @staticmethod
    def _safe_delete(path: str):
        """Delete a directory tree, ignoring errors if it doesn't exist."""
        try:
            if os.path.exists(path):
                shutil.rmtree(path)
        except Exception as e:
            logger.warning(f"Could not delete {path}: {e}")
