from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from h5p_mcp.models.quiz_models import MCQQuiz
from h5p_mcp.utils.html_utils import as_paragraph


class MCQGenerator:
    """
    Convert an MCQQuiz into H5P.MultiChoice content.json.

    H5P.MultiChoice expects the content.json root to have:
      question  (HTML string)
      answers   (list of answer objects)
      behaviour, UI, overallFeedback — all at root level.
    """

    def __init__(self, template_path: Path) -> None:
        self._template_path = template_path

    def generate_content_json(self, quiz: MCQQuiz) -> dict[str, Any]:
        template = json.loads(self._template_path.read_text(encoding="utf-8"))

        # Root-level question string (HTML).
        template["question"] = as_paragraph(quiz.question)

        correct = quiz.correct_answer.strip()
        answers = []
        for choice in quiz.choices:
            is_correct = choice == correct
            feedback = as_paragraph(quiz.explanation) if is_correct and quiz.explanation else ""
            answers.append(
                {
                    "text": as_paragraph(choice),
                    "correct": is_correct,
                    "tipsAndFeedback": {
                        "tip": "",
                        "chosenFeedback": feedback,
                        "notChosenFeedback": "",
                    },
                }
            )

        # Root-level answers and feedback.
        template["answers"] = answers
        template["overallFeedback"] = [
            {
                "from": 0,
                "to": 100,
                "feedback": as_paragraph(quiz.explanation) if quiz.explanation else "",
            }
        ]

        # UX defaults — keep randomised order, single correct answer.
        template.setdefault("behaviour", {})
        template["behaviour"].setdefault("randomAnswers", True)
        template["behaviour"].setdefault("showSolutionsRequiresInput", True)

        return template
