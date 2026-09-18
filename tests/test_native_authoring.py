"""Real generic authoring, negative semantic cases and embedded assets."""
import base64
import copy
import json
from zipfile import ZipFile

import pytest
from pydantic import ValidationError

from h5p_mcp.models.activity import Activity
from h5p_mcp.server import create_h5p_activity, export_h5p_batch
from h5p_mcp.exporters.h5p_exporter import H5PExporter
from h5p_mcp.validators.quiz_validator import validate_h5p_package


TF = {"library": "H5P.TrueFalse 1.8", "params": {"question": "<p>True?</p>", "correct": "true"}}
ACCORDION = {"library": "H5P.Accordion 1.0", "params": {"panels": [
    {"title": "Evaporación", "content": {"library": "H5P.AdvancedText 1.1", "params": {"text": "<p>Líquido a gas.</p>"}}}]}}
EXAMPLES = [TF, ACCORDION,
    {"library": "H5P.MultiChoice 1.16", "params": {"question": "<p>Two?</p>", "answers": [
        {"text": "<p>2</p>", "correct": True}, {"text": "<p>3</p>", "correct": False}]}},
    {"library": "H5P.Blanks 1.14", "params": {"text": "<p>Complete.</p>", "questions": ["<p>Una *palabra*.</p>"]}},
    {"library": "H5P.QuestionSet 1.21", "params": {"introPage": {"showIntroPage": False},
        "endGame": {"showAnimations": False, "skippable": False}, "questions": [TF]}}]


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["library"] for e in EXAMPLES])
def test_native_export_roundtrip(tmp_path, example):
    original = copy.deepcopy(example)
    prepared = create_h5p_activity(title="Actividad", language="es", **example)
    assert prepared["ok"], prepared["errors"]
    assert example == original
    result = H5PExporter(export_dir=str(tmp_path)).export(Activity.model_validate(prepared["activity"]), output_name="native")
    report = validate_h5p_package(result.output_path)
    assert report.ok, report.errors
    with ZipFile(result.output_path) as archive:
        manifest = json.loads(archive.read("h5p.json"))
        assert manifest["mainLibrary"] == example["library"].split()[0]
        assert manifest["language"] == "es"
        assert any(name.endswith("/library.json") for name in archive.namelist())


@pytest.mark.parametrize("library,params,expected", [
    ("H5P.TrueFalse 1.8", {}, "params.question"),
    ("H5P.TrueFalse 1.8", {"question": "Q", "correct": True}, "invalid select"),
    ("H5P.TrueFalse 1.8", {"question": "Q", "surprise": 1}, "unknown field"),
    ("H5P.TrueFalse 99.99", {"question": "Q"}, "unavailable"),
    ("H5P.Accordion 1.0", {"panels": []}, "minimum 1"),
    ("H5P.Accordion 1.0", {"panels": "text"}, "expected list"),
    ("H5P.Accordion 1.0", {"panels": [{"title": "T", "content": TF}]}, "allowed exact version"),
    ("H5P.Accordion 1.0", {"panels": [{"title": "T", "content": {"library": "H5P.AdvancedText 1.1", "params": {}}}]}, "params.text"),
    ("H5P.QuestionSet 1.21", {"passPercentage": 101}, "maximum 100"),
])
def test_semantic_errors_block_export(tmp_path, library, params, expected):
    report = create_h5p_activity("Invalid", library, params)
    assert not report["ok"]
    assert any(expected in error for error in report["errors"]), report
    with pytest.raises(RuntimeError):
        H5PExporter(export_dir=str(tmp_path)).export(Activity(title="Invalid", library=library, params=params), output_name="invalid")
    assert not (tmp_path / "invalid.h5p").exists()


@pytest.mark.parametrize("library", ["H5P.TrueFalse", "../bad 1.0", "H5P.TrueFalse 1.8.0"])
def test_exact_version_required(library):
    with pytest.raises(ValidationError):
        Activity(title="T", library=library, params={})


def test_legacy_contract_rejected():
    with pytest.raises(ValidationError):
        Activity.model_validate({"type": "truefalse", "title": "T", "question": "Q", "correct_answer": True})


def test_nested_local_image_is_packaged(tmp_path):
    picture = tmp_path / "source.png"
    raw = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a0ioAAAAASUVORK5CYII=")
    picture.write_bytes(raw)
    params = copy.deepcopy(TF["params"])
    params["media"] = {"type": {"library": "H5P.Image 1.1", "params": {
        "file": {"path": "asset:diagram", "mime": "image/png"}, "alt": "Diagram"}}}
    report = create_h5p_activity("With image", TF["library"], params, assets={"diagram": str(picture)})
    assert report["ok"], report
    result = H5PExporter(export_dir=str(tmp_path)).export(Activity.model_validate(report["activity"]), output_name="image")
    with ZipFile(result.output_path) as archive:
        body = json.loads(archive.read("content/content.json"))
        media = body["media"]["type"]["params"]["file"]
        assert media["width"] == 1
        assert archive.read("content/" + media["path"]) == raw
    assert picture.read_bytes() == raw
    assert validate_h5p_package(result.output_path).ok


def test_missing_media_is_not_silently_discarded():
    params = copy.deepcopy(TF["params"])
    params["media"] = {"type": {"library": "H5P.Image 1.1", "params": {"file": {"path": "missing.png"}, "alt": "T"}}}
    report = create_h5p_activity("Missing", TF["library"], params)
    assert not report["ok"]
    assert any("asset:<id>" in error for error in report["errors"])


def test_batch_reports_partial_success(tmp_path, monkeypatch):
    monkeypatch.setenv("H5P_MCP_EXPORT_DIR", str(tmp_path))
    report = export_h5p_batch([{"title": "Valid", **TF}, {"title": "Invalid", "library": TF["library"], "params": {}}])
    assert report["count"] == 2 and report["succeeded"] == 1
    assert report["results"][0]["ok"] and not report["results"][1]["ok"]
