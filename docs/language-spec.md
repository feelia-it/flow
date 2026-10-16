# Flow language specification

Flow is parsed into a syntax tree and evaluated by a deterministic local runtime. Keywords are case-insensitive; variable names are case-sensitive. Indent each nested block with four spaces. Every `If` requires a matching `End`; `Otherwise` is optional.

## Statements

```text
In /path/to/folder
Ask for a number and call it total
Ask for another number and call it second
Ask for a string and call it name
Ask for an operator and call it operation
Ask "What is your name?" and call it name
Set answer to total + second
Show "The answer is:"
Show answer
Show /home/user/Documents
Create folder /reports
Move it to /archive
Copy them to /archive
Write "Hello" to /reports/hello.txt
Write "Replace me" to /reports/hello.txt force
Read /sales.csv
Read /settings.json
Read /notes.txt
Read /notes.txt and call it notes
Save those rows to /reports/pending.csv force
For each folder in /home/user/Projects
    Show it
End
Repeat 3 times
    Show iteration
End
```

Paths may be absolute or relative to the most recent `In` folder. Quoted strings are treated as data, never as code. Expressions allow numeric/text constants, variables, parenthesized arithmetic, `+`, `-`, `*`, `/`, `//`, `%`, `**`, unary signs, comparisons, boolean operators, and dictionary/list subscription such as `row["status"]`. An operator asked into a variable can appear between expression operands (for example, `left operation right`); its value is validated against the supported arithmetic operators. No calls, attribute access, or arbitrary Python execution are supported.

## Conditions

```text
If /reports does not exist
    Create folder /reports
End

If there is a folder containing any of ["Accounts", "Payments"]
    Move it to /archive
Otherwise
    Show "Nothing matched"
End

If there is a PDF
    Copy it to /documents
End

If there are rows where status is "Pending"
    Save those rows to /reports/pending.csv
End

If total >= 10
    Show total
End

For each file in /home/user/Downloads
    Show it
End

For each row in rows
    Show row["status"]
End

Repeat 3 times
    Show iteration
End
```

Matching searches only the immediate contents of the active `In` folder. Word matching is case-insensitive against the entry name. Extension matching checks files only. A folder/file match runs the body once per match; `it` is the current entry and `them` is the matching collection. CSV filtering binds the matching rows to `them` and executes its body once, so `Save those rows` writes the complete filtered set. `result` is updated by input, `Set`, and CSV reads; conditions do not overwrite it.

`Read` reads UTF-8 `.csv` files with a header row into `rows`, `.json` files into `data`, and other files as text into `content`. CSV field values remain strings. `Save those rows` writes the header and filtered records. `Write` serializes a value as JSON when its destination ends in `.json`; otherwise it writes text.

`For each` iterates over the immediate files/folders in a folder, or over a list variable. `Repeat` runs a fixed integer count. Both forms are capped at 10,000 iterations. `Show /path/to/folder` lists the immediate entries; `Show /path/to/file.txt` prints its UTF-8 text.

`force` is supported on `Write`, `Save those rows`, `Move`, and `Copy`. It replaces an existing destination. Replacing a directory removes its previous contents and is not automatically reversible. Without `force`, writes and transfers refuse collisions.

Scheduling (`Every`), triggers (`When`), and nested script execution (`Run`) are intentionally unsupported and are reported as such.
