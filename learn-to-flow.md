# Learn to Flow

Flow is a readable language for describing small automations. A `.flow` script can ask questions, calculate, inspect folders, read and write documents, process CSV rows, and repeat work with loops. Flow runs locally and executes only the instructions its parser understands.

## Get started

Install Flow from the project directory using Python 3.12 or newer:

```bash
python -m pip install .
```

Check a script before changing files:

```bash
flow preview examples/organize-downloads.flow
```

Run it:

```bash
flow run examples/organize-downloads.flow
```

Preview follows the same script logic but does not create, overwrite, copy, or move files. It prints the planned file operations and ends with `No files changed.` Use preview before running any script that changes data.

## Your first Flow program

```text
Ask for a number and call it first
Ask for another number and call it second

Set total to first + second
Show "The total is:"
Show total
```

Save as `addition.flow`. Each instruction is one line. Quoted values are text; names such as `first` and `total` refer to values stored by `Ask` or `Set`.

## Ask for input

Use one of Flow's typed questions:

```text
Ask for a number and call it age
Ask for another number and call it quantity
Ask for a string and call it name
Ask for an operator and call it operation
Ask "What should we call this report?" and call it report_name
```

`text` is also accepted in place of `string`. Number input accepts whole numbers, decimals, and scientific notation, for example `12`, `2.5`, or `1e3`. Invalid, infinite, or missing numeric input is reported as a Flow error. An operator question accepts only `+`, `-`, `*`, `/`, `//`, `%`, and `**`.

Use an asked operator in an expression:

```text
Ask for a number and call it left
Ask for an operator and call it operation
Ask for another number and call it right
Set answer to left operation right
Show answer
```

## Values, calculations, and comparisons

```text
Set subtotal to 12.50 * 4
Set tax to subtotal * 0.08
Set total to subtotal + tax
Show total
```

Arithmetic uses the usual precedence and parentheses:

```text
Set answer to (first + second) * 2
```

Supported operators: `+`, `-`, `*`, `/`, `//`, `%`, `**`, unary `+`/`-`, comparisons `==`, `!=`, `<`, `<=`, `>`, `>=`, and boolean `and`, `or`, `not`. Text values must be quoted when written literally. Unknown variable names, invalid types, division by zero, and unsupported expression syntax produce clear errors; Flow does not execute arbitrary Python.

## Show text, values, and folder contents

```text
Show "Report complete"
Show total
Show /home/alex/Documents
```

Showing a folder path lists its immediate contents, sorted by name, and labels each entry as a file, folder, or symbolic link. It does not recursively traverse subfolders. Showing a UTF-8 text file displays its contents. To show a path value held in a variable, Flow prints the path itself; to list the directory, write the directory path directly, as in `Show /home/alex/Documents`.

## Conditions

Conditions use `If`, optional `Otherwise`, and a matching `End`. Indent the body with four spaces:

```text
If total >= 100
    Show "Large order"
Otherwise
    Show "Standard order"
End
```

Existence checks can create a missing destination:

```text
If /home/alex/backup does not exist
    Create folder /home/alex/backup
End
```

File and folder matching searches only the immediate contents of the active folder:

```text
In /home/alex/Downloads

If there is a folder containing any of ["Accounts", "Payments"]
    Show it
Otherwise
    Show "No matching folders"
End
```

`If there is a PDF` matches files with the `.pdf` extension. Matching folder/file names is case-insensitive. A matching block runs once for each match.

## Loops

`For each` iterates over a folder's immediate entries or over a list already in a Flow value:

```text
For each folder in /home/alex/Projects
    Show it
End

For each file in /home/alex/Downloads
    Show it
End
```

Use `item` for both files and folders, and `row` for CSV records:

```text
Read /home/alex/sales.csv and call it sales

For each row in sales
    Show row["status"]
End
```

The current loop value is available as `it` and by the declared variable name. `them` is the full collection for a `For each` loop. Loops are limited to 10,000 iterations, including `Repeat`, to guard against accidentally huge or unbounded work.

For a fixed number of repetitions:

```text
Repeat 3 times
    Show iteration
End
```

`iteration` starts at 1. A repeat count must be a whole number from 0 through 10,000.

