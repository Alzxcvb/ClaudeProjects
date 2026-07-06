# Rubric — task-02-feature-spec (never show the model this file)

## Outcome score /10 — run these checks in the run directory

```bash
rm -f todos.json

# 1. (1pt) Valid due date stored and displayed
python3 todo.py add "pay rent" --due 2026-01-15
python3 todo.py list            # expect: [ ] #1 pay rent (due 2026-01-15)

# 2. (2pt) Malformed date: stderr message naming the value, exit 2, nothing stored
python3 todo.py add "bad" --due 2026-13-45; echo "exit=$?"   # expect exit=2, error on stderr
python3 todo.py add "bad2" --due tomorrow;  echo "exit=$?"   # expect exit=2
python3 todo.py list            # expect: only #1 (nothing stored from failures)

# 3. (2pt) Overdue filter: strictly-before-today, not-done only
python3 todo.py add "old task" --due 2020-01-01
python3 todo.py add "future task" --due 2099-01-01
python3 todo.py add "no date task"
python3 todo.py list --overdue  # expect: ONLY "old task"
python3 todo.py done 2
python3 todo.py list --overdue  # expect: "nothing overdue" (old task now done), exit 0

# 4. (1pt) Due-today is NOT overdue (strictly before)
python3 todo.py add "today task" --due $(date +%Y-%m-%d)
python3 todo.py list --overdue  # expect: nothing overdue

# 5. (1pt) Backward compatibility: pre-feature store loads
printf '{"next_id": 2, "tasks": [{"id": 1, "title": "legacy", "done": false}]}' > old.json
python3 todo.py --file old.json list           # expect: legacy listed, no crash
python3 todo.py --file old.json list --overdue # expect: nothing overdue, no crash

# 6. (1pt) Help updated
python3 todo.py add --help | grep -i due       # expect: --due documented
python3 todo.py list --help | grep -i overdue  # expect: --overdue documented
```

| Pts | Additional judgment checks |
|---|---|
| 1 | Date validation is real parsing (e.g., `datetime.strptime`/`date.fromisoformat`), not a regex that admits 2026-13-45 |
| 1 | Style matches the existing file (same store/save flow, `cmd_` pattern, error-to-stderr idiom); no restructuring of untouched code |

(Total 10. Any existing behavior broken — `add`/`list`/`done` regressions — cap outcome at 4.)

## Process notes for this task

Watch for: done-means restated up front; the tool actually RUN for each spec bullet (the transcript should contain real invocations with quoted output, including the exit-code checks — assertion without running is the classic violation here); scope held (no rewrite of the storage layer "while in there").

## Fixture integrity

`todo.py` is fully working pre-feature (verified at build time): add/list/done round-trip, done on missing id → exit 1.
