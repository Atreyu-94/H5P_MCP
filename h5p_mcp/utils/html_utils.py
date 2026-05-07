from __future__ import annotations


def escape_html(text: str) -> str:
    """
    Escape a string for safe insertion into HTML.

    H5P content parameters often embed HTML strings. We keep it simple and avoid
    external deps since the content is typically short.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def as_paragraph(text: str) -> str:
    """
    Wrap escaped text in a paragraph tag.
    """
    return f"<p>{escape_html(text)}</p>"

