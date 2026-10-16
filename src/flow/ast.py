"""Typed syntax tree for the supported Flow language."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Statement:
    line: int


@dataclass(frozen=True)
class Context(Statement):
    path: str


@dataclass(frozen=True)
class Ask(Statement):
    prompt: str
    name: str
    value_type: str


@dataclass(frozen=True)
class SetValue(Statement):
    name: str
    expression: str


@dataclass(frozen=True)
class Show(Statement):
    value: str


@dataclass(frozen=True)
class CreateFolder(Statement):
    path: str


@dataclass(frozen=True)
class Transfer(Statement):
    operation: str
    source: str
    destination: str
    force: bool


@dataclass(frozen=True)
class WriteText(Statement):
    value: str
    path: str
    force: bool


@dataclass(frozen=True)
class ReadData(Statement):
    path: str
    name: str | None


@dataclass(frozen=True)
class SaveRows(Statement):
    path: str
    force: bool


@dataclass(frozen=True)
class If(Statement):
    condition: str
    body: tuple[Statement, ...]
    otherwise: tuple[Statement, ...]


@dataclass(frozen=True)
class ForEach(Statement):
    variable: str
    source: str
    body: tuple[Statement, ...]


@dataclass(frozen=True)
class Repeat(Statement):
    count: str
    body: tuple[Statement, ...]