## Work with files and folders

Set the working folder with `In`. Relative paths in following instructions are resolved against that folder:

```text
In /home/alex/Downloads
If there is a folder containing "Invoices"
    Move it to /home/alex/Documents
End
```

`it` means the current matched/looped file or folder. `them` means the whole collection:

```text
If there is a folder containing any of ["Accounts", "Payments"]
    Move it to /home/alex/Archive
End
```

Supported file actions:

```text
Create folder /home/alex/Reports
Copy it to /home/alex/Archive
Move it to /home/alex/Archive
Write "A plain text note" to /home/alex/Reports/note.txt
```

Move and copy destinations must already be folders. Flow skips symbolic links when searching and refuses paths that traverse a symbolic link.

## Read and write text, JSON, and CSV

`Read` detects the format from the filename extension:

```text
Read /home/alex/notes.txt and call it notes
Read /home/alex/settings.json and call it settings
Read /home/alex/sales.csv and call it sales
```

Text is available as `content` (or the optional name after `and call it`). JSON is parsed into `data`. CSV is read as a list of dictionaries using its first row as headers; it is available as `rows`, `them`, and the optional name. CSV values are strings.

Write text or JSON:

```text
Write notes to /home/alex/notes-copy.txt
Write settings to /home/alex/settings-copy.json
```

A `.json` destination gets JSON serialization; all other destinations get UTF-8 text. Quote literal text:

```text
Write "This is text, not Flow code" to /home/alex/message.txt
```

Filter and save CSV rows:

```text
Read /home/alex/sales.csv

If there are rows where status is "Pending"
    Save those rows to /home/alex/reports/pending.csv
    Show "Pending report created"
Otherwise
    Show "No pending orders found"
End
```

## Re-run a workflow with `force`

By default, Flow refuses to overwrite an existing file or folder. This protects data and makes accidental reruns visible. Add the explicit `force` keyword when replacing an existing output is intended:

```text
Save those rows to /home/alex/reports/pending.csv force
Write "Fresh report" to /home/alex/reports/summary.txt force
Write settings to /home/alex/settings.json force
```

`force` replaces existing text, JSON, or CSV output files. It also replaces a conflicting destination in a `Move` or `Copy` instruction:

```text
Copy it to /home/alex/Archive force
```

For a forced move/copy collision, Flow removes the old destination before copying or moving the source into place. This can permanently delete the old destination contents and cannot be automatically rolled back. Review `flow preview` before using `force`. It cannot replace a folder with a file or a file with a folder.

The provided [conditions.flow](conditions.flow) example uses `force` on its generated CSV report so it can be run repeatedly.

## Errors and troubleshooting

Flow reports syntax/runtime errors with the script line and a useful explanation. Common cases:

* `Unknown value 'total'`: spelling/capitalization does not match a value previously assigned.
* `... is not a valid number`: enter a whole number, decimal, or scientific notation value.
* `Destination already exists`: use a new path or add `force` only if replacement is intended.
* `Destination folder does not exist`: create it first or add an `If ... does not exist` block with `Create folder`.
* `Loop source is not a folder or list`: use an existing folder or list variable.
* `block is missing End`: add an `End` at the same indentation as the opening `If`, `For each`, or `Repeat`.
* `Could not read ...`: check the path, file permissions, UTF-8 encoding for text, or file syntax (especially JSON).

Line numbers refer to the `.flow` source. If a script reports an error, fix the stated instruction and preview again before running it.

## Safety notes

Flow scripts can access absolute paths named in the script. Run only scripts you trust. Preview destructive or bulk operations. `force` explicitly authorizes replacement; a forced directory replacement deletes the old destination contents. Flow is not an OS sandbox and does not yet provide configurable allowed-directory permissions.

The current runtime does not support shell commands, network calls, credential access, scheduling, file watchers, or AI-authored execution. Those should not be assumed to work even if a script describes them.

## More examples and reference

* [Calculator](examples/calculator.flow)
* [Organize downloads](examples/organize-downloads.flow)
* [Create a CSV report](examples/csv-report.flow)
* [Language specification](docs/language-spec.md)
* [Safety model](docs/safety-model.md)
