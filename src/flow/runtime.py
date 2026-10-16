"""Deterministic interpreter and filesystem actions for Flow."""

from __future__ import annotations

import ast
import csv
import io
import json
import math
import os
import operator
import re
import shutil
import tempfile
import tokenize
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

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
from flow.errors import FlowExecutionError


_BINARY_OPERATORS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_COMPARISON_OPERATORS: dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}
_VALID_OPERATORS = {"+", "-", "*", "/", "//", "%", "**"}
_MAX_LOOP_ITERATIONS = 10_000


class _OperatorValue(str):
    """A validated operator token entered through an Ask instruction."""


class Interpreter:
    """Execute a parsed Flow program, optionally planning without changing files."""

    def __init__(
        self,
        *,
        dry_run: bool = False,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ) -> None:
        self.dry_run = dry_run
        self.input_fn = input_fn
        self.output_fn = output_fn
        self.variables: dict[str, Any] = {}
        self.current_item: Path | dict[str, str] | None = None
        self.current_rows: list[dict[str, str]] = []
        self.context = Path.cwd()
        self._virtual_directories: set[Path] = set()
        self._virtual_paths: set[Path] = set()
        self.actions: list[str] = []

    def run(self, program: Iterable[Statement]) -> None:
        if self.dry_run:
            self.output_fn("FLOW PREVIEW")
        self._execute(program)
        if self.dry_run:
            self.output_fn("No files changed.")

    def _execute(self, statements: Iterable[Statement]) -> None:
        for statement in statements:
            try:
                self._execute_one(statement)
            except FlowExecutionError as exc:
                raise FlowExecutionError(f"Line {statement.line}: {exc}") from exc

    def _execute_one(self, statement: Statement) -> None:
        if isinstance(statement, Context):
            path = self._path(statement.path)
            self._ensure_no_symlinks(path)
            if not path.is_dir():
                raise FlowExecutionError(f"Folder does not exist: {path}")
            self.context = path.resolve()
            return
        if isinstance(statement, Ask):
            try:
                raw = self.input_fn(f"{statement.prompt}: ")
            except (EOFError, KeyboardInterrupt) as exc:
                raise FlowExecutionError("Input ended before a value was entered.") from exc
            if statement.value_type == "number":
                try:
                    value: Any = float(raw) if any(char in raw.casefold() for char in (".", "e")) else int(raw)
                except ValueError as exc:
                    raise FlowExecutionError(f"'{raw}' is not a valid number.") from exc
                if isinstance(value, float) and not math.isfinite(value):
                    raise FlowExecutionError(f"'{raw}' must be a finite number.")
            elif statement.value_type == "operator":
                if raw not in _VALID_OPERATORS:
                    raise FlowExecutionError(
                        f"'{raw}' is not a supported operator. Choose one of: "
                        + ", ".join(sorted(_VALID_OPERATORS))
                    )
                value = _OperatorValue(raw)
            else:
                value = raw
            self.variables[statement.name] = value
            self.variables["result"] = value
            return
        if isinstance(statement, SetValue):
            self.variables[statement.name] = self._evaluate(statement.expression)
            self.variables["result"] = self.variables[statement.name]
            return
        if isinstance(statement, Show):
            self._show(statement.value)
            return
        if isinstance(statement, CreateFolder):
            path = self._path(statement.path)
            self._ensure_no_symlinks(path)
            if path.is_dir() or path in self._virtual_directories:
                return
            if path.exists() or path in self._virtual_paths:
                raise FlowExecutionError(f"A file already exists at the folder destination: {path}")
            if self.dry_run:
                self._virtual_directories.add(path)
                self._virtual_paths.add(path)
                self._record(f"Would create folder: {path}")
            else:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    raise FlowExecutionError(f"Could not create folder {path}: {exc}") from exc
                self._record(f"Created folder: {path}")
            return
        if isinstance(statement, Transfer):
            self._transfer(statement)
            return
        if isinstance(statement, WriteText):
            self._write(statement)
            return
        if isinstance(statement, ReadData):
            self._read_data(statement)
            return
        if isinstance(statement, SaveRows):
            self._save_rows(statement)
            return
        if isinstance(statement, If):
            self._conditional(statement)
            return
        if isinstance(statement, ForEach):
            self._for_each(statement)
            return
        if isinstance(statement, Repeat):
            self._repeat(statement)
            return
        raise FlowExecutionError(f"Unsupported instruction: {type(statement).__name__}")

    def _conditional(self, statement: If) -> None:
        condition = statement.condition.strip()
        exists = re.fullmatch(r"(.+?)\s+(does\s+not\s+exist|exists)", condition, re.IGNORECASE)
        if exists:
            path = self._path(exists.group(1).strip())
            found = path.exists() or path in self._virtual_paths or path in self._virtual_directories
            is_negative = exists.group(2).casefold() == "does not exist"
            matches: list[Any] = [path] if found != is_negative else []
            self._run_branch(statement, matches)
            return

        rows = re.fullmatch(
            r"there\s+are\s+rows\s+where\s+([A-Za-z_]\w*)\s+is\s+(.+)",
            condition,
            re.IGNORECASE,
        )
        if rows:
            expected = self._value(rows.group(2))
            matches = [
                row for row in self.variables.get("rows", [])
                if str(row.get(rows.group(1), "")) == str(expected)
            ]
            self._run_branch(statement, matches, grouped=True)
            return

        matcher = self._match_condition(condition)
        if matcher is not None:
            matches = self._find_matches(*matcher)
            self._run_branch(statement, matches)
            return

        try:
            result = self._evaluate(condition)
        except FlowExecutionError as exc:
            raise FlowExecutionError(f"Invalid condition '{condition}': {exc}") from exc
        self._run_branch(statement, [result] if result else [])

    def _run_branch(self, statement: If, matches: list[Any], *, grouped: bool = False) -> None:
        if not matches:
            self._execute(statement.otherwise)
            return
        old_item, old_rows = self.current_item, self.current_rows
        old_it_present = "it" in self.variables
        old_it = self.variables.get("it")
        old_them_present = "them" in self.variables
        old_them = self.variables.get("them")
        self.variables["them"] = matches
        try:
            iteration = matches if not grouped else [matches]
            for match in iteration:
                self.current_item = match if isinstance(match, Path) else old_item
                self.current_rows = matches if grouped else old_rows
                self.variables["it"] = match if not grouped else matches
                self._execute(statement.body)
        finally:
            self.current_item, self.current_rows = old_item, old_rows
            if old_it_present:
                self.variables["it"] = old_it
            else:
                self.variables.pop("it", None)
            if old_them_present:
                self.variables["them"] = old_them
            else:
                self.variables.pop("them", None)

    def _for_each(self, statement: ForEach) -> None:
        values = self._collection(statement.source, statement.variable)
        if len(values) > _MAX_LOOP_ITERATIONS:
            raise FlowExecutionError(
                f"Loop has {len(values)} items; the safety limit is {_MAX_LOOP_ITERATIONS}."
            )
        old_context = self.context
        old_item, old_rows = self.current_item, self.current_rows
        old_them_present, old_them = "them" in self.variables, self.variables.get("them")
        old_it_present, old_it = "it" in self.variables, self.variables.get("it")
        old_name_present = statement.variable in self.variables
        old_name = self.variables.get(statement.variable)
        self.variables["them"] = values
        try:
            for value in values:
                self.current_item = value if isinstance(value, Path) else old_item
                self.current_rows = values if isinstance(value, dict) else old_rows
                self.variables["it"] = value
                self.variables[statement.variable] = value
                self._execute(statement.body)
                self.context = old_context
        finally:
            self.context = old_context
            self.current_item, self.current_rows = old_item, old_rows
            self._restore_variable(statement.variable, old_name_present, old_name)
            self._restore_variable("it", old_it_present, old_it)
            self._restore_variable("them", old_them_present, old_them)

    def _repeat(self, statement: Repeat) -> None:
        count = self._evaluate(statement.count)
        if isinstance(count, bool) or not isinstance(count, int):
            raise FlowExecutionError("Repeat count must be a whole number.")
        if not 0 <= count <= _MAX_LOOP_ITERATIONS:
            raise FlowExecutionError(
                f"Repeat count must be between 0 and {_MAX_LOOP_ITERATIONS} (the loop safety limit)."
            )
        old_iteration_present = "iteration" in self.variables
        old_iteration = self.variables.get("iteration")
        old_it_present, old_it = "it" in self.variables, self.variables.get("it")
        try:
            for index in range(1, count + 1):
                self.variables["iteration"] = index
                self.variables["it"] = index
                self._execute(statement.body)
        finally:
            self._restore_variable("iteration", old_iteration_present, old_iteration)
            self._restore_variable("it", old_it_present, old_it)

    def _collection(self, source: str, kind: str) -> list[Any]:
        value = source.strip()
        if re.fullmatch(r"[A-Za-z_]\w*", value) and value in self.variables:
            collection = self.variables[value]
            if not isinstance(collection, (list, tuple)):
                raise FlowExecutionError(f"'{value}' is not a list that can be looped over.")
            values = list(collection)
        else:
            folder = self._path(value)
            self._ensure_no_symlinks(folder)
            if not folder.is_dir():
                raise FlowExecutionError(f"Loop source is not a folder or list: {folder}")
            try:
                values = sorted(folder.iterdir(), key=lambda item: item.name.casefold())
            except OSError as exc:
                raise FlowExecutionError(f"Could not list loop folder {folder}: {exc}") from exc
            values = [entry for entry in values if not entry.is_symlink()]
        if kind == "folder":
            return [item for item in values if isinstance(item, Path) and item.is_dir()]
        if kind == "file":
            return [item for item in values if isinstance(item, Path) and item.is_file()]
        if kind == "row" and any(not isinstance(item, dict) for item in values):
            raise FlowExecutionError("For each row needs a collection of CSV rows.")
        return values

    def _show(self, source: str) -> None:
        value = source.strip()
        if value.startswith('"') and value.endswith('"'):
            self.output_fn(str(self._value(value)))
            return
        if value in self.variables or value in ("it", "them"):
            self.output_fn(_display(self._value(value)))
            return
        candidate = Path(value).expanduser()
        contextual_candidate = candidate if candidate.is_absolute() else self.context / candidate
        is_path = (
            candidate.is_absolute()
            or "/" in value
            or "\\" in value
            or contextual_candidate.exists()
        )
        if not is_path:
            self.output_fn(_display(self._value(value)))
            return
        path = self._path(value)
        self._ensure_no_symlinks(path)
        if not path.exists():
            raise FlowExecutionError(f"Cannot show '{path}': the path does not exist.")
        if path.is_dir():
            try:
                entries = sorted(path.iterdir(), key=lambda item: item.name.casefold())
            except OSError as exc:
                raise FlowExecutionError(f"Could not list folder {path}: {exc}") from exc
            self.output_fn(f"Contents of {path}:")
            if not entries:
                self.output_fn("(empty folder)")
                return
            for entry in entries:
                if entry.is_symlink():
                    kind = "Link"
                elif entry.is_dir():
                    kind = "Folder"
                else:
                    kind = "File"
                self.output_fn(f"{kind}: {entry.name}")
            return
        if path.is_file():
            try:
                self.output_fn(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError) as exc:
                raise FlowExecutionError(f"Could not show file {path} as UTF-8 text: {exc}") from exc
            return
        raise FlowExecutionError(f"Cannot show unsupported path type: {path}")

    def _restore_variable(self, name: str, existed: bool, value: Any) -> None:
        if existed:
            self.variables[name] = value
        else:
            self.variables.pop(name, None)

    @staticmethod
    def _match_condition(condition: str) -> tuple[str, tuple[str, ...]] | None:
        any_words = re.fullmatch(
            r"there\s+is\s+a\s+(folder|file)\s+containing\s+any\s+of\s+(\[.*\])",
            condition,
            re.IGNORECASE,
        )
        if any_words:
            try:
                words = ast.literal_eval(any_words.group(2))
            except (SyntaxError, ValueError) as exc:
                raise FlowExecutionError("The word list must be a list of quoted strings.") from exc
            if not isinstance(words, list) or not all(isinstance(word, str) for word in words):
                raise FlowExecutionError("The word list must contain only quoted strings.")
            return any_words.group(1).casefold(), tuple(words)

        containing = re.fullmatch(
            r"there\s+is\s+a\s+(folder|file)\s+containing\s+(.+)",
            condition,
            re.IGNORECASE,
        )
        if containing:
            return containing.group(1).casefold(), (_literal_or_raw(containing.group(2)),)

        extension = re.fullmatch(r"there\s+is\s+a\s+([A-Za-z0-9]+)", condition, re.IGNORECASE)
        if extension:
            return "extension", (extension.group(1).casefold(),)
        return None

    def _find_matches(self, kind: str, words: tuple[str, ...]) -> list[Path]:
        try:
            entries = sorted(self.context.iterdir(), key=lambda item: item.name.casefold())
        except OSError as exc:
            raise FlowExecutionError(f"Could not search {self.context}: {exc}") from exc
        matches: list[Path] = []
        for entry in entries:
            if entry.is_symlink():
                continue
            if kind == "folder" and not entry.is_dir():
                continue
            if kind == "file" and not entry.is_file():
                continue
            if kind == "extension":
                if not entry.is_file() or entry.suffix.casefold() != f".{words[0].lstrip('.')}":
                    continue
            elif words and not any(word.casefold() in entry.name.casefold() for word in words):
                continue
            matches.append(entry)
        return matches

    def _transfer(self, statement: Transfer) -> None:
        if statement.source == "it":
            sources = [self.current_item] if isinstance(self.current_item, Path) else []
        else:
            sources = list(self.variables.get("them", []))
        sources = [source for source in sources if isinstance(source, Path)]
        if not sources:
            raise FlowExecutionError(f"There is no current file or folder to {statement.operation}.")
        destination = self._path(statement.destination)
        self._ensure_no_symlinks(destination)
        for source in sources:
            self._ensure_no_symlinks(source)
            if not source.exists():
                raise FlowExecutionError(f"Source no longer exists: {source}")
            if destination.exists() and not destination.is_dir():
                raise FlowExecutionError(f"Destination is not a folder: {destination}")
            if destination not in self._virtual_directories and not destination.is_dir():
                raise FlowExecutionError(f"Destination folder does not exist: {destination}")
            target = destination / source.name
            self._ensure_no_symlinks(target)
            if target.resolve(strict=False) == source.resolve(strict=False):
                raise FlowExecutionError(f"Source and destination are the same path: {source}")
            target_exists = target.exists() or target in self._virtual_paths
            if target_exists and not statement.force:
                raise FlowExecutionError(f"Destination already exists; nothing was overwritten: {target}")
            verb = "move" if statement.operation == "move" else "copy"
            if self.dry_run:
                if target_exists:
                    self._record(f"Would replace existing destination: {target}")
                self._virtual_paths.add(target)
                if source.is_dir():
                    self._virtual_directories.add(target)
                self._record(f"Would {verb}: {source} -> {target}")
                continue
            try:
                if target_exists:
                    if target.is_symlink():
                        raise FlowExecutionError(f"Refusing to replace symbolic link: {target}")
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                if statement.operation == "move":
                    shutil.move(str(source), str(target))
                else:
                    if source.is_dir():
                        shutil.copytree(source, target, symlinks=True)
                    else:
                        shutil.copy2(source, target)
            except FlowExecutionError:
                raise
            except OSError as exc:
                raise FlowExecutionError(f"Could not {verb} {source} to {target}: {exc}") from exc
            self._record(f"{verb.capitalize()}d: {source} -> {target}")

    def _write(self, statement: WriteText) -> None:
        path = self._path(statement.path)
        self._ensure_no_symlinks(path)
        if path.is_dir():
            raise FlowExecutionError(f"Cannot write a file over a folder: {path}")
        exists = path.exists() or path in self._virtual_paths
        if exists and not statement.force:
            raise FlowExecutionError(f"Destination already exists; nothing was overwritten: {path}")
        value = self._value(statement.value)
        is_json = path.suffix.casefold() == ".json"
        if isinstance(value, list) and not is_json:
            value = "\n".join(str(item) for item in value)
        if is_json:
            try:
                content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
            except (TypeError, ValueError) as exc:
                raise FlowExecutionError(f"Could not encode JSON for {path}: {exc}") from exc
        else:
            content = str(value)
        if self.dry_run:
            self._plan_parent_folders(path.parent)
            self._virtual_paths.add(path)
            message = "Would overwrite" if exists else "Would write"
            self._record(f"{message} {'JSON' if is_json else 'text'}: {path}")
            return
        try:
            self._create_parent_folders(path.parent)
            self._write_output(path, content, statement.force)
        except OSError as exc:
            raise FlowExecutionError(f"Could not write {path}: {exc}") from exc
        self._record(f"{'Overwrote' if exists else 'Wrote'} {'JSON' if is_json else 'text'}: {path}")

    def _read_data(self, statement: ReadData) -> None:
        path = self._path(statement.path)
        self._ensure_no_symlinks(path)
        if not path.is_file():
            raise FlowExecutionError(f"File does not exist: {path}")
        try:
            if path.suffix.casefold() == ".csv":
                with path.open("r", encoding="utf-8-sig", newline="") as stream:
                    rows = list(csv.DictReader(stream))
                self.variables["rows"] = rows
                self.variables["them"] = rows
                self.variables["result"] = rows
                if statement.name:
                    self.variables[statement.name] = rows
                self._record(f"Read {len(rows)} row(s) from: {path}")
            elif path.suffix.casefold() == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
                self.variables["data"] = data
                self.variables["rows"] = []
                self.variables["them"] = []
                self.variables["result"] = data
                if statement.name:
                    self.variables[statement.name] = data
                self._record(f"Read JSON data from: {path}")
            else:
                content = path.read_text(encoding="utf-8")
                self.variables["content"] = content
                self.variables["rows"] = []
                self.variables["them"] = []
                self.variables["result"] = content
                if statement.name:
                    self.variables[statement.name] = content
                self._record(f"Read text from: {path}")
        except (OSError, csv.Error, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise FlowExecutionError(f"Could not read {path}: {exc}") from exc

    def _save_rows(self, statement: SaveRows) -> None:
        rows = self.current_rows or self.variables.get("them", [])
        if not rows or not all(isinstance(row, dict) for row in rows):
            raise FlowExecutionError("There are no filtered rows to save.")
        path = self._path(statement.path)
        self._ensure_no_symlinks(path)
        if path.is_dir():
            raise FlowExecutionError(f"Cannot save a CSV file over a folder: {path}")
        exists = path.exists() or path in self._virtual_paths
        if exists and not statement.force:
            raise FlowExecutionError(f"Destination already exists; nothing was overwritten: {path}")
        if self.dry_run:
            self._plan_parent_folders(path.parent)
            self._virtual_paths.add(path)
            action = "overwrite" if exists else "save"
            self._record(f"Would {action} {len(rows)} row(s) to: {path}")
            return
        try:
            self._create_parent_folders(path.parent)
            buffer = io.StringIO(newline="")
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
            self._write_output(path, buffer.getvalue(), statement.force)
        except (OSError, csv.Error) as exc:
            raise FlowExecutionError(f"Could not save CSV {path}: {exc}") from exc
        self._record(f"{'Overwrote' if exists else 'Saved'} {len(rows)} row(s) to: {path}")

    @staticmethod
    def _write_output(path: Path, content: str, force: bool) -> None:
        if not force:
            created = False
            try:
                with path.open("x", encoding="utf-8", newline="") as stream:
                    created = True
                    stream.write(content)
            except OSError:
                if created:
                    path.unlink(missing_ok=True)
                raise
            return
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", dir=path.parent,
                prefix=f".{path.name}.", delete=False
            ) as stream:
                temporary_path = Path(stream.name)
                stream.write(content)
            os.replace(temporary_path, path)
        except OSError:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

    def _evaluate(self, expression: str) -> Any:
        source = expression.strip()
        if source.startswith('"') and source.endswith('"'):
            try:
                return ast.literal_eval(source)
            except (SyntaxError, ValueError) as exc:
                if source.count('"') == 2:
                    raise FlowExecutionError(f"Invalid text value: {source}") from exc
        source = self._replace_operator_variables(source)
        try:
            parsed = ast.parse(source, mode="eval")
            return self._eval_node(parsed.body)
        except SyntaxError as exc:
            raise FlowExecutionError(f"Invalid expression: {source}") from exc
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise FlowExecutionError(f"Could not evaluate expression '{source}': {exc}") from exc

    def _replace_operator_variables(self, source: str) -> str:
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        except tokenize.TokenError as exc:
            raise FlowExecutionError(f"Invalid expression: {source}") from exc
        for token in reversed(tokens):
            if token.type != tokenize.NAME:
                continue
            value = self.variables.get(token.string)
            if not isinstance(value, _OperatorValue):
                continue
            start, end = token.start[1], token.end[1]
            source = source[:start] + str(value) + source[end:]
        return source

    def _eval_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool)):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in ("it", "them"):
                if node.id in self.variables:
                    return self.variables[node.id]
                if node.id == "it" and self.current_item is not None:
                    return self.current_item
                raise FlowExecutionError(f"'{node.id}' has no current value here.")
            if node.id not in self.variables:
                raise FlowExecutionError(f"Unknown value '{node.id}'.")
            return self.variables[node.id]
        if isinstance(node, ast.Subscript):
            collection = self._eval_node(node.value)
            key = self._eval_node(node.slice)
            try:
                return collection[key]
            except (KeyError, IndexError, TypeError) as exc:
                raise FlowExecutionError(f"Cannot read item {key!r} from this value.") from exc
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
            return _BINARY_OPERATORS[type(node.op)](self._eval_node(node.left), self._eval_node(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)):
            value = self._eval_node(node.operand)
            return +value if isinstance(node.op, ast.UAdd) else (-value if isinstance(node.op, ast.USub) else not value)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            values = [self._eval_node(value) for value in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators, strict=True):
                right = self._eval_node(comparator)
                operation = _COMPARISON_OPERATORS.get(type(op))
                if operation is None or not operation(left, right):
                    return False
                left = right
            return True
        raise FlowExecutionError("Only numbers, text, variables, arithmetic, and comparisons are allowed in expressions.")

    def _value(self, source: str) -> Any:
        value = source.strip()
        if value.startswith('"') and value.endswith('"'):
            try:
                return ast.literal_eval(value)
            except (SyntaxError, ValueError) as exc:
                raise FlowExecutionError(f"Invalid quoted text: {value}") from exc
        if re.fullmatch(r"[A-Za-z_]\w*", value) and value in self.variables:
            return self.variables[value]
        if value in ("it", "them"):
            return self._eval_node(ast.Name(id=value))
        return self._evaluate(value)

    def _path(self, value: str) -> Path:
        raw = value.strip()
        if raw.startswith('"') and raw.endswith('"'):
            resolved_value: Any = _literal_or_raw(raw)
        elif re.fullmatch(r"[A-Za-z_]\w*", raw) and raw in self.variables:
            resolved_value = self.variables[raw]
        elif raw in ("it", "them"):
            resolved_value = self._eval_node(ast.Name(id=raw))
        else:
            resolved_value = raw
        if isinstance(resolved_value, _OperatorValue):
            raise FlowExecutionError("An operator value cannot be used as a path.")
        if not isinstance(resolved_value, Path):
            if not isinstance(resolved_value, (str, int, float)):
                raise FlowExecutionError(f"Expected a path, got {resolved_value!r}.")
            path = Path(str(resolved_value)).expanduser()
        else:
            path = resolved_value
        if not path.is_absolute():
            path = self.context / path
        return Path(path)

    def _plan_parent_folders(self, parent: Path) -> None:
        missing: list[Path] = []
        current = parent
        while True:
            if current in self._virtual_paths and current not in self._virtual_directories:
                raise FlowExecutionError(f"A file already exists where a folder is needed: {current}")
            if current in self._virtual_directories or current.exists():
                if not current.is_dir() and current not in self._virtual_directories:
                    raise FlowExecutionError(f"A file already exists where a folder is needed: {current}")
                break
            missing.append(current)
            current = current.parent
        for folder in reversed(missing):
            self._virtual_directories.add(folder)
            self._virtual_paths.add(folder)
            self._record(f"Would create folder: {folder}")

    def _create_parent_folders(self, parent: Path) -> None:
        missing: list[Path] = []
        current = parent
        while not current.exists():
            missing.append(current)
            current = current.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise FlowExecutionError(f"Could not create parent folder {parent}: {exc}") from exc
        for folder in reversed(missing):
            self._record(f"Created folder: {folder}")

    @staticmethod
    def _ensure_no_symlinks(path: Path) -> None:
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current /= part
            if current.is_symlink():
                raise FlowExecutionError(f"Refusing to follow symbolic link: {current}")

    def _record(self, message: str) -> None:
        self.actions.append(message)
        self.output_fn(message)


def _literal_or_raw(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise FlowExecutionError(f"Invalid quoted value: {value}") from exc
        if isinstance(parsed, str):
            return parsed
    return value


def _display(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return str(value)
