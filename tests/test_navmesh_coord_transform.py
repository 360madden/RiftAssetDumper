"""Tests for navmesh coordinate transform and calibration capture helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.navmesh_calibration_capture import (
    _generate_stub_samples,
    add_landmark,
)
from scripts.navmesh_coord_transform import (
    compute_transform,
    load_transform,
    memory_to_obj,
    obj_to_memory,
    save_transform,
)


class TestTransformMath:
    """Unit tests for the core OBJ↔memory transform math."""

    def test_identity_transform_round_trip(self) -> None:
        transform = {
            "scale": [1.0, 1.0, 1.0],
            "offset": [0.0, 0.0, 0.0],
            "axis_mapping": [1, 1, 1],
        }
        px, py, pz = obj_to_memory(1.0, 2.0, 3.0, transform)
        assert (px, py, pz) == pytest.approx((1.0, 2.0, 3.0))

        x, y, z = memory_to_obj(px, py, pz, transform)
        assert (x, y, z) == pytest.approx((1.0, 2.0, 3.0))

    def test_scale_and_offset_transform(self) -> None:
        transform = {
            "scale": [10.0, 10.0, 10.0],
            "offset": [0.0, 5.0, 0.0],
            "axis_mapping": [1, 1, 1],
        }
        px, py, pz = obj_to_memory(1.0, 2.0, 3.0, transform)
        assert (px, py, pz) == pytest.approx((10.0, 25.0, 30.0))

        x, y, z = memory_to_obj(px, py, pz, transform)
        assert (x, y, z) == pytest.approx((1.0, 2.0, 3.0))

    def test_axis_flip(self) -> None:
        transform = {
            "scale": [1.0, 1.0, 1.0],
            "offset": [0.0, 0.0, 0.0],
            "axis_mapping": [-1, 1, -1],
        }
        px, py, pz = obj_to_memory(1.0, 2.0, 3.0, transform)
        assert (px, py, pz) == pytest.approx((-1.0, 2.0, -3.0))

        x, y, z = memory_to_obj(px, py, pz, transform)
        assert (x, y, z) == pytest.approx((1.0, 2.0, 3.0))


class TestComputeTransform:
    """Tests for computing transforms from calibration samples."""

    def test_compute_transform_from_stub_samples(self) -> None:
        samples = _generate_stub_samples()
        transform = compute_transform(samples, validation_tolerance=0.5)

        assert transform["scale"] == pytest.approx([10.0, 10.0, 10.0])
        assert transform["offset"] == pytest.approx([0.0, 5.0, 0.0])
        assert transform["axis_mapping"] == [1, 1, 1]
        assert all(rmse < 0.01 for rmse in transform["confidence_rmse"])

    def test_compute_transform_insufficient_landmarks(self) -> None:
        samples = {"landmarks": []}
        with pytest.raises(ValueError, match="Need at least 3 landmarks"):
            compute_transform(samples)

    def test_compute_transform_exceeds_tolerance(self) -> None:
        samples = {
            "landmarks": [
                {"id": "a", "obj_pos": [0.0, 0.0, 0.0], "memory_pos_samples": [[0.0, 0.0, 0.0]]},
                {"id": "b", "obj_pos": [1.0, 1.0, 1.0], "memory_pos_samples": [[10.0, 10.0, 10.0]]},
                {"id": "c", "obj_pos": [2.0, 2.0, 2.0], "memory_pos_samples": [[999.0, 999.0, 999.0]]},
            ]
        }
        with pytest.raises(ValueError, match="RMSE"):
            compute_transform(samples, validation_tolerance=0.5)

    def test_compute_transform_degenerate_axis(self) -> None:
        samples = {
            "landmarks": [
                {"id": "a", "obj_pos": [0.0, 0.0, 0.0], "memory_pos_samples": [[0.0, 0.0, 0.0]]},
                {"id": "b", "obj_pos": [0.0, 1.0, 2.0], "memory_pos_samples": [[0.0, 10.0, 20.0]]},
                {"id": "c", "obj_pos": [0.0, 2.0, 4.0], "memory_pos_samples": [[0.0, 20.0, 40.0]]},
            ]
        }
        with pytest.raises(ValueError, match="no variance"):
            compute_transform(samples)

    def test_compute_transform_invalid_tolerance(self) -> None:
        samples = _generate_stub_samples()
        with pytest.raises(ValueError, match="validation_tolerance"):
            compute_transform(samples, validation_tolerance=0.0)
        with pytest.raises(ValueError, match="validation_tolerance"):
            compute_transform(samples, validation_tolerance=float("nan"))


class TestTransformIO:
    """Tests for loading and saving transform JSON."""

    def test_save_and_load_transform(self, tmp_path: Path) -> None:
        transform = {
            "scale": [10.0, 10.0, 10.0],
            "offset": [0.0, 5.0, 0.0],
            "axis_mapping": [1, 1, 1],
            "confidence_rmse": [0.01, 0.01, 0.01],
            "validation_tolerance": 0.5,
        }
        path = tmp_path / "transform.json"
        save_transform(transform, path)
        loaded = load_transform(path)
        assert loaded == transform

    def test_load_transform_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_transform(tmp_path / "missing.json")

    def test_save_transform_invalid_data(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="missing required fields"):
            save_transform({"scale": [1, 1, 1]}, tmp_path / "bad.json")  # type: ignore[arg-type]


class TestCalibrationHelpers:
    """Tests for calibration sample helpers."""

    def test_add_landmark_creates_new(self) -> None:
        samples: dict = {"landmarks": []}
        add_landmark(samples, "ep1_origin", (0.0, 0.0, 0.0), (0.0, 5.0, 0.0))
        assert len(samples["landmarks"]) == 1
        assert samples["landmarks"][0]["id"] == "ep1_origin"
        assert samples["landmarks"][0]["memory_pos_samples"] == [[0.0, 5.0, 0.0]]

    def test_add_landmark_appends_samples(self) -> None:
        samples: dict = {"landmarks": []}
        add_landmark(samples, "ep1_origin", (0.0, 0.0, 0.0), (0.0, 5.0, 0.0))
        add_landmark(samples, "ep1_origin", (0.0, 0.0, 0.0), (0.1, 5.0, 0.0))
        assert len(samples["landmarks"]) == 1
        assert len(samples["landmarks"][0]["memory_pos_samples"]) == 2
