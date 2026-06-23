import pytest

from benchmarks._safety import safe_rmtree_child, safe_unlink_child


def test_safe_rmtree_child_removes_expected_hidden_run_dir(tmp_path):
    output_dir = tmp_path / "output"
    run_dir = output_dir / ".trace-loop-seed-1"
    run_dir.mkdir(parents=True)
    (run_dir / "artifact.txt").write_text("ok", encoding="utf-8")

    safe_rmtree_child(output_dir, run_dir, allowed_prefixes=(".trace-loop-seed-",))

    assert not run_dir.exists()


def test_safe_rmtree_child_rejects_path_outside_output_dir(tmp_path):
    output_dir = tmp_path / "output"
    outside = tmp_path / "outside"
    output_dir.mkdir()
    outside.mkdir()

    with pytest.raises(ValueError, match="outside benchmark output dir"):
        safe_rmtree_child(output_dir, outside, allowed_prefixes=(".trace-loop-seed-",))


def test_safe_rmtree_child_rejects_same_prefix_sibling_outside_output_dir(tmp_path):
    output_dir = tmp_path / "output"
    sibling = tmp_path / "output_evil" / ".trace-loop-seed-1"
    output_dir.mkdir()
    sibling.mkdir(parents=True)

    with pytest.raises(ValueError, match="outside benchmark output dir"):
        safe_rmtree_child(output_dir, sibling, allowed_prefixes=(".trace-loop-seed-",))


def test_safe_rmtree_child_rejects_output_dir_itself(tmp_path):
    output_dir = tmp_path / ".trace-loop-seed-output"
    output_dir.mkdir()

    with pytest.raises(ValueError, match="output dir itself"):
        safe_rmtree_child(output_dir, output_dir, allowed_prefixes=(".trace-loop-seed-",))


def test_safe_rmtree_child_rejects_unexpected_directory_name(tmp_path):
    output_dir = tmp_path / "output"
    unexpected = output_dir / "regular-dir"
    unexpected.mkdir(parents=True)

    with pytest.raises(ValueError, match="unexpected benchmark directory"):
        safe_rmtree_child(output_dir, unexpected, allowed_prefixes=(".trace-loop-seed-",))


def test_safe_unlink_child_rejects_directory(tmp_path):
    output_dir = tmp_path / "output"
    directory = output_dir / "raw_results.json"
    directory.mkdir(parents=True)

    with pytest.raises(ValueError, match="non-file"):
        safe_unlink_child(output_dir, directory)
