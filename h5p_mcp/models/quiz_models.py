from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def _decode_unicode_escapes(text: str) -> str:
    """
    Decode literal \\uXXXX sequences that were not resolved by the JSON parser.

    This happens when JSON is double-encoded (e.g. the string contains the 6
    characters backslash-u-0-0-e-9 instead of the actual é character).  We
    normalise them here so that validators and generators always work with
    real Unicode text.
    """
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)


class QuizType(str, Enum):
    mcq = "mcq"
    truefalse = "truefalse"
    blanks = "blanks"
    questionset = "questionset"


class QuizBase(BaseModel):
    """
    Canonical, AI-friendly quiz schema used by MCP tools.

    Generators convert these models into H5P content JSON structures.
    """

    type: QuizType
    title: str = Field(min_length=1, max_length=200)


class MCQQuiz(QuizBase):
    type: Literal[QuizType.mcq] = QuizType.mcq
    question: str = Field(min_length=1, max_length=2000)
    choices: list[str] = Field(min_length=2, max_length=12)
    correct_answer: str = Field(min_length=1, max_length=500)
    explanation: str = Field(default="", max_length=4000)

    @field_validator("choices")
    @classmethod
    def _normalize_choices(cls, v: list[str]) -> list[str]:
        cleaned = [c.strip() for c in v if c.strip()]
        if len(cleaned) < 2:
            raise ValueError("choices must contain at least 2 non-empty items")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("choices must not contain duplicates")
        return cleaned

    @model_validator(mode="after")
    def _correct_in_choices(self) -> "MCQQuiz":
        if self.correct_answer.strip() not in self.choices:
            raise ValueError("correct_answer must match one of the choices exactly")
        return self


class TrueFalseQuiz(QuizBase):
    type: Literal[QuizType.truefalse] = QuizType.truefalse
    question: str = Field(min_length=1, max_length=2000)
    correct_answer: bool
    explanation: str = Field(default="", max_length=4000)


class FillBlanksQuiz(QuizBase):
    type: Literal[QuizType.blanks] = QuizType.blanks
    text: str = Field(
        min_length=1,
        max_length=8000,
        description="Text containing H5P.Blanks asterisk-wrapped answers, e.g. 'The capital is *Paris*.'",
    )
    answers: list[str] = Field(min_length=1, max_length=50)

    @field_validator("text", mode="before")
    @classmethod
    def _normalize_text(cls, v: str) -> str:
        """Decode literal \\uXXXX escapes so comparisons always use real characters."""
        return _decode_unicode_escapes(v) if isinstance(v, str) else v

    @field_validator("answers")
    @classmethod
    def _normalize_answers(cls, v: list[str]) -> list[str]:
        cleaned = [_decode_unicode_escapes(a).strip() for a in v if a.strip()]
        if not cleaned:
            raise ValueError("answers must contain at least 1 non-empty item")
        return cleaned

    @model_validator(mode="after")
    def _answers_match_text(self) -> "FillBlanksQuiz":
        extracted = extract_asterisk_answers(self.text)
        if not extracted:
            raise ValueError("text must contain at least one *answer* (asterisk-wrapped)")
        missing = [a for a in self.answers if a not in extracted]
        if missing:
            raise ValueError(
                "answers must be present in text as *answer* tokens. Missing: " + ", ".join(missing)
            )
        return self


class QuestionSetQuiz(QuizBase):
    """
    A mixed quiz container exported as H5P.QuestionSet.

    This enables packaging multiple question *types* into a single .h5p.
    """

    type: Literal[QuizType.questionset] = QuizType.questionset
    intro: str = Field(default="", max_length=4000)
    questions: list[MCQQuiz | TrueFalseQuiz | FillBlanksQuiz] = Field(min_length=1, max_length=50)
    pass_percentage: int = Field(default=50, ge=0, le=100)

    @model_validator(mode="after")
    def _validate_nested(self) -> "QuestionSetQuiz":
        # Ensure nested items are not themselves containers.
        for q in self.questions:
            if getattr(q, "type", None) == QuizType.questionset:
                raise ValueError("Nested questionset is not supported")
        return self


QuizModel = MCQQuiz | TrueFalseQuiz | FillBlanksQuiz | QuestionSetQuiz


class ExportRequest(BaseModel):
    quiz_data: dict[str, Any]
    output_name: str = Field(min_length=1, max_length=120)


def extract_asterisk_answers(text: str) -> list[str]:
    """
    Extract asterisk-wrapped answers from H5P.Blanks text.

    Example: "A *cat* and a *dog*." -> ["cat", "dog"]
    """
    results: list[str] = []
    in_token = False
    buf: list[str] = []
    for ch in text:
        if ch == "*":
            if in_token:
                token = "".join(buf).strip()
                if token:
                    results.append(token)
                buf = []
                in_token = False
            else:
                in_token = True
                buf = []
            continue
        if in_token:
            buf.append(ch)
    return results

