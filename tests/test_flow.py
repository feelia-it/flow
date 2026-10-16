from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from flow.cli import main
from flow.errors import FlowExecutionError, FlowSyntaxError
from flow.parser import parse
from flow.runtime import Interpreter


class FlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.output: list[str] = []

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_flow(self, source: str, *, dry_run: bool = False, answers: list[str] | None = None) -> Interpreter:
        responses = iter(answers or [])

        def answer(prompt: str) -> str:
            self.assertTrue(prompt.endswith(": "))
            return next(responses)

        interpreter = Interpreter(
            dry_run=dry_run,
            input_fn=answer,
            output_fn=self.output.append,
        )
        interpreter.run(parse(source))
        return interpreter

    def test_calculator_and_nested_conditional(self) -> None:
        source = """
Ask for a number and call it first
Ask for another number and call it second
Set result to first + second
If result == 12
    If first < second
        Show result
    End
Otherwise
    Show "wrong"
End
"""
        self.run_flow(source, answers=["5", "7"])
        self.assertEqual(self.output, ["12"])

    def test_reports_invalid_number_as_flow_error(self) -> None:
        with self.assertRaisesRegex(FlowExecutionError, "not a valid number"):
            self.run_flow("Ask for a number and call it count", answers=["lots"])

    def test_ask_string_and_operator_values_work_in_expressions(self) -> None:
        self.run_flow(
            """
Ask for a number and call it first
Ask for an operator and call it operation
Ask for a string and call it label
Set result to first operation 3
Show label
Show result
""",
            answers=["5", "*", "Product"],
        )
        self.assertEqual(self.output, ["Product", "15"])

    def test_text_expressions_support_concatenation(self) -> None:
        self.run_flow('Set greeting to "Hello, " + "Flow"\nShow greeting')
        self.assertEqual(self.output, ["Hello, Flow"])

    def test_invalid_operator_is_reported_as_a_flow_error(self) -> None:
        with self.assertRaisesRegex(FlowExecutionError, "not a supported operator"):
            self.run_flow("Ask for an operator and call it operation", answers=[";"])

    def test_unknown_expression_name_is_not_silently_treated_as_text(self) -> None:
        with self.assertRaisesRegex(FlowExecutionError, "Unknown value 'missing'"):
            self.run_flow("Show missing")

    def test_unbound_pronouns_produce_real_errors(self) -> None:
        with self.assertRaisesRegex(FlowExecutionError, "has no current value"):
            self.run_flow("Show it")
        with self.assertRaisesRegex(FlowExecutionError, "has no current value"):
            self.run_flow("Show them")

    def test_folder_match_moves_each_match_and_creates_destination(self) -> None:
        downloads = self.root / "downloads"
        downloads.mkdir()
        (downloads / "Accounts 2026").mkdir()
        (downloads / "Hello Payments").mkdir()
        (downloads / "Other").mkdir()
        backup = self.root / "backup"
        source = f"""
In {downloads}
If there is a folder containing any of ["Hello", "Accounts", "Payments"]
    If {backup} does not exist
        Create folder {backup}
    End
    Move it to {backup}
End
"""
        self.run_flow(source)
        self.assertTrue((backup / "Accounts 2026").is_dir())
        self.assertTrue((backup / "Hello Payments").is_dir())
        self.assertTrue((downloads / "Other").is_dir())
        self.assertEqual(len([line for line in self.output if line.startswith("Moved:")]), 2)

    def test_preview_plans_changes_without_mutating_files(self) -> None:
        downloads = self.root / "downloads"
        downloads.mkdir()
        (downloads / "Accounts").mkdir()
        backup = self.root / "backup"
        source = f"""
In {downloads}
If there is a folder containing any of ["Accounts"]
    If {backup} does not exist
        Create folder {backup}
    End
    Move it to {backup}
End
"""
        self.run_flow(source, dry_run=True)
        self.assertTrue((downloads / "Accounts").is_dir())
        self.assertFalse(backup.exists())
        self.assertTrue(any(line.startswith("Would move:") for line in self.output))
        self.assertEqual(self.output[-1], "No files changed.")

    def test_destination_collision_does_not_overwrite_or_move_source(self) -> None:
        downloads = self.root / "downloads"
        backup = self.root / "backup"
        downloads.mkdir()
        backup.mkdir()
        source_folder = downloads / "Accounts"
        source_folder.mkdir()
        (source_folder / "original.txt").write_text("source", encoding="utf-8")
        target = backup / "Accounts"
        target.mkdir()
        (target / "original.txt").write_text("target", encoding="utf-8")

        with self.assertRaisesRegex(FlowExecutionError, "nothing was overwritten"):
            self.run_flow(f"In {downloads}\nIf there is a folder containing \"Accounts\"\n    Move it to {backup}\nEnd")
        self.assertEqual((source_folder / "original.txt").read_text(encoding="utf-8"), "source")
        self.assertEqual((target / "original.txt").read_text(encoding="utf-8"), "target")

    def test_write_text_keeps_text_as_data_and_rejects_existing_file(self) -> None:
        output_path = self.root / "report.txt"
        content = 'Write "Set x to 99" to ' + str(output_path)
        self.run_flow(content)
        self.assertEqual(output_path.read_text(encoding="utf-8"), "Set x to 99")
        with self.assertRaisesRegex(FlowExecutionError, "nothing was overwritten"):
            self.run_flow(content)

    def test_force_replaces_existing_text_and_json_files(self) -> None:
        text_path = self.root / "report.txt"
        text_path.write_text("old report", encoding="utf-8")
        json_path = self.root / "settings.json"
        json_path.write_text('{"old": true}', encoding="utf-8")
        self.run_flow(
            f'Write "new report" to {text_path} force\n'
            f'Write "updated" to {json_path} force'
        )
        self.assertEqual(text_path.read_text(encoding="utf-8"), "new report")
        self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), "updated")

    def test_read_and_write_json(self) -> None:
        source = self.root / "settings.json"
        destination = self.root / "copy.json"
        source.write_text('{"theme": "dark", "enabled": true}', encoding="utf-8")
        self.run_flow(f"Read {source}\nWrite data to {destination}")
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), {"theme": "dark", "enabled": True})

    def test_csv_filter_saves_all_matching_rows(self) -> None:
        source = self.root / "sales.csv"
        source.write_text("status,amount\nPending,10\nDone,20\nPending,30\n", encoding="utf-8")
        report = self.root / "reports" / "pending.csv"
        self.run_flow(
            f"""
Read {source}
If there are rows where status is "Pending"
    Save those rows to {report}
Otherwise
    Show "No pending orders found"
End
"""
        )
        with report.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows, [{"status": "Pending", "amount": "10"}, {"status": "Pending", "amount": "30"}])

    def test_force_replaces_existing_csv_report_on_rerun(self) -> None:
        source = self.root / "sales.csv"
        source.write_text("status,amount\nPending,10\n", encoding="utf-8")
        report = self.root / "pending.csv"
        script = f"""
Read {source}
If there are rows where status is "Pending"
    Save those rows to {report} force
End
"""
        self.run_flow(script)
        self.output.clear()
        self.run_flow(script)
        with report.open(encoding="utf-8", newline="") as stream:
            self.assertEqual(list(csv.DictReader(stream)), [{"status": "Pending", "amount": "10"}])
        self.assertIn(f"Overwrote 1 row(s) to: {report}", self.output)

    def test_force_replaces_existing_transfer_destination(self) -> None:
        source_folder = self.root / "source"
        target_folder = self.root / "target"
        source_folder.mkdir()
        target_folder.mkdir()
        (source_folder / "item").mkdir()
        (source_folder / "item" / "fresh.txt").write_text("fresh", encoding="utf-8")
        (target_folder / "item").mkdir()
        (target_folder / "item" / "stale.txt").write_text("stale", encoding="utf-8")
        self.run_flow(
            f'In {source_folder}\nIf there is a folder containing "item"\n'
            f'    Move it to {target_folder} force\nEnd'
        )
        self.assertTrue((target_folder / "item" / "fresh.txt").exists())
        self.assertFalse((target_folder / "item" / "stale.txt").exists())

    def test_for_each_and_repeat_loops_are_bounded_and_work(self) -> None:
        folder = self.root / "data"
        folder.mkdir()
        (folder / "A").mkdir()
        (folder / "B").mkdir()
        (folder / "note.txt").write_text("hello", encoding="utf-8")
        self.run_flow(
            f"""
For each folder in {folder}
    Show it
End
Repeat 3 times
    Show iteration
End
"""
        )
        self.assertEqual(
            self.output,
            [str(folder / "A"), str(folder / "B"), "1", "2", "3"],
        )

    def test_for_each_can_iterate_csv_rows_and_read_fields(self) -> None:
        source = self.root / "sales.csv"
        source.write_text("status,amount\nPending,10\nDone,20\n", encoding="utf-8")
        self.run_flow(f"Read {source} and call it sales\nFor each row in sales\n    Show row[\"status\"]\nEnd")
        self.assertEqual(self.output[-2:], ["Pending", "Done"])

    def test_repeat_limit_is_reported_as_a_flow_error(self) -> None:
        with self.assertRaisesRegex(FlowExecutionError, "safety limit"):
            self.run_flow("Repeat 10001 times\n    Show iteration\nEnd")

    def test_show_directory_lists_its_contents(self) -> None:
        folder = self.root / "data"
        folder.mkdir()
        (folder / "subfolder").mkdir()
        (folder / "notes.txt").write_text("text", encoding="utf-8")
        self.run_flow(f"Show {folder}")
        self.assertEqual(
            self.output,
            [f"Contents of {folder}:", "File: notes.txt", "Folder: subfolder"],
        )

    def test_read_supports_named_text_and_json_values(self) -> None:
        text_path = self.root / "notes.txt"
        text_path.write_text("read me", encoding="utf-8")
        json_path = self.root / "settings.json"
        json_path.write_text('{"enabled": true}', encoding="utf-8")
        interpreter = self.run_flow(
            f"Read {text_path} and call it notes\n"
            f"Read {json_path} and call it settings\n"
            "Show notes\nShow settings"
        )
        self.assertEqual(interpreter.variables["notes"], "read me")
        self.assertEqual(interpreter.variables["settings"], {"enabled": True})
        self.assertEqual(self.output[-2:], ["read me", '{\n  "enabled": true\n}'])

    def test_parser_rejects_unclosed_and_misindented_blocks(self) -> None:
        with self.assertRaisesRegex(FlowSyntaxError, "missing End"):
            parse("If total > 0\n    Show total")
        with self.assertRaisesRegex(FlowSyntaxError, "unexpected indentation"):
            parse("Show 1\n    Show 2")

    def test_parser_reports_deferred_features_as_unsupported(self) -> None:
        with self.assertRaisesRegex(FlowSyntaxError, "not available in v0.1"):
            parse("Every day at 10 PM")

    def test_matching_skips_symbolic_links(self) -> None:
        downloads = self.root / "downloads"
        downloads.mkdir()
        outside = self.root / "Accounts"
        outside.mkdir()
        (downloads / "Accounts-link").symlink_to(outside, target_is_directory=True)
        self.run_flow(f'In {downloads}\nIf there is a folder containing "Accounts"\n    Show it\nEnd')
        self.assertEqual(self.output, [])

    def test_transfer_refuses_symlink_destinations_even_with_force(self) -> None:
        source_folder = self.root / "source"
        target_folder = self.root / "target"
        outside = self.root / "outside.txt"
        source_folder.mkdir()
        target_folder.mkdir()
        (source_folder / "item.txt").write_text("new", encoding="utf-8")
        outside.write_text("keep", encoding="utf-8")
        (target_folder / "item.txt").symlink_to(outside)
        with self.assertRaisesRegex(FlowExecutionError, "symbolic link"):
            self.run_flow(
                f'In {source_folder}\nIf there is a file containing "item"\n'
                f'    Copy it to {target_folder} force\nEnd'
            )
        self.assertEqual(outside.read_text(encoding="utf-8"), "keep")

    def test_cli_preview_returns_success_for_valid_script(self) -> None:
        script = self.root / "hello.flow"
        script.write_text('Show "hello"\n', encoding="utf-8")
        self.assertEqual(main(["preview", str(script)]), 0)


if __name__ == "__main__":
    unittest.main()
