import copy
import io
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from contentcrm import cli
from contentcrm.config import DEFAULTS
from contentcrm.db import connect


class CrmTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db_path = self.dir / "test.db"
        self.cfg = copy.deepcopy(DEFAULTS)
        self.cfg["db_path"] = str(self.db_path)
        self.conn = connect(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def crm(self, *argv):
        """Run the real CLI against the test db; returns (exit_code, stdout, stderr).
        Points --config at a missing file so tests always see DEFAULTS, not
        whatever is in the project config.json."""
        self.conn.commit()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(
                ["--db", str(self.db_path), "--config", str(self.dir / "no-config.json")]
                + [str(a) for a in argv]
            )
        return code, out.getvalue(), err.getvalue()

    def one(self, sql, *params):
        return self.conn.execute(sql, params).fetchone()

    def count(self, table, where="1=1", *params):
        return self.conn.execute(
            f"SELECT COUNT(*) c FROM {table} WHERE {where}", params
        ).fetchone()["c"]
