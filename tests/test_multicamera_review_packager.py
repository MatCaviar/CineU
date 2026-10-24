import json

from cineu_demo.multicamera_review_packager import _read_json


def test_read_json_accepts_utf8_bom_manifest_written_by_powershell(tmp_path):
    path = tmp_path / "manifest.json"
    payload = {"schema_version": "cineu.hillside_render_batch.v1", "jobs": []}
    path.write_text(json.dumps(payload), encoding="utf-8-sig")
    assert _read_json(path) == payload
