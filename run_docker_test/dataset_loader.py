from dotenv import load_dotenv
from datasets import load_dataset, Dataset
from typing import TypedDict, cast

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

def load_swebench_lite_dataset():
    name = "SWE-bench/SWE-bench_Lite"
    split = "dev"
    dataset = cast(Dataset, load_dataset(name, split=split))

    return [cast(SWEbenchInstance, instance) for instance in dataset]

if __name__ == "__main__":
    dataset = load_swebench_lite_dataset()
    for i in range(1):
        print(dataset[i]["repo"])