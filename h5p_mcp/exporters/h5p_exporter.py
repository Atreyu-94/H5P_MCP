from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from h5p_mcp.generators.blanks_generator import BlanksGenerator
from h5p_mcp.generators.mcq_generator import MCQGenerator
from h5p_mcp.generators.questionset_generator import QuestionSetGenerator
from h5p_mcp.generators.truefalse_generator import TrueFalseGenerator
from h5p_mcp.models.quiz_models import FillBlanksQuiz, MCQQuiz, QuestionSetQuiz, QuizModel, QuizType, TrueFalseQuiz
from h5p_mcp.utils.file_utils import resolve_export_dir, safe_filename
from h5p_mcp.lumi_backend import run_lumi


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportResult:
    output_path: Path
    h5p_json: dict[str, Any]
    content_json: dict[str, Any]


class H5PExporter:
    """
    Export canonical quiz models into .h5p (zip) packages.

    The resulting .h5p includes:
    - h5p.json
    - content/content.json and all libraries resolved and packaged by Lumi
    """

    def __init__(self, *, export_dir: str | None = None, templates_dir: str | None = None) -> None:
        self._export_dir = resolve_export_dir(export_dir)
        self._templates_dir = Path(templates_dir) if templates_dir else Path(
            __file__).resolve().parents[1] / "templates"

        self._mcq = MCQGenerator(self._templates_dir / "mcq" / "content.json")
        self._tf = TrueFalseGenerator(
            self._templates_dir / "truefalse" / "content.json")
        self._blanks = BlanksGenerator(
            self._templates_dir / "blanks" / "content.json")
        self._qs = QuestionSetGenerator(
            template_path=self._templates_dir / "questionset" / "content.json",
            templates_dir=self._templates_dir,
        )

    def export(self, quiz: QuizModel, *, output_name: str) -> ExportResult:
        out_stem = safe_filename(output_name)
        out_path = self._export_dir / f"{out_stem}.h5p"

        content_json = self._generate_content_json(quiz)

        logger.info("Exporting quiz type=%s title=%s -> %s",
                    quiz.type.value, quiz.title, out_path)

        if out_path.exists():
            raise FileExistsError(f"Export already exists; choose a new output_name: {out_path}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".lumi-", dir=out_path.parent) as work:
            package = Path(work) / "activity.h5p"
            result = run_lumi("export", content=content_json, title=quiz.title,
                              main_library=_library_for_type(quiz.type), path=str(package))
            # Same-filesystem, exclusive publication: no partial output or overwrite,
            # including two concurrent exports with the same output name.
            os.link(package, out_path)
        return ExportResult(output_path=out_path, h5p_json=result["h5p_json"], content_json=result["content_json"])

    def _generate_content_json(self, quiz: QuizModel) -> dict[str, Any]:
        if isinstance(quiz, MCQQuiz):
            return self._mcq.generate_content_json(quiz)
        if isinstance(quiz, TrueFalseQuiz):
            return self._tf.generate_content_json(quiz)
        if isinstance(quiz, FillBlanksQuiz):
            return self._blanks.generate_content_json(quiz)
        if isinstance(quiz, QuestionSetQuiz):
            return self._qs.generate_content_json(quiz)
        raise ValueError(f"Unsupported quiz model: {type(quiz).__name__}")

def _library_for_type(qtype: QuizType) -> str:
    # Version resolution belongs to Lumi's installed library catalog.
    if qtype == QuizType.mcq:
        return "H5P.MultiChoice"
    if qtype == QuizType.truefalse:
        return "H5P.TrueFalse"
    if qtype == QuizType.blanks:
        return "H5P.Blanks"
    if qtype == QuizType.questionset:
        return "H5P.QuestionSet"
    raise ValueError(f"Unsupported QuizType: {qtype}")
