#!/usr/bin/env python3
"""orders-service startup stub: load config, simulate a DB connection."""

import json
import os
import sys
from urllib.parse import urlparse

CONFIG_PATH = os.environ.get("APP_CONFIG", "config/settings.json")


def load_config():
    with open(CONFIG_PATH) as f:
        raw = json.load(f)
    pool_size = int(raw.get("pool_size", 5))
    if not 1 <= pool_size <= 50:
        raise ValueError(f"pool_size out of range: {pool_size}")
    return {"database_url": raw["database_url"], "pool_size": pool_size}


def connect(url, pool_size):
    parsed = urlparse(url)
    if parsed.scheme != "postgres":
        raise ValueError(f"unsupported database scheme: {parsed.scheme!r}")
    if not parsed.hostname:
        raise ValueError("database url has no hostname")
    return (
        f"connected to {parsed.hostname}:{parsed.port or 5432} "
        f"pool={pool_size} (simulated)"
    )


def main():
    try:
        config = load_config()
    except FileNotFoundError:
        print(f"fatal: config file not found: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    except KeyError as exc:
        print(f"fatal: missing config key: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"config loaded from {CONFIG_PATH}")

    try:
        print(connect(config["database_url"], config["pool_size"]))
    except ValueError as exc:
        print(f"fatal: cannot connect: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
