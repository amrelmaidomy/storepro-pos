from contextlib import closing
from datetime import datetime
from pathlib import Path
import os
import sqlite3
import tempfile

from .db import VERSION, audit
from .auth import Auth


class Backup:
    def __init__(self, db):
        self.db = db

    def export(self, actor, destination):
        Auth(self.db).require(actor, "manage")
        return self.create(destination)

    def create(self, destination):
        destination = Path(destination)

        if destination.resolve() == self.db.path.resolve():
            raise ValueError("لا تستخدم قاعدة التشغيل كوجهة للنسخ")

        destination.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp = tempfile.mkstemp(
            prefix="backup-",
            suffix=".db",
            dir=destination.parent,
        )
        os.close(fd)

        try:
            with closing(self.db.connect()) as source:
                with closing(sqlite3.connect(tmp)) as target:
                    source.backup(target)

            # جميع الاتصالات أُغلقت قبل التحقق ونقل الملف.
            self.validate(tmp)
            os.replace(tmp, destination)
        finally:
            if Path(tmp).exists():
                Path(tmp).unlink()

        return destination

    def validate(self, path):
        path = Path(path)

        if not path.is_file():
            raise ValueError("ملف النسخة غير موجود")

        try:
            with closing(
                sqlite3.connect(
                    path.resolve().as_uri() + "?mode=ro",
                    uri=True,
                )
            ) as connection:
                if connection.execute(
                    "PRAGMA integrity_check"
                ).fetchone()[0] != "ok":
                    raise ValueError("النسخة تالفة")

                if connection.execute(
                    "PRAGMA user_version"
                ).fetchone()[0] != VERSION:
                    raise ValueError("إصدار النسخة غير متوافق")

                if connection.execute("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("علاقات النسخة غير سليمة")

                required = {
                    "users",
                    "products",
                    "sales",
                    "sale_items",
                    "purchases",
                    "purchase_items",
                    "stock_moves",
                    "shifts",
                    "cash_moves",
                    "parties",
                    "party_moves",
                    "returns",
                    "return_items",
                    "settings",
                    "audit",
                }

                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }

                if not required.issubset(tables):
                    raise ValueError("هذا ليس ملف StorePro كاملًا")

                with closing(self.db.connect()) as live:
                    for table in required:
                        expected = {
                            row["name"]
                            for row in live.execute(
                                f"PRAGMA table_info({table})"
                            )
                        }
                        actual = {
                            row[1]
                            for row in connection.execute(
                                f"PRAGMA table_info({table})"
                            )
                        }

                        if not expected.issubset(actual):
                            raise ValueError("مخطط النسخة غير متوافق")

        except sqlite3.DatabaseError as error:
            raise ValueError("ملف قاعدة بيانات غير صالح") from error

    def restore(self, actor, path):
        Auth(self.db).require(actor, "manage")
        path = Path(path)

        if path.resolve() == self.db.path.resolve():
            raise ValueError("اختر نسخة مختلفة عن قاعدة التشغيل")

        self.validate(path)

        stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        safety_backup = self.db.path.with_name(
            self.db.path.name + ".before-restore-" + stamp
        )
        self.create(safety_backup)

        fd, temp = tempfile.mkstemp(
            prefix="restore-",
            suffix=".db",
            dir=self.db.path.parent,
        )
        os.close(fd)

        try:
            with closing(
                sqlite3.connect(
                    path.resolve().as_uri() + "?mode=ro",
                    uri=True,
                )
            ) as source:
                with closing(sqlite3.connect(temp)) as target:
                    source.backup(target)

            # إغلاق المصدر والهدف قبل استبدال قاعدة التشغيل.
            self.validate(temp)
            os.replace(temp, self.db.path)

            with self.db.transaction() as connection:
                found = connection.execute(
                    "SELECT id FROM users WHERE id=?",
                    (actor,),
                ).fetchone()

                audit(
                    connection,
                    actor if found else None,
                    "database_restored",
                    path.name,
                )
        finally:
            if Path(temp).exists():
                Path(temp).unlink()

    def automatic(self, directory, keep=10):
        if type(keep) is not int or not 1 <= keep <= 100:
            raise ValueError("عدد النسخ بين 1 و100")

        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        path = directory / (
            "storepro-"
            + datetime.now().strftime("%Y%m%d-%H%M%S%f")
            + ".db"
        )
        self.create(path)

        backups = sorted(
            directory.glob("storepro-*.db"),
            key=lambda item: item.name,
            reverse=True,
        )

        for old in backups[keep:]:
            old.unlink()

        return path