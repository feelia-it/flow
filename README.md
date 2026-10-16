# Flow

**Automation that reads like instructions.**

Flow is a simple, readable automation language for everyday tasks. Write instructions in plain language to organize files, process documents, work with CSV and JSON data, perform calculations, generate reports, and automate repetitive workflows.

Instead of writing a full Python script, describe what you want to happen. Flow interprets the instructions it supports and executes them locally, with a preview mode to help you inspect file operations before making changes.

```text
Ask for a number and call it first
Ask for another number and call it second

Set total to first + second

Show "The total is:"
Show total
```

**Readable scripts. Practical automation. More control over your files.**

[Learn to Flow](learn-to-flow.md) · [Examples](examples/) · [Report a bug](https://github.com/feelia-it/flow/issues)

---

## Table of contents

- [Why Flow?](#why-flow)
- [Features](#features)
- [Getting started](#getting-started)
- [Your first workflow](#your-first-workflow)
- [Preview before running](#preview-before-running)
- [What can you automate?](#what-can-you-automate)
- [Language overview](#language-overview)
- [Project structure](#project-structure)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Why Flow?

Everyday automation shouldn't require a large script or extensive programming knowledge.

Flow provides a straightforward way to describe common tasks using readable instructions. It is designed for people who want to automate useful work without dealing with the complexity of a general-purpose programming language.

- **Readable by design:** Write instructions that are easier to understand and maintain.
- **Useful for everyday work:** Automate file organization, document processing, calculations, and reports.
- **Previewable:** Inspect planned file operations before executing them.
- **Local execution:** Run workflows on your own machine.
- **Built-in control flow:** Use conditions, loops, variables, and expressions to build flexible automations.
- **Focused execution:** Flow executes the instructions and expressions its interpreter supports rather than arbitrary Python code.

## Features

### File and folder automation

Organize directories, find matching files and folders, create folders, copy files, and move items between locations.

### Data and document processing

Read and write supported text and JSON files, load CSV records, filter rows, and save processed results.

### Calculations and expressions

Work with numbers, arithmetic, comparisons, and boolean expressions to automate decisions and calculations.

### Conditions and loops

Use `If`, `Otherwise`, `For each`, and `Repeat` to handle different situations and process multiple items.

### Interactive input and output

Ask users for values, display results, and build workflows that adapt to the information provided.

### Preview-first workflow

Use `flow preview` to inspect planned file operations without changing files. This helps you verify a workflow before running it.

## Getting started

### Requirements

- Python 3.12 or newer
- A terminal or command prompt

### 1. Clone the repository

```bash
git clone https://github.com/feelia-it/flow.git
cd flow
```

### 2. Install Flow

Install the project and its command-line interface:

```bash
python -m pip install .
```

### 3. Verify your installation

Check that the `flow` command is available:

```bash
flow --help
```

### 4. Run an example

Preview an example workflow first:

```bash
flow preview examples/organize-downloads.flow
```

If the preview looks correct, execute it:

```bash
flow run examples/organize-downloads.flow
```

For a complete introduction to the language, see the [Learn to Flow guide](learn-to-flow.md).

## Your first workflow

Create a file named `addition.flow`:

```text
Ask for a number and call it first
Ask for another number and call it second

Set total to first + second

Show "The total is:"
Show total
```

Run the script:

```bash
flow run addition.flow
```

Flow asks for two numbers, calculates their sum, and displays the result.

### A workflow with a condition

Flow supports conditional instructions, allowing a script to make decisions based on its values.

```text
Ask for a number and call it total

If total >= 100
    Show "Large amount"
Otherwise
    Show "Standard amount"
End
```

### A workflow that processes CSV data

You can read CSV files and work with their rows.

```text
Read sales.csv and call it sales

For each row in sales
    Show row["status"]
End
```

This example displays the `status` value for each row in `sales.csv`, assuming the file contains a `status` column.

For more examples covering expressions, file operations, loops, JSON, and CSV processing, see the [Learn to Flow guide](learn-to-flow.md) and the [`examples/`](examples/) directory.

## Preview before running

File automation can change or move important data. Flow includes a preview mode so you can inspect planned file operations before executing a workflow.

```bash
flow preview examples/organize-downloads.flow
```

Preview runs the workflow logic without creating, overwriting, copying, or moving files. It prints the planned file operations and finishes with `No files changed.`

When you are satisfied with the plan, run the workflow:

```bash
flow run examples/organize-downloads.flow
```

**Recommended workflow:** Preview first, review the planned changes, then execute.

## What can you automate?

| Use case | Example |
| --- | --- |
| File organization | Sort files and move matching folders |
| Document handling | Read and write text files |
| Data processing | Read CSV and JSON data |
| Reporting | Filter records and save results |
| Calculations | Perform arithmetic and comparisons |
| Repetitive tasks | Repeat instructions across files or records |
| Interactive workflows | Ask questions and use the answers in calculations |

## Language overview

Flow uses a small set of readable instructions to express common automation tasks.

| Instruction | Purpose |
| --- | --- |
| `Ask` | Request input from the user |
| `Set` | Store or calculate a value |
| `Show` | Display a value, file, or folder contents |
| `Read` | Read supported files |
| `Write` | Write text or JSON data |
| `In` | Set the working folder |
| `If` / `Otherwise` / `End` | Execute conditional instructions |
| `For each` | Iterate over files, folders, or collections |
| `Repeat` | Repeat instructions a specified number of times |
| `Create folder` | Create a directory |
| `Copy` | Copy a matched item |
| `Move` | Move a matched item |

Flow supports arithmetic operators, comparisons, boolean logic, and expressions involving stored values. It also supports file and folder matching, including checks for existence and matching names.

For detailed syntax, supported expressions, file operations, and practical examples, consult the **[Learn to Flow guide](learn-to-flow.md)**.

## Project structure

```text
flow/
├── src/
│   └── flow/          # Flow implementation
├── examples/          # Example workflows
├── tests/             # Automated tests
├── docs/              # Project documentation
├── demoCSV/           # CSV demonstration resources
├── learn-to-flow.md   # Language tutorial
├── conditions.flow    # Condition examples
├── pyproject.toml     # Python project configuration
├── LICENSE            # MIT license
└── README.md
```

## Development

Want to explore the implementation or contribute to Flow?

Clone the repository and install it locally:

```bash
git clone https://github.com/feelia-it/flow.git
cd flow
python -m pip install .
```

Run the test suite with `pytest`:

```bash
python -m pytest
```

To experiment with the language, create a `.flow` file and use `flow preview` before `flow run` whenever the workflow changes files.

## Contributing

Contributions, bug reports, and suggestions are welcome.

To contribute:

1. Explore the existing examples and documentation.
2. Open an issue to report a bug or discuss a proposed improvement.
3. Make your changes and add or update tests where appropriate.
4. Submit a pull request describing the change.

Please keep the language readable, the behavior predictable, and file operations easy to inspect.

- [Open an issue](https://github.com/feelia-it/flow/issues)
- [Browse the repository](https://github.com/feelia-it/flow)

## License

Flow is released under the [MIT License](LICENSE).

You are free to use, modify, and distribute the project in accordance with the license terms.
