"""Indentation-aware parser for Flow's initial, deliberately small grammar."""

from __future__ import annotations

import ast as python_ast
import re
from dataclasses import dataclass

from flow.ast import (
    Ask,
    Context,
    CreateFolder,
    ForEach,
    If,
    ReadData,
    Repeat,
    SaveRows,
    SetValue,
    Show,
    Statement,
    Transfer,
    WriteText,
)
from flow.errors import FlowSyntaxError


@dataclass(frozen=True)
class _Line:
    number: int
    indent: int
    text: str


class Parser:
    def __init__(self, source: str) -> None:
        self.lines: list[_Line] = []
        for number, raw in enumerate(source.splitlines(), start=1):
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            if "\t" in raw[: len(raw) - len(raw.lstrip())]:
                raise FlowSyntaxError(f"Line {number}: use spaces, not tabs, for indentation.")
            indent = len(raw) - len(raw.lstrip(" "))
            self.lines.append(_Line(number, indent, raw.strip()))
        self.index = 0

    def parse(self) -> tuple[Statement, ...]:
        statements = self._block(0, allow_otherwise=False)
        if self.index < len(self.lines):
            line = self.lines[self.index]
            raise FlowSyntaxError(f"Line {line.number}: unexpected indentation or block marker.")
        return tuple(statements)

    def _block(self, indent: int, allow_otherwise: bool) -> list[Statement]:
        statements: list[Statement] = []
        while self.index < len(self.lines):
            line = self.lines[self.index]
            if line.indent < indent:
                break
            if line.indent > indent:
                raise FlowSyntaxError(f"Line {line.number}: unexpected indentation.")
            if line.text.casefold() == "end":
                break
            if line.text.casefold() == "otherwise":
                if not allow_otherwise:
                    raise FlowSyntaxError(f"Line {line.number}: Otherwise has no matching If.")
                break
            self.index += 1
            if line.text.casefold().startswith("if "):
                statements.append(self._parse_if(line))
            elif line.text.casefold().startswith("for each "):
                statements.append(self._parse_for_each(line))
            elif line.text.casefold().startswith("repeat "):
                statements.append(self._parse_repeat(line))
            else:
                statements.append(self._parse_statement(line))
        return statements

    def _parse_if(self, line: _Line) -> If:
        condition = line.text[3:].strip()
        if not condition:
            raise FlowSyntaxError(f"Line {line.number}: If needs a condition.")
        body = self._block(line.indent + 4, allow_otherwise=True)
        if self.index >= len(self.lines):
            raise FlowSyntaxError(f"Line {line.number}: If block is missing End.")

        otherwise: list[Statement] = []
        marker = self.lines[self.index]
        if marker.indent == line.indent and marker.text.casefold() == "otherwise":
            self.index += 1
            otherwise = self._block(line.indent + 4, allow_otherwise=False)
            if self.index >= len(self.lines):
                raise FlowSyntaxError(f"Line {line.number}: If block is missing End.")
            marker = self.lines[self.index]
        if marker.indent != line.indent or marker.text.casefold() != "end":
            raise FlowSyntaxError(f"Line {marker.number}: expected End for If on line {line.number}.")
        self.index += 1
        return If(line.number, condition, tuple(body), tuple(otherwise))

    def _parse_for_each(self, line: _Line) -> ForEach:
        match = re.fullmatch(r"For\s+each\s+(item|file|folder|row)\s+in\s+(.+)", line.text, re.IGNORECASE)
        if not match:
            raise FlowSyntaxError(
                f"Line {line.number}: use 'For each item|file|folder|row in a-folder-or-list'."
            )
        body = self._block(line.indent + 4, allow_otherwise=False)
        self._consume_end(line)
        return ForEach(line.number, match.group(1).casefold(), match.group(2).strip(), tuple(body))

    def _parse_repeat(self, line: _Line) -> Repeat:
        match = re.fullmatch(r"Repeat\s+(.+?)\s+times", line.text, re.IGNORECASE)
        if not match:
            raise FlowSyntaxError(f"Line {line.number}: use 'Repeat a-number times'.")
        body = self._block(line.indent + 4, allow_otherwise=False)
        self._consume_end(line)
        return Repeat(line.number, match.group(1).strip(), tuple(body))

    def _consume_end(self, line: _Line) -> None:
        if self.index >= len(self.lines):
            raise FlowSyntaxError(f"Line {line.number}: block is missing End.")
        marker = self.lines[self.index]
        if marker.indent != line.indent or marker.text.casefold() != "end":
            raise FlowSyntaxError(f"Line {marker.number}: expected End for block on line {line.number}.")
        self.index += 1

    def _parse_statement(self, line: _Line) -> Statement:
        text = line.text
        if match := re.fullmatch(r"In\s+(.+)", text, flags=re.IGNORECASE):
            return Context(line.number, _unquote(match.group(1).strip()))
        if match := re.fullmatch(
            r'Ask\s+for\s+(another\s+|an?\s+)?(number|string|text|operator)\s+and\s+call\s+it\s+([A-Za-z_]\w*)',
            text,
            flags=re.IGNORECASE,
        ):
            value_type = match.group(2).casefold()
            value_type = "string" if value_type == "text" else value_type
            prompt = f"Enter {value_type}" if not match.group(1) else f"Enter another {value_type}"
            return Ask(line.number, prompt, match.group(3), value_type)
        if match := re.fullmatch(r'Ask\s+"((?:[^"\\]|\\.)*)"\s+and\s+call\s+it\s+([A-Za-z_]\w*)', text, flags=re.IGNORECASE):
            return Ask(line.number, _unquote(f'"{match.group(1)}"'), match.group(2), "string")
        if match := re.fullmatch(r"Set\s+([A-Za-z_]\w*)\s+to\s+(.+)", text, flags=re.IGNORECASE):
            return SetValue(line.number, match.group(1), match.group(2))
        if match := re.fullmatch(r"Show\s+(.+)", text, flags=re.IGNORECASE):
            return Show(line.number, match.group(1))
        if match := re.fullmatch(r"Create\s+folder\s+(.+?)(?:\s+if\s+it\s+does\s+not\s+exist)?", text, flags=re.IGNORECASE):
            return CreateFolder(line.number, _unquote(match.group(1).strip()))
        if match := re.fullmatch(r"(Move|Copy)\s+(it|them)\s+to\s+(.+?)(?:\s+(force))?", text, flags=re.IGNORECASE):
            return Transfer(
                line.number, match.group(1).casefold(), match.group(2).casefold(),
                _unquote(match.group(3).strip()), bool(match.group(4)),
            )
        if match := re.fullmatch(
            r'Write\s+("(?:[^"\\]|\\.)*"|.+?)\s+to\s+(.+?)(?:\s+(force))?',
            text,
            flags=re.IGNORECASE,
        ):
            return WriteText(
                line.number, match.group(1), _unquote(match.group(2).strip()), bool(match.group(3))
            )
        if match := re.fullmatch(r"Read\s+(.+?)(?:\s+and\s+call\s+it\s+([A-Za-z_]\w*))?", text, flags=re.IGNORECASE):
            return ReadData(line.number, _unquote(match.group(1).strip()), match.group(2))
        if match := re.fullmatch(
            r"Save\s+those\s+rows\s+to\s+(.+?)(?:\s+(force))?",
            text,
            flags=re.IGNORECASE,
        ):
            return SaveRows(line.number, _unquote(match.group(1).strip()), bool(match.group(2)))
        unsupported = ("Every ", "When ", "Run ")
        if text.startswith(unsupported):
            raise FlowSyntaxError(
                f"Line {line.number}: scheduling, triggers, and script calls are not available in v0.1."
            )
        raise FlowSyntaxError(f"Line {line.number}: I don't understand this instruction: {text}")


def _unquote(value: str) -> str:
    if value.startswith('"') and value.endswith('"'):
        try:
            result = python_ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise FlowSyntaxError(f"Invalid quoted value: {value}") from exc
        if not isinstance(result, str):
            raise FlowSyntaxError(f"Expected quoted text, got: {value}")
        return result
    return value


def parse(source: str) -> tuple[Statement, ...]:
    """Parse Flow source into an immutable statement tree."""
    return Parser(source).parse()
