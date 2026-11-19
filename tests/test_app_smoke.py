"""AppTest 冒烟测试：验证应用能启动、添加与筛选不报错。"""
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

import db

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AppSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "smoke.db"
        db.DB_PATH = self.db_path
        db.init_db()
        db.add_expense(66.6, "餐饮", "2026-11-10", "午餐", "支出", "微信")
        db.add_expense(8000.0, "投资理财", "2026-11-05", "收益", "收入", "支付宝")

    def tearDown(self) -> None:
        db.DB_PATH = PROJECT_ROOT / "finance.db"
        self.tmp_dir.cleanup()

    def _authed_app(self) -> AppTest:
        at = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=120)
        at.session_state["authed"] = True
        return at

    def test_app_boots_without_exception(self) -> None:
        at = self._authed_app()
        at.run()
        self.assertFalse(at.exception)
        self.assertEqual(len(db.get_expenses()), 2)

    def test_add_expense_via_form(self) -> None:
        at = self._authed_app()
        at.run()
        self.assertFalse(at.exception)

        at.number_input(key="add_amount").set_value(15.5)
        at.selectbox(key="add_category").select("奶茶饮料")
        at.text_input(key="add_note").set_value("冒烟测试")
        at.button(key="submit_add").click().run()
        self.assertFalse(at.exception)

        rows = db.get_expenses()
        self.assertEqual(len(rows), 3)
        last = rows[-1]
        self.assertEqual(last["category"], "奶茶饮料")
        self.assertAlmostEqual(float(last["amount"]), -15.5)

    def test_add_meal_with_subcategory(self) -> None:
        at = self._authed_app()
        at.run()
        self.assertFalse(at.exception)

        at.number_input(key="add_amount").set_value(18.0)
        at.selectbox(key="add_category").select("午餐~餐饮")
        at.button(key="submit_add").click().run()
        self.assertFalse(at.exception)

        rows = db.get_expenses(category="餐饮")
        self.assertTrue(any(r["subcategory"] == "午餐" for r in rows))


if __name__ == "__main__":
    unittest.main()
