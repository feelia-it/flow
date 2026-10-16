# Flow safety model (v0.1)

Flow only executes instructions represented by its parsed syntax tree. It has no shell command, import, network, credential, or AI-execution feature.

* `preview` runs the same matching and condition logic but performs no filesystem writes or moves. It reports planned changes and ends with `No files changed.`
* Existing move, copy, text-write, and CSV-write destinations are rejected unless the script explicitly uses `force`.
* `force` on a move or copy can delete an existing destination directory and all its contents. This is reported in preview but cannot be rolled back automatically.
* File and folder matching is limited to the immediate `In` directory. Matched symlinks and paths traversing symlinks are rejected/skipped.
* Move/copy operations report the source and destination. Replacing a file output is atomic where the platform supports it. A failed action reports its script line and does not claim success. Earlier actions in a multi-step script are not automatically rolled back.
* User scripts can name absolute paths, so only run scripts you trust. Preview a script before running it.

This is a first milestone, not an OS-level sandbox or a permission broker. A future version should add configurable capability roots and explicit permission prompts before claiming stronger isolation.
