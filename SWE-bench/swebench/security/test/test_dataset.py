"""Unit tests for swebench.security.dataset"""
import pytest

from swebench.security.dataset import FEATURE_REQUESTS, PROJECTS_DIR, load_dataset


def test_load_all_instances():
    instances = load_dataset()
    assert len(instances) == 9


def test_filter_by_single_project():
    instances = load_dataset(projects=["project_a"])
    assert len(instances) == 3
    assert all(i.project_id == "project_a" for i in instances)


def test_filter_by_single_track():
    instances = load_dataset(tracks=[1])
    assert len(instances) == 3
    assert all(i.track == 1 for i in instances)


def test_filter_by_project_and_track():
    instances = load_dataset(projects=["project_b"], tracks=[2, 3])
    assert len(instances) == 2
    assert all(i.project_id == "project_b" for i in instances)
    assert {i.track for i in instances} == {2, 3}


def test_instance_id_format():
    instances = load_dataset()
    for i in instances:
        assert i.instance_id == f"{i.project_id}__track_{i.track}"


def test_ground_truth_paths_exist():
    instances = load_dataset()
    for i in instances:
        assert i.ground_truth_path.exists(), (
            f"ground_truth.json missing for {i.instance_id}: {i.ground_truth_path}"
        )


def test_project_paths_exist():
    instances = load_dataset()
    for i in instances:
        assert i.project_path.exists(), (
            f"Project path missing for {i.instance_id}: {i.project_path}"
        )


def test_track3_has_feature_request():
    instances = load_dataset(tracks=[3])
    for i in instances:
        assert i.feature_request is not None
        assert len(i.feature_request) > 0


def test_track1_and_2_no_feature_request():
    instances = load_dataset(tracks=[1, 2])
    for i in instances:
        assert i.feature_request is None


def test_prompts_not_empty():
    instances = load_dataset()
    for i in instances:
        assert len(i.prompt) > 0


def test_track3_prompts_contain_feature_request():
    instances = load_dataset(tracks=[3])
    for i in instances:
        assert i.feature_request in i.prompt


def test_all_projects_covered():
    instances = load_dataset()
    project_ids = {i.project_id for i in instances}
    assert project_ids == {"project_a", "project_b", "project_c"}


def test_all_tracks_covered():
    instances = load_dataset()
    tracks = {i.track for i in instances}
    assert tracks == {1, 2, 3}


def test_load_ground_truth():
    instances = load_dataset(projects=["project_a"], tracks=[1])
    gt = instances[0].load_ground_truth()
    assert isinstance(gt, list)
    assert len(gt) > 0
    for entry in gt:
        assert "cwe_id" in entry
        assert "file" in entry
        assert "line_start" in entry
