from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from h5p_mcp.models.quiz_models import TrueFalseQuiz
from h5p_mcp.utils.html_utils import as_paragraph


class TrueFalseGenerator:
    """
    Convert a TrueFalseQuiz into H5P.TrueFalse content.json.
    """

    def __init__(self, template_path: Path) -> None:
        self._template_path = template_path

    def generate_content_json(self, quiz: TrueFalseQuiz) -> dict[str, Any]:
        template = json.loads(self._template_path.read_text(encoding="utf-8"))

        template["title"] = quiz.title
        template["question"] = as_paragraph(quiz.question)
        template["correct"] = "true" if quiz.correct_answer else "false"

        if quiz.explanation:
            template["feedback"] = {
                "correct": as_paragraph(quiz.explanation),
                "wrong": as_paragraph(quiz.explanation),
            }
        else:
            template["feedback"] = {"correct": "", "wrong": ""}

        return template


