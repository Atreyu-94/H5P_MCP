from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from h5p_mcp.models.quiz_models import FillBlanksQuiz
from h5p_mcp.utils.html_utils import escape_html


def _escape_html_preserve_asterisk(text: str) -> str:
    """Escape HTML entities but keep asterisk markers intact for H5P.Blanks."""
    # Split on asterisks, escape only the non-blank segments, then reassemble.
    parts = text.split("*")
    escaped: list[str] = []
    for i, part in enumerate(parts):
        # Even-indexed parts are plain text; odd-indexed parts are blank answers.
        if i % 2 == 0:
            escaped.append(escape_html(part))
        else:
            escaped.append(f"*{part}*")
    return "".join(escaped)


class BlanksGenerator:
    """
    Convert a FillBlanksQuiz into H5P.Blanks content.json.
    """

    def __init__(self, template_path: Path) -> None:
        self._template_path = template_path

    def generate_content_json(self, quiz: FillBlanksQuiz) -> dict[str, Any]:
        template = json.loads(self._template_path.read_text(encoding="utf-8"))

        template["title"] = quiz.title
        # H5P.Blanks expects HTML string; answers are asterisk-wrapped in text.
        template["text"] = f"<p>{_escape_html_preserve_asterisk(quiz.text)}</p>"

        # Better UX defaults for language learning / practice questions.
        template.setdefault("behaviour", {})
        template["behaviour"].setdefault("caseSensitive", False)
        template["behaviour"].setdefault("enableSolutionsButton", True)

        return template


