"""Strict single-action JSON protocol. Never execute partially parsed output."""
import json
import re


class ParseError(ValueError):
    pass


SCHEMA = {
    "shell": ({"command": str}, {}),
    "read": ({"path": str}, {"start": int, "lines": int}),
    "patch": ({"path": str, "old": str, "new": str}, {}),
    "search": ({"query": str}, {"path": str}),
    "finish": ({"message": str}, {}),
}


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ParseError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_action(content: str):
    text = content.strip()
    repaired = False
    fence = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", text, re.S)
    if fence:
        text = fence.group(1).strip()
        repaired = True
    try:
        value = json.loads(text, object_pairs_hook=no_duplicates,
                           parse_constant=lambda x: (_ for _ in ()).throw(ParseError(f"invalid JSON constant {x}")))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ParseError("reply with one valid JSON object; escape newlines inside strings") from exc
    if type(value) is not dict or set(value) != {"tool", "args"}:
        raise ParseError('required shape: {"tool":"name","args":{...}}; no extra keys')
    tool, args = value["tool"], value["args"]
    if not isinstance(tool, str) or tool not in SCHEMA or type(args) is not dict:
        raise ParseError("unknown tool or non-object args")
    required, optional = SCHEMA[tool]
    if not set(required) <= set(args) or set(args) - set(required) - set(optional):
        raise ParseError(f"{tool} requires {list(required)}; optional {list(optional)}")
    for key, expected in (required | optional).items():
        if key in args and type(args[key]) is not expected:
            raise ParseError(f"{key} must be {expected.__name__}")
        if key in args and isinstance(args[key], str) and (len(args[key]) > 32768 or "\x00" in args[key]):
            raise ParseError(f"{key} is too long or contains a NUL")
    if "start" in args and args["start"] < 1:
        raise ParseError("start must be positive")
    if "lines" in args and not 1 <= args["lines"] <= 200:
        raise ParseError("lines must be between 1 and 200")
    return value, repaired
