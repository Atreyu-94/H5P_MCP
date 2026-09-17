"""Regression checks against the installed, pinned Lumi backend."""
import hashlib
import json
from zipfile import ZipFile

import pytest

from h5p_mcp.exporters.h5p_exporter import H5PExporter
from h5p_mcp.lumi_backend import SOURCE, run_lumi
from h5p_mcp.models.quiz_models import TrueFalseQuiz
from h5p_mcp.validators.quiz_validator import validate_h5p_package


def test_pinned_backend_identity():
    provenance = json.loads((SOURCE / "provenance.json").read_text())
    assert provenance["commit"] == "efcfeebc6d7ae349f4fb708e2f44284151f77558"
    assert hashlib.sha256((SOURCE / provenance["archive"]).read_bytes()).hexdigest() == provenance["sha256"]
    assert run_lumi("catalog")["core"] == "1.28.0"


@pytest.fixture
def package(tmp_path):
    return H5PExporter(export_dir=str(tmp_path)).export(
        TrueFalseQuiz(title="Core compatibility", question="True?", correct_answer=True),
        output_name="original",
    ).output_path


@pytest.mark.parametrize("minor,expected", [(28, True), (29, False)])
def test_required_core_api(package, minor, expected):
    """Exercise the importer's actual Core gate, not just its reported version."""
    target = package.with_name(f"requires-1-{minor}.h5p")
    with ZipFile(package) as source, ZipFile(target, "w") as output:
        for name in source.namelist():
            data = source.read(name)
            if name.startswith("H5P.TrueFalse-") and name.endswith("/library.json"):
                library = json.loads(data)
                library["coreApi"] = {"majorVersion": 1, "minorVersion": minor}
                data = json.dumps(library).encode()
            output.writestr(name, data)
    report = validate_h5p_package(target)
    assert report.ok is expected, report.errors
    if not expected:
        assert any("api-version" in error.lower() or "core" in error.lower() for error in report.errors)


def test_missing_libraries_rejected(package):
    target = package.with_name("content-only.h5p")
    with ZipFile(package) as source, ZipFile(target, "w") as output:
        for name in ("h5p.json", "content/content.json"):
            output.writestr(name, source.read(name))
    assert not validate_h5p_package(target).ok


def test_existing_export_preserved(package):
    before = package.read_bytes()
    with pytest.raises(FileExistsError):
        H5PExporter(export_dir=str(package.parent)).export(
            TrueFalseQuiz(title="Replacement", question="False?", correct_answer=False),
            output_name=package.stem,
        )
    assert package.read_bytes() == before


@pytest.mark.parametrize("invalid", [None, [], "text"])
def test_non_object_json_rejected(tmp_path, invalid):
    target = tmp_path / "invalid.h5p"
    with ZipFile(target, "w") as output:
        output.writestr("h5p.json", json.dumps(invalid))
        output.writestr("content/content.json", "{}")
    report = validate_h5p_package(target)
    assert not report.ok
    assert any("JSON object" in error for error in report.errors)
