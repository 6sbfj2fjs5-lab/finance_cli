from datetime import datetime
from io import BytesIO

import streamlit as st
import pandas as pd
import plotly.express as px

# Matplotlib font settings to avoid Chinese glyph missing warnings
import matplotlib
from matplotlib import rcParams, font_manager
import os

# Try to register a Chinese font from common Windows locations to avoid missing glyphs
_candidates = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyh.ttf",
    r"C:\Windows\Fonts\SimHei.ttf",
    r"C:\Windows\Fonts\SimSun.ttc",
    r"C:\Windows\Fonts\MSYH.TTC",
]
for _p in _candidates:
    if os.path.exists(_p):
        try:
            font_manager.fontManager.addfont(_p)
            name = font_manager.FontProperties(fname=_p).get_name()
            rcParams["font.sans-serif"] = [name]
            break
        except Exception:
            continue
else:
    rcParams["font.sans-serif"] = ["DejaVu Sans"]

rcParams["axes.unicode_minus"] = False

from db import (
    add_expense,
    delete_expense,
    get_expenses,
    update_expense_date,
    get_payment_stats,
    get_stats,
    get_type_stats,
    init_db,
)
from exporter import export_expenses_to_excel
from models import CATEGORIES, PAYMENT_METHODS, TRANSACTION_TYPES
from services import format_currency, prepare_expense_rows, prepare_stats_dataframe


