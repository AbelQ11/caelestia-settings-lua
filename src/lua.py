"""Small, dependency-free Lua reader/writer.

The app never *executes* Lua.  It only needs to understand the configuration
tables Hyprland and Caelestia use, and to rewrite specific values without
touching the rest of the file.  This module provides:

* :func:`parse_table` / :func:`iter_calls` for reading ``hl.monitor({...})``,
  ``hl.workspace_rule({...})``, ``hl.window_rule({...})``, ``hl.bind(...)``
  and ``return { ... }`` variable tables;
* :func:`set_table_values` / :func:`remove_table_values` for surgically
  updating scalar entries in ``variables.lua`` / ``hypr-vars.lua``;
* :func:`replace_managed_block` for the marked blocks the app owns in
  ``hypr-user.lua``.

Everything is string-in / string-out so it can be unit-tested without any
files, and so a malformed file raises instead of silently corrupting data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

__all__ = [
    "LuaCall",
    "LuaParseError",
    "format_value",
    "iter_calls",
    "managed_block",
    "parse_table",
    "read_table_values",
    "remove_managed_block",
    "remove_table_values",
    "replace_managed_block",
    "set_table_values",
    "strip_managed_block",
    "lua_string",
]


class LuaParseError(ValueError):
    """Raised when a Lua snippet cannot be understood."""


@dataclass(frozen=True)
class LuaCall:
    name: str
    table: Any
    start: int
    end: int
    args: str


# ---------------------------------------------------------------------------
# Low-level scanning
# ---------------------------------------------------------------------------


def _skip_ws(text: str, i: int) -> int:
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif text.startswith("--", i):
            if text.startswith("--[[", i):
                close = text.find("]]", i + 4)
                i = n if close < 0 else close + 2
            else:
                newline = text.find("\n", i)
                i = n if newline < 0 else newline + 1
            continue
        else:
            break
    return i


def _find_matching(text: str, start: int, opener: str = "{", closer: str = "}") -> int:
    if start >= len(text) or text[start] != opener:
        raise LuaParseError(f"expected {opener!r} at offset {start}")
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            i = _skip_string(text, i)
            continue
        if text.startswith("--", i):
            i = _skip_ws(text, i)
            continue
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise LuaParseError(f"unbalanced {opener!r} starting at offset {start}")


def _skip_string(text: str, i: int) -> int:
    quote = text[i]
    i += 1
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == quote:
            return i + 1
        i += 1
    raise LuaParseError("unterminated string")


def _parse_string(text: str, i: int) -> tuple[str, int]:
    quote = text[i]
    i += 1
    out: list[str] = []
    n = len(text)
    escapes = {
        "n": "\n",
        "t": "\t",
        "r": "\r",
        "\\": "\\",
        '"': '"',
        "'": "'",
        "0": "\0",
    }
    while i < n:
        c = text[i]
        if c == "\\":
            nxt = text[i + 1] if i + 1 < n else ""
            out.append(escapes.get(nxt, nxt))
            i += 2
            continue
        if c == quote:
            return "".join(out), i + 1
        out.append(c)
        i += 1
    raise LuaParseError("unterminated string")


_NUMBER_RE = re.compile(r"[-+]?(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d*)?(?:[eE][-+]?\d+)?|\.\d+)")


def _parse_number(text: str, i: int) -> tuple[int | float, int]:
    match = _NUMBER_RE.match(text, i)
    if not match:
        raise LuaParseError(f"invalid number at offset {i}")
    raw = match.group(0)
    value: int | float
    if raw.lower().startswith(("0x", "-0x", "+0x")):
        value = int(raw, 16)
    elif any(ch in raw for ch in ".eE"):
        value = float(raw)
    else:
        value = int(raw)
    return value, match.end()


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _parse_identifier(text: str, i: int) -> tuple[str, int]:
    match = _IDENT_RE.match(text, i)
    if not match:
        raise LuaParseError(f"invalid identifier at offset {i}")
    return match.group(0), match.end()


def _parse_raw_expression(text: str, i: int) -> tuple[str, int]:
    """Consume a Lua expression up to the next top-level ``,`` or ``}``."""

    start = i
    depth = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            i = _skip_string(text, i)
            continue
        if text.startswith("--", i):
            newline = text.find("\n", i)
            i = n if newline < 0 else newline + 1
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0 and c == "}":
                break
            depth -= 1
        elif c == "," and depth == 0:
            break
        i += 1
    return text[start:i].strip(), i


def _parse_value(text: str, i: int) -> tuple[Any, int, int, int]:
    """Return ``(value, end, value_start, value_end)``."""

    i = _skip_ws(text, i)
    value_start = i
    if i >= len(text):
        raise LuaParseError("unexpected end of input")
    c = text[i]

    if c in "\"'":
        value, i = _parse_string(text, i)
        after = _skip_ws(text, i)
        if text.startswith("..", after):
            # String concatenation (e.g. colour expressions): keep the source.
            raw, end = _parse_raw_expression(text, value_start)
            return raw, end, value_start, end
        return value, i, value_start, i
    if c == "{":
        value, i = _parse_table_internal(text, i)
        return value, i, value_start, i
    if c.isdigit() or (c in "+-." and i + 1 < len(text) and text[i + 1].isdigit()):
        value, i = _parse_number(text, i)
        return value, i, value_start, i

    ident_match = _IDENT_RE.match(text, i)
    if ident_match:
        ident = ident_match.group(0)
        if ident in ("true", "false", "nil"):
            i = ident_match.end()
            return {"true": True, "false": False, "nil": None}[ident], i, value_start, i

    raw, i = _parse_raw_expression(text, i)
    if not raw:
        raise LuaParseError(f"missing value at offset {value_start}")
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        # A quoted string followed by a concatenation is kept raw on purpose;
        # a plain quoted string was handled above.
        return raw[1:-1], i, value_start, i
    return raw, i, value_start, i


class _TableResult:
    __slots__ = ("fields", "spans", "array", "end", "open")

    def __init__(self) -> None:
        self.fields: dict[str, Any] = {}
        self.spans: dict[str, tuple[int, int]] = {}
        self.array: list[Any] = []
        self.end: int = 0
        self.open: int = 0


def _parse_table_result(text: str, i: int) -> _TableResult:
    i = _skip_ws(text, i)
    if i >= len(text) or text[i] != "{":
        raise LuaParseError(f"expected '{{' at offset {i}")
    result = _TableResult()
    result.open = i
    i += 1
    n = len(text)

    while True:
        i = _skip_ws(text, i)
        if i >= n:
            raise LuaParseError("unterminated table")
        if text[i] == "}":
            result.end = i + 1
            return result
        if text[i] == ",":
            i += 1
            continue

        # key = value or positional value
        key: str | None = None
        c = text[i]
        if c in "\"'":
            candidate, after = _parse_string(text, i)
            after = _skip_ws(text, after)
            if after < n and text[after] == "=":
                key = candidate
                i = after + 1
        elif c == "[":
            # [expr] = value
            close = _find_matching(text, i, "[", "]")
            inner = text[i + 1:close].strip()
            if len(inner) >= 2 and inner[0] == inner[-1] and inner[0] in "\"'":
                inner = inner[1:-1]
            after = _skip_ws(text, close + 1)
            if after < n and text[after] == "=":
                key = inner
                i = after + 1
        else:
            ident_match = _IDENT_RE.match(text, i)
            if ident_match:
                after = _skip_ws(text, ident_match.end())
                if after < n and text[after] == "=":
                    key = ident_match.group(0)
                    i = after + 1

        if key is None:
            value, i, _vs, _ve = _parse_value(text, i)
            result.array.append(value)
            continue

        value, i, vs, ve = _parse_value(text, i)
        result.fields[key] = value
        result.spans[key] = (vs, ve)

        i = _skip_ws(text, i)
        if i < n and text[i] == ",":
            i += 1


def _parse_table_internal(text: str, i: int) -> tuple[Any, int]:
    result = _parse_table_result(text, i)
    if result.array and not result.fields:
        return result.array, result.end
    if result.array:
        data = dict(result.fields)
        data["__array__"] = result.array
        return data, result.end
    return result.fields, result.end


def parse_table(text: str, start: int = 0) -> tuple[Any, int]:
    """Parse a Lua table literal starting at ``start``.

    Returns ``(value, end_offset)``.  A pure array table becomes a Python
    ``list``; a mixed table becomes a dict with an extra ``__array__`` key.
    """

    return _parse_table_internal(text, start)


def _find_call_end(text: str, open_paren: int) -> int:
    return _find_matching(text, open_paren, "(", ")")


_CALL_RE = re.compile(r"(?<![\w.])((?:[A-Za-z_][A-Za-z0-9_]*\.)*[A-Za-z_][A-Za-z0-9_]*)\s*\(")


def iter_calls(text: str, names: Iterable[str] | None = None) -> list[LuaCall]:
    """Find every ``namespace.func(...)`` call with a single table argument."""

    wanted = set(names) if names is not None else None
    calls: list[LuaCall] = []
    for match in _CALL_RE.finditer(text):
        name = match.group(1)
        short = name.rsplit(".", 1)[-1]
        if wanted is not None and name not in wanted and short not in wanted:
            continue
        # Ignore calls that are commented out on their own line.
        line_start = text.rfind("\n", 0, match.start()) + 1
        if "--" in text[line_start:match.start()]:
            continue
        open_paren = text.find("(", match.start())
        try:
            close_paren = _find_call_end(text, open_paren)
        except LuaParseError:
            continue
        args = text[open_paren + 1:close_paren]
        first = _skip_ws(args, 0)
        table: Any = None
        if first < len(args) and args[first] == "{":
            try:
                table, _ = parse_table(args, first)
            except LuaParseError:
                table = None
        calls.append(
            LuaCall(
                name=name,
                table=table,
                start=match.start(),
                end=close_paren + 1,
                args=args,
            )
        )
    return calls


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def lua_string(value: str) -> str:
    escaped = (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


_LUA_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def format_key(key: str) -> str:
    """Render a table key, using bracket syntax when needed."""

    if _LUA_KEY_RE.match(key):
        return key
    return f"[{lua_string(key)}]"


def format_value(value: Any, indent: int = 0) -> str:
    """Render a Python value as a Lua literal (inline for scalars/lists)."""

    pad = " " * indent
    inner_pad = " " * (indent + 4)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "nil"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return repr(value)
    if isinstance(value, str):
        return lua_string(value)
    if isinstance(value, (list, tuple)):
        if not value:
            return "{}"
        simple = all(isinstance(v, (str, int, float, bool)) for v in value)
        if simple:
            return "{ " + ", ".join(format_value(v) for v in value) + " }"
        items = ",\n".join(inner_pad + format_value(v, indent + 4) for v in value)
        return "{\n" + items + "\n" + pad + "}"
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = ",\n".join(
            f"{inner_pad}{format_key(key)} = {format_value(val, indent + 4)}"
            for key, val in value.items()
            if key != "__array__"
        )
        array = value.get("__array__")
        if array:
            extra = ",\n".join(inner_pad + format_value(v, indent + 4) for v in array)
            items = f"{items},\n{extra}" if items else extra
        return "{\n" + items + "\n" + pad + "}"
    return lua_string(str(value))


# ---------------------------------------------------------------------------
# Managed blocks
# ---------------------------------------------------------------------------

BEGIN_TEMPLATE = "-- BEGIN Caelestia Settings: {block_id}"
END_TEMPLATE = "-- END Caelestia Settings: {block_id}"


def managed_block(block_id: str, body: str) -> str:
    body = body.rstrip()
    return f"{BEGIN_TEMPLATE.format(block_id=block_id)}\n{body}\n{END_TEMPLATE.format(block_id=block_id)}"


def _block_regex(block_id: str) -> re.Pattern[str]:
    begin = re.escape(BEGIN_TEMPLATE.format(block_id=block_id))
    end = re.escape(END_TEMPLATE.format(block_id=block_id))
    return re.compile(rf"(?ms)^[ \t]*{begin}.*?^[ \t]*{end}[ \t]*(?:\n|$)")


def replace_managed_block(
    text: str,
    block_id: str,
    body: str,
    *,
    anchor: str | None = r"(?m)^[ \t]*return\s+config\b",
) -> str:
    """Replace (or insert) a marked block, keeping the rest of the file."""

    block = managed_block(block_id, body)
    pattern = _block_regex(block_id)
    if pattern.search(text):
        return pattern.sub(lambda _m: block + "\n", text, count=1)

    if anchor:
        match = re.search(anchor, text)
        if not match:
            # Files created by older helpers may end with `return {}` instead
            # of `return config`; never write an unreachable block after it.
            match = re.search(r"(?m)^[ \t]*return\b", text)
        if match:
            head = text[: match.start()].rstrip()
            tail = text[match.start():]
            prefix = head + "\n\n" if head else ""
            return f"{prefix}{block}\n\n{tail}"

    stripped = text.rstrip()
    return f"{stripped}\n\n{block}\n" if stripped else f"{block}\n"


def remove_managed_block(text: str, block_id: str) -> str:
    match = _block_regex(block_id).search(text)
    if not match:
        return text
    before = text[: match.start()].rstrip()
    after = text[match.end():].lstrip("\n")
    if before and after:
        return f"{before}\n\n{after}"
    return before or after


def strip_managed_block(text: str, block_id: str) -> str:
    """Return only the body of a managed block (or an empty string)."""

    pattern = _block_regex(block_id)
    match = pattern.search(text)
    if not match:
        return ""
    block = match.group(0)
    lines = block.splitlines()
    if len(lines) >= 2:
        return "\n".join(lines[1:-1])
    return ""


# ---------------------------------------------------------------------------
# Updating `return { ... }` variable tables
# ---------------------------------------------------------------------------


_RETURN_TABLE_RE = re.compile(r"(?m)^[ \t]*return\s*\{")


def _find_return_table(text: str) -> tuple[_TableResult | None, int]:
    match = _RETURN_TABLE_RE.search(text)
    if not match:
        return None, -1
    brace = text.find("{", match.start())
    try:
        return _parse_table_result(text, brace), brace
    except LuaParseError:
        return None, -1


def read_table_values(text: str) -> dict[str, Any]:
    """Return the top-level scalar fields of a ``return { ... }`` table.

    Raw Lua expressions (for example concatenated colours) are returned as
    their source text so callers can still display them.
    """

    result, _ = _find_return_table(text)
    if result is None:
        return {}
    data = dict(result.fields)
    data.pop("__array__", None)
    return data


def set_table_values(text: str, updates: dict[str, Any]) -> str:
    """Update top-level scalar fields of the file's ``return { ... }`` table.

    Missing keys are appended before the closing brace.  Formatting and
    comments elsewhere in the file are preserved.
    """

    result, brace = _find_return_table(text)
    if result is None:
        # No return table: build one, preserving anything before it.
        body = ",\n".join(
            f"    {format_key(key)} = {format_value(value)}" for key, value in updates.items()
        )
        table = "return {\n" + body + "\n}\n"
        return text.rstrip() + "\n\n" + table if text.strip() else table

    replacements: list[tuple[int, int, str]] = []
    missing: list[tuple[str, Any]] = []
    for key, value in updates.items():
        span = result.spans.get(key)
        if span is None:
            missing.append((key, value))
        else:
            start, end = span
            replacements.append((start, end, format_value(value)))

    new_text = text
    for start, end, rendered in sorted(replacements, key=lambda item: item[0], reverse=True):
        new_text = new_text[:start] + rendered + new_text[end:]

    if missing:
        # Re-find the closing brace in the (possibly shifted) text.
        result2, _ = _find_return_table(new_text)
        if result2 is None:
            raise LuaParseError("could not locate the return table")
        close = result2.end - 1
        line_start = new_text.rfind("\n", 0, close) + 1
        indent_match = re.match(r"[ \t]*", new_text[line_start:close])
        indent = indent_match.group(0) if indent_match else ""
        if not indent:
            indent = "    "
        addition = "".join(
            f"{indent}{format_key(key)} = {format_value(value)},\n" for key, value in missing
        )
        new_text = new_text[:line_start] + addition + new_text[line_start:]

    return new_text


def remove_table_values(text: str, keys: Iterable[str]) -> str:
    """Remove top-level fields from the ``return { ... }`` table."""

    result, _ = _find_return_table(text)
    if result is None:
        return text

    new_text = text
    for key in keys:
        span = result.spans.get(key)
        if span is None:
            continue
        start, end = span
        # Expand to the whole line so commas/indentation go with the value.
        line_start = new_text.rfind("\n", 0, start) + 1
        line_end = new_text.find("\n", end)
        line_end = len(new_text) if line_end < 0 else line_end + 1
        new_text = new_text[:line_start] + new_text[line_end:]

    return new_text
