from datetime import datetime
from io import BytesIO

import streamlit as st

from db import add_expense, delete_expense, get_expenses, get_stats, init_db
from exporter import export_expenses_to_excel
from models import CATEGORIES
from services import format_currency, prepare_expense_rows, prepare_stats_dataframe


def main() -> None:
    init_db()

    st.set_page_config(page_title="记账工具", page_icon="💰", layout="wide")
    st.title("💰 个人记账工具")
    st.caption("使用 Streamlit + SQLite 管理你的消费记录")

    st.subheader("📝 添加账目")
    with st.form("add_expense_form"):
        col1, col2 = st.columns(2)
        with col1:
            amount = st.number_input("金额", min_value=0.0, step=0.01, format="%.2f")
            category = st.selectbox("分类", CATEGORIES)
        with col2:
            expense_date = st.date_input("日期")
            note = st.text_area("备注", placeholder="例如：午餐、地铁、日用品")

        submitted = st.form_submit_button("添加账目", use_container_width=True)
        if submitted:
            if amount <= 0:
                st.warning("金额必须大于 0")
            else:
                add_expense(float(amount), category, expense_date.strftime("%Y-%m-%d"), note.strip())
                st.success("已添加账目")
                st.rerun()

    st.subheader("📤 导出账单")
    export_mode = st.radio("导出范围", ["当前月份", "全年", "自定义月份组合"], horizontal=True)
    export_year = st.number_input("年份", min_value=2000, max_value=2100, value=datetime.now().year)
    if export_mode == "当前月份":
        current_month = datetime.now().month
        selected_months = [current_month]
    elif export_mode == "全年":
        selected_months = list(range(1, 13))
    else:
        selected_months = st.multiselect("选择月份", list(range(1, 13)), default=[datetime.now().month])

    if st.button("生成 Excel 导出", use_container_width=True):
        buffer = BytesIO()
        export_expenses_to_excel(buffer, months=selected_months, year=int(export_year))
        buffer.seek(0)
        st.download_button(
            label="下载 Excel 账单",
            data=buffer.getvalue(),
            file_name=f"expense_report_{export_year}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.subheader("账目列表")
    col1, col2 = st.columns(2)
    with col1:
        month_options = [("全部", None)] + [(f"{i}月", i) for i in range(1, 13)]
        month_label, month_value = st.selectbox(
            "按月份筛选",
            month_options,
            format_func=lambda option: option[0],
        )
    with col2:
        category_filter = st.selectbox("按分类筛选", ["全部"] + CATEGORIES)

    expenses = get_expenses(
        month=month_value,
        category=category_filter if category_filter != "全部" else None,
    )

    if expenses:
        display_rows = prepare_expense_rows(expenses)
        st.dataframe(display_rows, use_container_width=True, hide_index=True)

        delete_id = st.number_input("输入要删除的账目 ID", min_value=1, step=1, key="delete_id")
        if st.button("删除账目"):
            delete_expense(int(delete_id))
            st.success("已删除账目")
            st.rerun()
    else:
        st.info("暂无账目记录")

    st.subheader("分类统计")
    stats = get_stats()
    if stats:
        stats_df = prepare_stats_dataframe(stats)
        display_stats_df = stats_df.copy()
        display_stats_df["总额"] = display_stats_df["总额"].map(lambda value: format_currency(value))
        chart_data = stats_df.set_index("分类")
        st.bar_chart(chart_data)
        st.dataframe(display_stats_df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无统计数据")


if __name__ == "__main__":
    main()
