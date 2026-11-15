"""English UI strings.

The application is now English-only.  ``t()`` is kept as a tiny indirection so
existing call sites do not need to change and so a translation layer can be
added later without touching every page.
"""

from __future__ import annotations


def t(text: str) -> str:
    """Return the English UI string for ``text``."""

    return text
