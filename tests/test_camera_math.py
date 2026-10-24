from cineu_demo.camera_math import compute_hitchcock_zoom_keys


def test_hitchcock_zoom_focal_distance_coupling():
    keys = compute_hitchcock_zoom_keys([0, 0, 100], [0, -1, 0], 900, 300, 35, 0, 100, num_keys=4)
    assert len(keys) == 4
    assert keys[0]["focal_length"] == 35
    assert abs(keys[-1]["focal_length"] - 35 * 300 / 900) < 1e-6
    for k in keys:
        assert "location" in k and "rotation" in k and "focus_distance" in k