def main() -> None:
    init_db()

    st.set_page_config(page_title="记账工具", page_icon="💰", layout="wide")
    st.title("💰 个人记账工具")
    st.caption("使用 Streamlit + SQLite 管理你的消费记录")

    col_form, col_list = st.columns([3, 7], gap="small")
    with col_form:
        st.subheader("📝 添加账目")
        with st.form("add_expense_form"):
            col1, col2 = st.columns(2)
            with col1:
                amount = st.number_input("金额", min_value=0.0, step=0.01, format="%.2f")
                transaction_type = st.selectbox("收支类型", TRANSACTION_TYPES)
                category = st.selectbox("分类", CATEGORIES)
            with col2:
                payment_method = st.selectbox("支付方式", PAYMENT_METHODS)
                expense_date = st.date_input("日期")
                note = st.text_area("备注", placeholder="例如：午餐、地铁、日用品")

            submitted = st.form_submit_button("添加账目", width="stretch")
            if submitted:
                if amount <= 0:
                    st.warning("金额必须大于 0")
                else:
                    add_expense(
                        float(amount),
                        category,
                        expense_date.strftime("%Y-%m-%d"),
                        note.strip(),
                        transaction_type,
                        payment_method,
                    )
                    st.success("已添加账目")
                    st.rerun()

    with col_list:
        st.subheader("账目列表")
        st.markdown(
            "<div id='expense-list-box'></div>"
            "<style>"
            "/* 表单行间距压缩 */"
            "form [data-testid='stElementContainer'] {margin-bottom:0.1rem !important;padding-bottom:0 !important;}"
            "form [data-testid='stHorizontalBlock'] {gap:0.5rem !important;}"
            "form [data-testid='stFormSubmitButton'] {margin-top:0 !important;padding-top:0 !important;}"
            "/* 筛选行边框盒子 */"
            "#expense-list-box + div {border:1px solid #e6e6e6;border-radius:8px;padding:4px;margin-bottom:8px;background:#ffffff;font-size:14px;}"
            "/* 压缩列间距 */"
            "#expense-list-box ~ div > div > div {padding-left:3px;padding-right:3px;}"
            "/* 单元格内容居中对齐 */"
            "#expense-list-box ~ div .stMarkdown,"
            "#expense-list-box ~ div .stDateInput,"
            "#expense-list-box ~ div .stDateInput>div,"
            "#expense-list-box ~ div .stDateInput>div>div,"
            "#expense-list-box ~ div .stButton,"
            "#expense-list-box ~ div .stButton>button {display:flex;align-items:center;justify-content:center;}"
            "/* 日期控件和按钮统一高度 */"
            "#expense-list-box ~ div .stDateInput>div>div,"
            "#expense-list-box ~ div .stButton>button,"
            "#expense-list-box ~ div .stDateInput input[type='date'] {height:22px;min-height:22px;line-height:22px;box-sizing:border-box;padding:1px 6px;font-size:14px;}"
            "/* 日期控件内部居中对齐 */"
            "#expense-list-box ~ div .stDateInput input,"
            "#expense-list-box ~ div .stDateInput input[type='date'] {vertical-align:middle;padding:1px 6px;margin-top:0 !important;font-size:14px;}"
            "/* 日期输入微调 */"
            "#expense-list-box ~ div .stDateInput input[type='date'] {transform:translateY(-2px);}"
            "/* 按钮基线对齐 */"
            "#expense-list-box ~ div .stButton>button {transform:translateY(0);padding-top:2px;padding-bottom:2px;height:24px;min-height:24px;font-size:14px;}"
            "/* 隐藏多余标签 */"
            "#expense-list-box ~ div .stDateInput label {display:none;margin:0;padding:0;}"
            "#expense-list-box ~ div .css-1y0tads {margin-top:0;}"
            "</style>",
            unsafe_allow_html=True,
        )
        col_month, col_type, col_payment, col_category = st.columns([1.2, 1, 1, 1])
        month_options = [("全部", None)] + [(f"{i}月", i) for i in range(1, 13)]
        month_label, month_value = col_month.selectbox(
            "按月份筛选",
            month_options,
            format_func=lambda option: option[0],
        )
        transaction_type_filter = col_type.selectbox("收支类型", ["全部"] + TRANSACTION_TYPES)
        payment_method_filter = col_payment.selectbox("支付方式", ["全部"] + PAYMENT_METHODS)
        category_filter = col_category.selectbox("按分类筛选", ["全部"] + CATEGORIES)

        expenses = get_expenses(
            month=month_value,
            category=category_filter if category_filter != "全部" else None,
            transaction_type=transaction_type_filter if transaction_type_filter != "全部" else None,
            payment_method=payment_method_filter if payment_method_filter != "全部" else None,
        )

        # 分页设置
        PAGE_SIZE = 10
        total_pages = max(1, (len(expenses) + PAGE_SIZE - 1) // PAGE_SIZE)
        if "page" not in st.session_state:
            st.session_state.page = 1
        if st.session_state.page > total_pages:
            st.session_state.page = total_pages

        if expenses:
            page_expenses = expenses[(st.session_state.page - 1) * PAGE_SIZE:st.session_state.page * PAGE_SIZE]

            def color_amount_html(val: str) -> str:
                if isinstance(val, str) and val.startswith("("):
                    return f"<span style='color:red'>{val}</span>"
                if isinstance(val, str) and val.startswith("¥"):
                    return f"<span style='color:green'>{val}</span>"
                return f"{val}"

            def color_payment_html(val: str) -> str:
                if val == "支付宝":
                    return f"<span style='color:#1E90FF;font-weight:bold'>{val}</span>"
                if val == "微信":
                    return f"<span style='color:#12B92A;font-weight:bold'>{val}</span>"
                return f"{val}"

            header_cols = st.columns([1, 2, 2, 2, 2, 2, 1, 1], vertical_alignment="center")
            headers = ["ID", "金额", "类型", "支付方式", "分类", "日期", "保存", "删除"]
            for col, text in zip(header_cols, headers):
                col.markdown(
                    f"<div style='text-align:center;font-weight:600;padding-bottom:4px;font-size:15px;color:#222;'>{text}</div>",
                    unsafe_allow_html=True,
                )

            for expense in page_expenses:
                row_cols = st.columns([1, 2, 2, 2, 2, 2, 1, 1], vertical_alignment="center")
                row_cols[0].markdown(
                    f"<div style='display:flex;align-items:center;justify-content:center;min-height:24px;padding:2px 4px;font-size:14px;color:#333;'>{expense['id']}</div>",
                    unsafe_allow_html=True,
                )
                display_amount = prepare_expense_rows([expense])[0]["金额"]
                row_cols[1].markdown(
                    f"<div style='display:flex;align-items:center;justify-content:center;min-height:24px;padding:2px 4px;font-size:14px;'>{color_amount_html(display_amount)}</div>",
                    unsafe_allow_html=True,
                )
                row_cols[2].markdown(
                    f"<div style='display:flex;align-items:center;justify-content:center;min-height:24px;padding:2px 4px;font-size:14px;color:#333;'>{expense.get('transaction_type', '支出')}</div>",
                    unsafe_allow_html=True,
                )
                payment_html = color_payment_html(expense.get("payment_method", "支付宝"))
                row_cols[3].markdown(
                    f"<div style='display:flex;align-items:center;justify-content:center;min-height:24px;padding:2px 4px;font-size:14px;color:#1E90FF;'>{payment_html}</div>",
                    unsafe_allow_html=True,
                )
                row_cols[4].markdown(
                    f"<div style='display:flex;align-items:center;justify-content:center;min-height:24px;padding:2px 4px;font-size:14px;color:#333;'>{expense.get('category', '其他')}</div>",
                    unsafe_allow_html=True,
                )
                date_key = f"edit_date_{expense['id']}"
                row_cols[5].markdown(
                    "<div style='display:flex;align-items:center;justify-content:center;min-height:20px;padding:0;'>",
                    unsafe_allow_html=True,
                )
                new_date = row_cols[5].date_input(
                    "",
                    value=datetime.strptime(expense["date"], "%Y-%m-%d"),
                    key=date_key,
                    label_visibility="collapsed",
                )
                row_cols[5].markdown("</div>", unsafe_allow_html=True)
                save_key = f"save_date_{expense['id']}"
                delete_key = f"delete_row_{expense['id']}"
                if row_cols[6].button("保存", key=save_key, use_container_width=True):
                    update_expense_date(expense["id"], new_date.strftime("%Y-%m-%d"))
                    st.success(f"已更新 ID {expense['id']} 的日期")
                    st.rerun()
                if row_cols[7].button("🗑️", key=delete_key, use_container_width=True):
                    delete_expense(expense["id"])
                    st.success(f"已删除 ID {expense['id']}")
                    st.rerun()
                # row separator to create a compact table look
                st.markdown("<div style='width:100%;border-top:1px solid #efefef;margin:6px 0;'></div>", unsafe_allow_html=True)

            # 分页控件
            col_prev, col_info, col_next = st.columns([1, 3, 1])
            prev_disabled = st.session_state.page <= 1
            next_disabled = st.session_state.page >= total_pages
            if col_prev.button("◀ 上一页", disabled=prev_disabled, use_container_width=True):
                st.session_state.page -= 1
                st.rerun()
            col_info.markdown(
                f"<div style='text-align:center;font-size:14px;padding-top:4px;'>第 {st.session_state.page} / {total_pages} 页（共 {len(expenses)} 条）</div>",
                unsafe_allow_html=True,
            )
            if col_next.button("下一页 ▶", disabled=next_disabled, use_container_width=True):
                st.session_state.page += 1
                st.rerun()
        else:
            st.info("暂无账目记录")

    export_col_title, export_col_mode, export_col_year, export_col_months, export_col_button = st.columns([1.2, 2.5, 1, 1.2, 1])
    export_col_title.markdown(
        "<div style='display:flex;align-items:center;height:100%;'><span style='font-size:28px;font-weight:bold;'>📤 导出账单</span></div>",
        unsafe_allow_html=True,
    )
    export_mode = export_col_mode.radio(
        "导出范围",
        ["当前月份", "全年", "自定义月份组合"],
        horizontal=True,
    )
    export_year = export_col_year.number_input(
        "年份", min_value=2000, max_value=2100, value=datetime.now().year
    )
    if export_mode == "当前月份":
        current_month = datetime.now().month
        selected_months = [current_month]
    elif export_mode == "全年":
        selected_months = list(range(1, 13))
    else:
        selected_months = export_col_months.multiselect(
            "选择月份", list(range(1, 13)), default=[datetime.now().month]
        )
    export_col_button.markdown(
        "<div style='display:flex;align-items:center;justify-content:center;height:100%;'><span style='font-size:0.95rem;font-weight:bold;color:#1E90FF;'>生成 Excel 导出</span></div>",
        unsafe_allow_html=True,
    )
    if export_col_button.button("立即导出", key="generate_excel", use_container_width=True):
        buffer = BytesIO()
        export_expenses_to_excel(buffer, months=selected_months, year=int(export_year))
        buffer.seek(0)
        st.download_button(
            label="下载 Excel 账单",
            data=buffer.getvalue(),
            file_name=f"expense_report_{export_year}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )

    st.subheader("分类统计")
    stats = get_stats()
    type_stats = get_type_stats()
    payment_stats = get_payment_stats()

    if stats:
        stats_df = prepare_stats_dataframe(stats)
        display_stats_df = stats_df.copy()
        display_stats_df["总额"] = display_stats_df["总额"].map(lambda value: format_currency(value))
        chart_data = stats_df.set_index("分类")
        st.write("按分类统计")
        st.bar_chart(chart_data)
        st.dataframe(display_stats_df, width="stretch", hide_index=True)

    # 将收支类型统计和支付方式统计并排展示，进一步缩小饼图并调整样式
    if type_stats or payment_stats:
        col_type, col_payment = st.columns(2)

        with col_type:
            st.markdown("**按收支类型统计**")
            if type_stats:
                type_df = prepare_stats_dataframe(
                    [{"category": item["type"], "total": item["total"]} for item in type_stats]
                )
                type_df["总额"] = type_df["总额"].map(lambda value: format_currency(value))
                vals = [float(item["total"]) for item in type_stats]
                labels = [item["type"] for item in type_stats]
                if any(vals):
                    df_chart = pd.DataFrame({"label": labels, "value": vals})
                    fig_plotly = px.pie(df_chart, values="value", names="label", hole=0)
                    fig_plotly.update_traces(textposition="inside", textinfo="percent+label", insidetextorientation="radial")
                    fig_plotly.update_layout(
                        title_text="收支类型分布",
                        title_x=0.5,
                        title_font_size=10,
                        legend=dict(orientation="h", y=-0.24, x=0.5, xanchor="center", font=dict(size=8)),
                        margin=dict(t=40, b=20, l=10, r=10),
                    )
                    st.plotly_chart(fig_plotly, use_container_width=False, width=280, height=300)
                else:
                    st.info("无收支类型数据")
                st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
                st.dataframe(type_df, width="stretch", hide_index=True)
            else:
                st.info("无收支类型数据")

        with col_payment:
            st.markdown("**按支付方式统计**")
            if payment_stats:
                payment_df = prepare_stats_dataframe(
                    [{"category": item["payment_method"], "total": item["total"]} for item in payment_stats]
                )
                payment_df["总额"] = payment_df["总额"].map(lambda value: format_currency(value))
                vals = [float(item["total"]) for item in payment_stats]
                labels = [item["payment_method"] for item in payment_stats]
                if any(vals):
                    df_chart2 = pd.DataFrame({"label": labels, "value": vals})
                    fig_plotly2 = px.pie(df_chart2, values="value", names="label", hole=0)
                    fig_plotly2.update_traces(textposition="inside", textinfo="percent+label", insidetextorientation="radial")
                    fig_plotly2.update_layout(
                        title_text="支付方式分布",
                        title_x=0.5,
                        title_font_size=10,
                        legend=dict(orientation="h", y=-0.24, x=0.5, xanchor="center", font=dict(size=8)),
                        margin=dict(t=40, b=20, l=10, r=10),
                    )
                    st.plotly_chart(fig_plotly2, use_container_width=False, width=280, height=300)
                else:
                    st.info("无支付方式数据")
                st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
                st.dataframe(payment_df, width="stretch", hide_index=True)
            else:
                st.info("无支付方式数据")

    if not (stats or type_stats or payment_stats):
        st.info("暂无统计数据")


if __name__ == "__main__":
    main()
