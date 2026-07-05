import unittest
from pathlib import Path
from io import BytesIO

import db
import exporter


class StatsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path(__file__).resolve().parents[1] / "finance_test.db"
        if self.db_path.exists():
            self.db_path.unlink()

        db.DB_PATH = self.db_path
        db.init_db()
        # 添加支出与收入
        db.add_expense(50.0, "餐饮", "2026-07-03", "午餐", "支出", "支付宝")
        db.add_expense(100.0, "投资理财", "2026-07-04", "收益", "收入", "微信")

    def tearDown(self) -> None:
        # 尝试删除测试数据库文件，若被占用则忽略
        try:
            if self.db_path.exists():
                self.db_path.unlink()
        except PermissionError:
            pass

    def test_type_and_payment_stats(self) -> None:
        type_stats = db.get_type_stats()
        payment_stats = db.get_payment_stats()

        # 收支类型统计应包含 收入 与 支出
        types = {t["type"]: t["total"] for t in type_stats}
        self.assertIn("收入", types)
        self.assertIn("支出", types)
        # 支付方式统计应包含 支付宝 与 微信
        pays = {p["payment_method"]: p["total"] for p in payment_stats}
        self.assertIn("支付宝", pays)
        self.assertIn("微信", pays)

    def test_export_includes_sheets(self) -> None:
        buffer = BytesIO()
        exporter.export_expenses_to_excel(buffer, months=[7], year=2026)
        self.assertGreater(len(buffer.getvalue()), 0)