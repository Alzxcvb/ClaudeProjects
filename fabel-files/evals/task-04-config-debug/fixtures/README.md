# orders-service (simulated)

A stub of our orders service used for local testing. It reads its settings and simulates a database connection at startup.

## Configuration contract

Settings live in `config/settings.json`. Keys (snake_case):

| Key | Type | Meaning |
|---|---|---|
| `database_url` | string | Postgres connection URL, scheme `postgres://` |
| `pool_size` | int | Connection pool size, 1–50 |

The config file path can be overridden with the `APP_CONFIG` environment variable.

## Expected startup output

```
$ python3 app.py
config loaded from config/settings.json
connected to db.internal.example:5433 pool=10 (simulated)
```

Exit code 0.
