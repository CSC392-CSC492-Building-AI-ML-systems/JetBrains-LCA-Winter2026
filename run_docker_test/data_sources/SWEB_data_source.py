import os

from dotenv import load_dotenv
from datasets import load_dataset, Dataset
from typing import TypedDict, cast
import git

from constants import data_path

load_dotenv()

class SWEbenchInstance(TypedDict):
    repo: str
    instance_id: str
    base_commit: str
    patch: str
    test_patch: str
    problem_statement: str
    hints_text: str
    created_at: str
    version: str
    FAIL_TO_PASS: str
    PASS_TO_PASS: str
    environment_setup_commit: str

def load_swebench_lite_dataset(split = "dev"):
    name = "SWE-bench/SWE-bench_Lite"
    dataset = cast(Dataset, load_dataset(name, split=split))

    return [cast(SWEbenchInstance, instance) for instance in dataset]

class SWELiteDataSource():
    def __init__(self, split, repos_dir):
        self._split = split
        self._repos_dir = repos_dir
        self.dataset = load_swebench_lite_dataset(split)
        self.__load_dataset()

    def __load_dataset(self):
        for i, item in enumerate(self.dataset):
            if i > 5:
                break
            repo_name = item["repo"].split("/")[-1]
            full_url = "https://github.com/" + item["repo"]
            repo_path = f"{self._repos_dir}/{repo_name}"
            if not os.path.exists(repo_path):
                git.Repo.clone_from(full_url, repo_path)

    def __iter__(self):
        for item in self.dataset:
            repo_name = item["repo"].split("/")[-1]
            repo_path = f"{self._repos_dir}/{repo_name}"
            yield {
                "text_id": item["instance_id"],
                "repo_path": repo_path,
                "base_commit": item["base_commit"],
                "patch": item["patch"],
                "test_patch": item["test_patch"],
                "problem_statement": item["problem_statement"],
                "hints_text": item["hints_text"],
                "FAIL_TO_PASS": item["FAIL_TO_PASS"],
                "PASS_TO_PASS": item["PASS_TO_PASS"],
                "environment_setup_commit": item["environment_setup_commit"]
            }

if __name__ == "__main__":
    source = SWELiteDataSource("dev", data_path)