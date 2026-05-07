from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedMarkdownQuiz:
    quiz_data: dict[str, Any]


_HEADER_RE = re.compile(r"^\s*###\s*(?P<type>MCQ|TF|TRUEFALSE|BLANKS)\s*:\s*(?P<title>.+?)\s*$", re.IGNORECASE)
_Q_RE = re.compile(r"^\s*(Q|Question)\s*:\s*(?P<q>.+?)\s*$", re.IGNORECASE)
_A_RE = re.compile(r"^\s*(A|Answer)\s*:\s*(?P<a>true|false)\s*$", re.IGNORECASE)
_TEXT_RE = re.compile(r"^\s*(Text)\s*:\s*(?P<t>.+?)\s*$", re.IGNORECASE)
_ANSWERS_RE = re.compile(r"^\s*(Answers)\s*:\s*(?P<a>.+?)\s*$", re.IGNORECASE)
_EXPL_RE = re.compile(r"^\s*(Explanation)\s*:\s*(?P<e>.+?)\s*$", re.IGNORECASE)
_CHOICE_RE = re.compile(r"^\s*-\s*\[(?P<mark>[ xX])\]\s*(?P<choice>.+?)\s*$")


def parse_markdown_quizzes(markdown: str) -> list[dict[str, Any]]:
    """
    Parse a simple markdown format into canonical quiz dicts.

    Supported blocks:

    ### MCQ: Title
    Q: Question text
    - [ ] choice
    - [x] correct choice
    Explanation: optional explanation

    ### TF: Title
    Q: Question text
    A: true|false
    Explanation: optional explanation

    ### Blanks: Title
    Text: The capital is *Paris*.
    Answers: Paris
    """
    lines = markdown.replace("\r\n", "\n").split("\n")
    i = 0
    out: list[dict[str, Any]] = []

    while i < len(lines):
        m = _HEADER_RE.match(lines[i] or "")
        if not m:
            i += 1
            continue

        qtype_raw = (m.group("type") or "").strip().lower()
        title = (m.group("title") or "").strip()
        i += 1

        block_lines: list[str] = []
        while i < len(lines) and not _HEADER_RE.match(lines[i] or ""):
            block_lines.append(lines[i])
            i += 1

        if qtype_raw == "mcq":
            out.append(_parse_mcq_block(title, block_lines))
        elif qtype_raw in {"tf", "truefalse"}:
            out.append(_parse_tf_block(title, block_lines))
        elif qtype_raw == "blanks":
            out.append(_parse_blanks_block(title, block_lines))
        else:
            raise ValueError(f"Unsupported quiz type in header: {m.group('type')}")

    return out


def _parse_mcq_block(title: str, block_lines: list[str]) -> dict[str, Any]:
    question = ""
    explanation = ""
    choices: list[str] = []
    correct: str | None = None

    for line in block_lines:
        if not question:
            qm = _Q_RE.match(line or "")
            if qm:
                question = qm.group("q").strip()
                continue

        cm = _CHOICE_RE.match(line or "")
        if cm:
            choice = cm.group("choice").strip()
            choices.append(choice)
            if cm.group("mark").strip().lower() == "x":
                correct = choice
            continue

        em = _EXPL_RE.match(line or "")
        if em:
            explanation = em.group("e").strip()
            continue

    if not question:
        raise ValueError(f"MCQ '{title}' missing 'Q:' line")
    if len(choices) < 2:
        raise ValueError(f"MCQ '{title}' must have at least 2 choices")
    if correct is None:
        raise ValueError(f"MCQ '{title}' must mark one choice as correct using - [x]")

    return {
        "type": "mcq",
        "title": title,
        "question": question,
        "choices": choices,
        "correct_answer": correct,
        "explanation": explanation,
    }


def _parse_tf_block(title: str, block_lines: list[str]) -> dict[str, Any]:
    question = ""
    answer: bool | None = None
    explanation = ""

    for line in block_lines:
        if not question:
            qm = _Q_RE.match(line or "")
            if qm:
                question = qm.group("q").strip()
                continue

        am = _A_RE.match(line or "")
        if am:
            answer = am.group("a").strip().lower() == "true"
            continue

        em = _EXPL_RE.match(line or "")
        if em:
            explanation = em.group("e").strip()
            continue

    if not question:
        raise ValueError(f"TF '{title}' missing 'Q:' line")
    if answer is None:
        raise ValueError(f"TF '{title}' missing 'A: true|false' line")

    return {"type": "truefalse", "title": title, "question": question, "correct_answer": answer, "explanation": explanation}


def _parse_blanks_block(title: str, block_lines: list[str]) -> dict[str, Any]:
    text = ""
    answers: list[str] = []

    for line in block_lines:
        tm = _TEXT_RE.match(line or "")
        if tm:
            text = tm.group("t").strip()
            continue

        am = _ANSWERS_RE.match(line or "")
        if am:
            raw = am.group("a").strip()
            answers = [p.strip() for p in re.split(r"[,\n]+", raw) if p.strip()]
            continue

    if not text:
        raise ValueError(f"Blanks '{title}' missing 'Text:' line")
    if not answers:
        raise ValueError(f"Blanks '{title}' missing 'Answers:' line")

    return {"type": "blanks", "title": title, "text": text, "answers": answers}

