#!/usr/bin/env python3
"""A minimal file-backed todo list CLI."""

import argparse
import json
import os
import sys

DEFAULT_STORE = "todos.json"


def load_store(path):
    if not os.path.exists(path):
        return {"next_id": 1, "tasks": []}
    with open(path) as f:
        return json.load(f)


def save_store(path, store):
    with open(path, "w") as f:
        json.dump(store, f, indent=2)


def cmd_add(args, store):
    task = {"id": store["next_id"], "title": args.title, "done": False}
    store["tasks"].append(task)
    store["next_id"] += 1
    print(f"added #{task['id']}: {task['title']}")
    return store


def cmd_list(args, store):
    tasks = store["tasks"]
    if not tasks:
        print("no tasks")
        return None
    for task in tasks:
        mark = "x" if task["done"] else " "
        print(f"[{mark}] #{task['id']} {task['title']}")
    return None


def cmd_done(args, store):
    for task in store["tasks"]:
        if task["id"] == args.id:
            task["done"] = True
            print(f"done #{task['id']}: {task['title']}")
            return store
    print(f"error: no task with id {args.id}", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="A minimal todo list.")
    parser.add_argument("--file", default=DEFAULT_STORE, help="storage file")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="add a task")
    p_add.add_argument("title")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="list tasks")
    p_list.set_defaults(func=cmd_list)

    p_done = sub.add_parser("done", help="mark a task done")
    p_done.add_argument("id", type=int)
    p_done.set_defaults(func=cmd_done)

    args = parser.parse_args()
    store = load_store(args.file)
    changed = args.func(args, store)
    if changed is not None:
        save_store(args.file, changed)


if __name__ == "__main__":
    main()
