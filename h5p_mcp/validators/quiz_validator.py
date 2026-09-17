from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from pydantic import TypeAdapter, ValidationError

from h5p_mcp.models.quiz_models import QuizModel, QuizType
from h5p_mcp.lumi_backend import run_lumi

# TypeAdapter is required for validating against a union type alias (X | Y | Z).
# Plain union aliases don't expose .model_validate() the way BaseModel subclasses do.
_QUIZ_ADAPTER: TypeAdapter[QuizModel] = TypeAdapter(QuizModel)


@dataclass(frozen=True)
class H5PValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]


def validate_quiz_data(quiz_data: dict[str, Any]) -> QuizModel:
    """
    Validate and coerce the canonical quiz schema using Pydantic.
    """
    try:
        return _QUIZ_ADAPTER.validate_python(quiz_data)
    except ValidationError as e:
        raise ValueError(e.json(indent=2)) from e


def validate_h5p_package(path: str | Path) -> H5PValidationResult:
    """
    Validate JSON roots, then import with Lumi into empty temporary storage.

    Requires a self-contained package. Import validation is not playback testing.
    """
    p = Path(path)
    errors: list[str] = []
    warnings: list[str] = []

    if not p.exists():
        return H5PValidationResult(ok=False, errors=[f"File does not exist: {p}"], warnings=[])
    if p.suffix.lower() != ".h5p":
        warnings.append("File does not have .h5p extension (still may be a valid zip).")

    try:
        with ZipFile(p, "r") as z:
            names = set(z.namelist())
            if "h5p.json" not in names:
                errors.append("Missing 'h5p.json' at zip root.")
            if "content/content.json" not in names:
                errors.append("Missing 'content/content.json'.")

            h5p_json = _read_json_from_zip(z, "h5p.json", errors)
            content_json = _read_json_from_zip(z, "content/content.json", errors)

            if isinstance(h5p_json, dict):
                if "mainLibrary" not in h5p_json:
                    errors.append("h5p.json missing 'mainLibrary'.")
                if "preloadedDependencies" not in h5p_json:
                    errors.append("h5p.json missing 'preloadedDependencies'.")
                else:
                    deps = h5p_json.get("preloadedDependencies")
                    if not isinstance(deps, list) or not deps:
                        errors.append("'preloadedDependencies' must be a non-empty list.")

            if not isinstance(h5p_json, dict):
                errors.append("h5p.json must contain a JSON object.")
            if not isinstance(content_json, dict):
                errors.append("content/content.json must contain a JSON object.")

            if isinstance(h5p_json, dict) and isinstance(content_json, dict):
                main = h5p_json.get("mainLibrary")
                if main and isinstance(main, str):
                    expected = {
                        "H5P.MultiChoice": QuizType.mcq,
                        "H5P.TrueFalse": QuizType.truefalse,
                        "H5P.Blanks": QuizType.blanks,
                        "H5P.QuestionSet": QuizType.questionset,
                    }
                    if main not in expected:
                        warnings.append(f"Unknown mainLibrary '{main}'. Package may still import if installed.")

    except Exception as e:  # noqa: BLE001
        errors.append(f"Failed to read zip: {e}")

    if not errors:
        try:
            report = run_lumi("validate", path=str(p.resolve()))
            errors.extend(report.get("errors", []))
            warnings.extend(report.get("warnings", []))
        except RuntimeError as error:
            errors.append(str(error))
    return H5PValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


def _read_json_from_zip(z: ZipFile, name: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        raw = z.read(name)
    except KeyError:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        errors.append(f"Invalid JSON in '{name}': {e}")
        return None

