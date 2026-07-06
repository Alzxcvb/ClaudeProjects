# Task: Add due dates and an overdue filter to the todo CLI

`todo.py` is a working command-line todo tool with JSON file storage. Try it:

```bash
python3 todo.py add "buy milk"
python3 todo.py list
python3 todo.py done 1
```

## Feature spec

1. `add` accepts an optional `--due YYYY-MM-DD` flag storing a due date with the task.
2. A new `list --overdue` flag shows only tasks that are (a) not done AND (b) have a due date strictly before today.
3. `list` (with and without `--overdue`) shows the due date next to any task that has one, in the format `(due 2026-07-01)`.

## Done means

- `--due` with a malformed or impossible date (e.g., `2026-13-45`, `tomorrow`) prints an error naming the bad value to **stderr** and exits with code **2**, storing nothing.
- Tasks without a due date are never overdue and never shown by `list --overdue`.
- `list --overdue` on a store with no overdue tasks prints `nothing overdue` and exits 0.
- Existing behavior and the existing storage file format remain backward compatible: a `todos.json` created before this change still loads (tasks in it simply have no due date).
- `--help` output for `add` and `list` documents the new flags.

Keep the existing code style. Verify your work by running the tool.
