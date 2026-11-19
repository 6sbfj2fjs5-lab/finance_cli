"""个人记账工具（Python + Streamlit + SQLite）主页面。

功能：添加账目、列表筛选/分页/编辑/删除、KPI 概览、统计图表、导出 Excel/CSV。
"""
import os
from datetime import date, datetime, timedelta
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db import (
    add_expense,
    delete_expense,
    get_category_stats,
    get_day_summary,
    get_expenses,
    get_month_summary,
    get_monthly_trend,
    get_months,
    get_overall_summary,
    get_payment_stats,
    get_type_stats,
    init_db,
    update_expense,
)
from exporter import export_expenses_to_excel
from models import (
    CATEGORIES,
    CATEGORY_EMOJI,
    CATEGORY_SUBCATEGORIES,
    PAYMENT_COLORS,
    PAYMENT_METHODS,
    TRANSACTION_TYPES,
    TYPE_COLORS,
    category_emoji,
    category_label,
    category_options,
    parse_category_label,
)
from services import (
    expense_list_frame,
    format_currency,
    format_signed_currency,
    monthly_trend_frame,
    stats_table_frame,
    style_expense_list,
)

# ---------- 参考色板（dataviz 验证色，浅色模式） ----------
C_BLUE = "#2a78d6"
C_GREEN = "#0ca30c"   # 收入 / 正向
C_RED = "#e34948"     # 支出 / 负向
C_INK = "#0b0b0b"
C_INK_2 = "#52514e"
C_MUTED = "#898781"
C_GRID = "#e1e0d9"
C_VIOLET = "#6250d6"

PAGE_SIZE_OPTIONS = [10, 20, 50]
FILTER_KEYS = ("f_year", "f_month", "f_type", "f_pay", "f_cat", "f_date")

_GLOBAL_CSS = """
<style>
#MainMenu, footer, [data-testid="stToolbar"] {visibility: hidden;}
[data-testid="stHeader"] {background: transparent;}
.block-container {padding-top: 1.1rem; padding-bottom: 3rem; max-width: 1240px;}
div[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #e5eaf2 !important;
    border-radius: 14px !important;
    background: #ffffff;
    box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05);
}
.stButton > button {border-radius: 8px; font-weight: 600;}
.stTextInput input, .stNumberInput input, .stDateInput input,
.stTextArea textarea, [data-baseweb="select"] > div {border-radius: 8px;}
[data-testid="stDataFrame"] {font-size: 14px;}
</style>
"""


# ======================================================================
# 通用小组件
# ======================================================================

def _app_password() -> str:
    """访问密码：优先 Streamlit secrets，其次环境变量 APP_PASSWORD；未配置返回空串（本地免密）。"""
    try:
        secret = st.secrets.get("APP_PASSWORD")
        if secret:
            return str(secret)
    except Exception:
        pass
    return os.environ.get("APP_PASSWORD", "")


def _ensure_auth() -> bool:
    """访问密码门：未配置密码时（本地使用）直接放行；配置后同一浏览器会话只需输入一次。"""
    password = _app_password()
    if not password or st.session_state.get("authed"):
        return True

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<div style='height:50px'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("#### 🔐 请输入访问密码")
            st.caption("账目数据为个人隐私，输入密码后即可使用")
            with st.form("login_form"):
                pwd = st.text_input("密码", type="password", key="login_pwd")
                if st.form_submit_button("进入", type="primary", width="stretch"):
                    if pwd == password:
                        st.session_state["authed"] = True
                        st.rerun()
                    else:
                        st.error("密码错误，请重试")
    return False


def _kpi_card(label: str, value: str, sub: str, color: str, icon: str) -> str:
    return (
        f"<div style='background:#ffffff;border:1px solid #e5eaf2;border-radius:14px;"
        f"padding:14px 18px;box-shadow:0 1px 3px rgba(16,24,40,.05);'>"
        f"<div style='display:flex;align-items:center;gap:8px;'>"
        f"<span style='font-size:18px;line-height:1;'>{icon}</span>"
        f"<span style='color:#6b7280;font-size:13px;'>{label}</span></div>"
        f"<div style='font-size:25px;font-weight:700;color:{color};margin-top:6px;"
        f"font-variant-numeric:tabular-nums;'>{value}</div>"
        f"<div style='font-size:12px;color:#9ca3af;margin-top:4px;'>{sub}</div></div>"
    )


def _available_years() -> list[int]:
    years = {int(m[:4]) for m in get_months()}
    years.add(datetime.now().year)
    return sorted(years, reverse=True)


def _resolve_day_label(label: str, today: date) -> date:
    """把日期标签（今日/昨日/YYYY-MM-DD）解析为具体日期。"""
    if label == "今日":
        return today
    if label == "昨日":
        return today - timedelta(days=1)
    return datetime.strptime(label, "%Y-%m-%d").date()


def _day_label(target: date, today: date) -> str:
    """把具体日期转成标签：今天/昨天显示「今日/昨日」，其余显示 YYYY-MM-DD。"""
    if target == today:
        return "今日"
    if target == today - timedelta(days=1):
        return "昨日"
    return target.strftime("%Y-%m-%d")


def _shift_day(delta: int) -> None:
    """上一日/下一日翻页回调：在重跑前更新查看日期，并同步左侧添加表单的日期。"""
    base = datetime.now().date()
    label = st.session_state.get("f_date", "今日")
    if label == "全部":
        target = base - timedelta(days=1) if delta < 0 else base
    else:
        target = _resolve_day_label(label, base) + timedelta(days=delta)
        target = min(target, base)
    st.session_state["f_date"] = _day_label(target, base)
    st.session_state["add_date"] = target
    st.session_state["page"] = 1


def _base_layout(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="'Segoe UI', system-ui, 'Microsoft YaHei', sans-serif", size=13, color=C_INK),
        showlegend=False,
    )
    return fig


def _stats_column_config(entity_label: str) -> dict:
    return {
        "项目": st.column_config.TextColumn(entity_label),
        "笔数": st.column_config.NumberColumn("笔数", width="small"),
        "总额": st.column_config.NumberColumn("总额", format="¥%.2f", width="medium"),
        "占比": st.column_config.ProgressColumn("占比", format="%.1f%%", min_value=0.0, max_value=1.0),
    }


# ======================================================================
# 页面区块
# ======================================================================

def _render_hero(today: datetime, overall: dict) -> None:
    st.markdown(
        f"""
        <div style="background:linear-gradient(120deg,{C_BLUE} 0%,{C_VIOLET} 55%,#e87ba4 120%);
        border-radius:16px;padding:20px 28px;margin-bottom:14px;color:#ffffff;
        display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
          <div>
            <div style="font-size:25px;font-weight:800;letter-spacing:.5px;">💰 个人记账工具</div>
            <div style="font-size:13px;opacity:.9;margin-top:4px;">Python + Streamlit + SQLite · 记好每一笔，看清每一分</div>
          </div>
          <div style="text-align:right;font-size:13px;line-height:1.8;opacity:.95;">
            <div>📅 {today:%Y 年 %m 月 %d 日}</div>
            <div>🧾 累计 {overall['count']} 笔 · 结余 <b>{format_currency(overall['balance'])}</b></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpi(today: datetime) -> None:
    cur = get_month_summary(today.year, today.month)
    prev_day = today.replace(day=1) - timedelta(days=1)
    prev = get_month_summary(prev_day.year, prev_day.month)

    def _delta(current: float, previous: float) -> str:
        diff = current - previous
        arrow = "↑" if diff >= 0 else "↓"
        return f"较上月 {arrow} {format_currency(abs(diff))}"

    count_diff = cur["count"] - prev["count"]
    count_sub = f"较上月 {'+' if count_diff >= 0 else ''}{count_diff} 笔"
    balance_color = C_GREEN if cur["balance"] >= 0 else C_RED

    day = get_day_summary(today.strftime("%Y-%m-%d"))
    yday = get_day_summary((today - timedelta(days=1)).strftime("%Y-%m-%d"))
    day_diff = day["expense"] - yday["expense"]
    if day["count"] == 0:
        day_sub = "今天还没有记账 ✍️"
    else:
        day_arrow = "↑" if day_diff >= 0 else "↓"
        day_sub = f"较昨日 {day_arrow} {format_currency(abs(day_diff))} · 今日 {day['count']} 笔"

    cards = [
        _kpi_card("本月收入", format_currency(cur["income"]), _delta(cur["income"], prev["income"]), C_GREEN, "💰"),
        _kpi_card("本月支出", format_currency(cur["expense"]), _delta(cur["expense"], prev["expense"]), C_RED, "💸"),
        _kpi_card("本月结余", format_currency(cur["balance"]), _delta(cur["balance"], prev["balance"]), balance_color, "🏦"),
        _kpi_card("本月笔数", f"{cur['count']} 笔", count_sub, C_VIOLET, "🧾"),
        _kpi_card("今日支出", format_currency(day["expense"]), day_sub, C_RED, "🌤️"),
    ]
    st.markdown(
        f"<div style='display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:14px;'>"
        f"{''.join(cards)}</div>",
        unsafe_allow_html=True,
    )


def _render_add_form(today: date) -> None:
    with st.container(border=True):
        st.markdown("#### 📝 添加账目")
        # 分类放在表单外：餐饮类以「早餐~餐饮」小类~大类形式直接选择
        options = category_options()
        cat_label = st.selectbox(
            "分类", [opt[0] for opt in options], key="add_category",
            format_func=lambda label: f"{category_emoji(*parse_category_label(label))} {label}",
        )
        category, subcategory = parse_category_label(cat_label)
        with st.form("add_expense_form", border=False):
            transaction_type = st.segmented_control(
                "收支类型", TRANSACTION_TYPES, default="支出", key="add_type",
            )
            amount = st.number_input(
                "金额（元）", min_value=0.0, step=1.0, format="%.2f",
                placeholder="0.00", key="add_amount",
            )
            payment_method = st.segmented_control(
                "支付方式", PAYMENT_METHODS, default="支付宝", key="add_payment",
            )
            expense_date = st.date_input(
                "日期", value=st.session_state.get("add_date", today),
            )
            note = st.text_input("备注", placeholder="例如：午餐、地铁、给爸妈买礼物", key="add_note")
            submitted = st.form_submit_button("➕ 添加账目", type="primary", width="stretch", key="submit_add")
            if submitted:
                if amount <= 0:
                    st.warning("金额必须大于 0")
                else:
                    add_expense(
                        amount, category, expense_date.strftime("%Y-%m-%d"),
                        note.strip(), transaction_type, payment_method, subcategory,
                    )
                    # 添加后：表单日期保持为刚记账的日期，右侧列表也跳到该日期，
                    # 确保「记的哪天的账，就看哪天的列表」
                    today_d = datetime.now().date()
                    st.session_state["add_date"] = expense_date
                    st.session_state["f_date"] = _day_label(expense_date, today_d)
                    st.session_state["page"] = 1
                    st.session_state["flash"] = (
                        "success",
                        f"已添加：{cat_label} {format_currency(float(amount))}（{transaction_type} · {payment_method}）",
                    )
                    st.rerun()


def _render_list_section() -> None:
    with st.container(border=True):
        title_col, csv_col = st.columns([4, 1.2], gap="small", vertical_alignment="center")
        title_col.markdown("#### 📋 账目列表")

        # 筛选行：保持原默认「今日 · 支出」不变；在日期左侧新增上一日/下一日按钮，
        # 翻页浏览每日数据，点击翻页时同步左侧添加表单的日期；日期选"全部"时显示年份/月份
        years = _available_years()
        today = datetime.now()
        today_d = today.date()
        day_state = st.session_state.get("f_date", "今日")
        cat_state = st.session_state.get("f_cat")
        show_sub_filter = cat_state in CATEGORY_SUBCATEGORIES
        if show_sub_filter and st.session_state.get("f_sub") not in ["全部"] + CATEGORY_SUBCATEGORIES[cat_state]:
            st.session_state.pop("f_sub", None)  # 大类切换后清掉旧细分选择
        show_ym = day_state == "全部"

        col_specs = [0.7]  # 上一日/下一日（新增）
        col_specs += [1.1]  # 日期
        if show_ym:
            col_specs += [1, 1]  # 年份 月份
        col_specs += [1, 1, 1.2]  # 收支类型 支付方式 分类
        if show_sub_filter:
            col_specs += [1]  # 大类细分（餐饮/购物等）
        col_specs += [0.8]  # 重置

        fc = st.columns(col_specs, gap="small", vertical_alignment="bottom")
        col_idx = 0
        with fc[col_idx]:
            st.button(
                "◀", key="prev_day", width="stretch", help="查看前一天",
                on_click=_shift_day, args=(-1,),
            )
            st.button(
                "▶", key="next_day", width="stretch", help="查看后一天",
                on_click=_shift_day, args=(1,),
                disabled=day_state == "今日",
            )
        col_idx += 1

        # 日期下拉框保持原来的「今日/昨日/全部」三个选项；仅当翻页超出昨天时临时追加具体日期
        day_options = ["今日", "昨日", "全部"]
        if day_state not in day_options:
            day_options.append(day_state)
        f_date = fc[col_idx].selectbox(
            "日期", day_options, key="f_date",
            format_func=lambda label: {
                "今日": "今日", "昨日": "昨日", "全部": "全部",
            }.get(label, label[5:]),
        )
        col_idx += 1

        year = None
        month_label = "全部"
        if show_ym:
            year = fc[col_idx].selectbox("年份", years, key="f_year", index=years.index(today.year))
            col_idx += 1
            month_label = fc[col_idx].selectbox("月份", ["全部"] + [f"{m} 月" for m in range(1, 13)], key="f_month")
            col_idx += 1
        ttype = fc[col_idx].selectbox("收支类型", ["全部"] + TRANSACTION_TYPES, key="f_type", index=2)
        col_idx += 1
        pay = fc[col_idx].selectbox("支付方式", ["全部"] + PAYMENT_METHODS, key="f_pay")
        col_idx += 1
        cat = fc[col_idx].selectbox(
            "分类", ["全部"] + CATEGORIES, key="f_cat",
            format_func=lambda c: c if c == "全部" else f"{CATEGORY_EMOJI.get(c, '📦')} {c}",
        )
        col_idx += 1
        if show_sub_filter:
            sub = fc[col_idx].selectbox(
                f"{cat_state}细分", ["全部"] + CATEGORY_SUBCATEGORIES.get(cat_state, []), key="f_sub",
                format_func=lambda s: s if s == "全部" else f"{category_emoji(cat_state, s)} {category_label(cat_state, s)}",
            )
            col_idx += 1
        else:
            sub = "全部"
        reset_col = fc[col_idx]
        if reset_col.button("🔄 重置", width="stretch", key="reset_filters"):
            for k in FILTER_KEYS:
                st.session_state.pop(k, None)
            st.session_state.pop("f_sub", None)
            st.session_state.pop("add_date", None)  # 左侧表单日期回到今天
            st.session_state.pop("_last_filter", None)
            st.session_state["page"] = 1
            st.rerun()

        sub_value = sub if (cat in CATEGORY_SUBCATEGORIES and sub != "全部") else None
        if f_date != "全部":
            expenses = get_expenses(
                date_str=_resolve_day_label(f_date, today_d).strftime("%Y-%m-%d"),
                category=None if cat == "全部" else cat,
                transaction_type=None if ttype == "全部" else ttype,
                payment_method=None if pay == "全部" else pay,
                subcategory=sub_value,
            )
        else:
            month_value = int(month_label.split(" ")[0]) if month_label != "全部" else None
            expenses = get_expenses(
                month=f"{year}-{month_value:02d}" if month_value else None,
                year=year if month_value is None else None,
                category=None if cat == "全部" else cat,
                transaction_type=None if ttype == "全部" else ttype,
                payment_method=None if pay == "全部" else pay,
                subcategory=sub_value,
            )

        # 筛选变化时回到第 1 页
        filter_sig = (f_date, year, month_label, ttype, pay, cat, sub_value)
        if st.session_state.get("_last_filter") not in (None, filter_sig):
            st.session_state["page"] = 1
        st.session_state["_last_filter"] = filter_sig

        if not expenses:
            csv_col.markdown("")
            st.info("📭 没有符合条件的账目，去左侧添加第一笔吧～")
            return

        # 当前筛选结果导出 CSV
        csv_df = pd.DataFrame(
            [
                {
                    "ID": e["id"], "日期": e["date"], "收支类型": e["transaction_type"],
                    "分类": category_label(e["category"], e.get("subcategory") or ""),
                    "细分": e.get("subcategory") or "",
                    "支付方式": e["payment_method"], "金额": e["amount"], "备注": e["note"] or "",
                }
                for e in expenses
            ]
        )
        csv_bytes = csv_df.to_csv(index=False).encode("utf-8-sig")
        csv_col.download_button(
            "⬇️ CSV", data=csv_bytes,
            file_name=f"账目列表_{datetime.now():%Y%m%d_%H%M}.csv",
            mime="text/csv", width="stretch", key="csv_export",
            help="导出当前筛选结果的 CSV 文件",
        )

        # 分页
        df = expense_list_frame(expenses)
        page_size = st.session_state.get("page_size", PAGE_SIZE_OPTIONS[0])
        total = len(df)
        total_pages = max(1, -(-total // page_size))
        page = min(max(st.session_state.get("page", 1), 1), total_pages)
        st.session_state["page"] = page
        page_df = df.iloc[(page - 1) * page_size: page * page_size]

        st.dataframe(
            style_expense_list(page_df),
            hide_index=True,
            width="stretch",
            key="list_df",
            selection_mode="single-row",
            on_select="rerun",
        )

        # 选中行操作
        selected = None
        selection = st.session_state.get("list_df", {}).get("selection", {})
        sel_rows = selection.get("rows", [])
        if sel_rows and sel_rows[0] < len(page_df):
            sel_row = page_df.iloc[sel_rows[0]]
            sel_id = int(sel_row["ID"])
            raw = next((e for e in expenses if e["id"] == sel_id), None)
            if raw:
                selected = (raw, sel_row)

        act1, act2, act3 = st.columns([1.5, 1.5, 3], gap="small", vertical_alignment="center")
        if selected:
            raw, row = selected
            if act1.button(f"✏️ 编辑 ID {raw['id']}", width="stretch", key="edit_btn"):
                edit_dialog(raw)
            if act2.button(f"🗑️ 删除 ID {raw['id']}", width="stretch", key="delete_btn"):
                delete_dialog(raw)
            act3.markdown(
                f"<div style='font-size:13px;color:{C_MUTED};padding-top:6px;'>已选中：{row['日期']} · {row['分类']}"
                f" · {format_signed_currency(float(row['金额']))} · 备注：{row['备注'] or '无'}</div>",
                unsafe_allow_html=True,
            )
        else:
            act3.markdown(
                f"<div style='font-size:13px;color:{C_MUTED};padding-top:6px;'>"
                f"💡 单击表格中的任意一行，即可编辑或删除该账目</div>",
                unsafe_allow_html=True,
            )

        # 翻页
        nav1, nav2, nav3, nav4 = st.columns([1.1, 1.6, 1.1, 1], gap="small", vertical_alignment="center")
        if nav1.button("◀ 上一页", disabled=page <= 1, width="stretch", key="prev_page"):
            st.session_state["page"] = page - 1
            st.rerun()
        nav2.markdown(
            f"<div style='text-align:center;font-size:13px;color:{C_INK_2};padding-top:6px;'>"
            f"第 <b>{page}</b> / {total_pages} 页 · 共 {total} 条</div>",
            unsafe_allow_html=True,
        )
        if nav3.button("下一页 ▶", disabled=page >= total_pages, width="stretch", key="next_page"):
            st.session_state["page"] = page + 1
            st.rerun()
        nav4.selectbox("每页", PAGE_SIZE_OPTIONS, key="page_size", label_visibility="collapsed")


@st.dialog("✏️ 编辑账目")
def edit_dialog(exp: dict) -> None:
    st.markdown(f"账目 ID：**{exp['id']}**（原记录于 {exp['date']}）")
    # 分类放在表单外：餐饮类以「早餐~餐饮」小类~大类形式直接选择
    options = category_options()
    labels = [opt[0] for opt in options]
    current_label = category_label(exp.get("category", "其他"), exp.get("subcategory") or "")
    cat_index = labels.index(current_label) if current_label in labels else 0
    cat_label = st.selectbox(
        "分类", labels, index=cat_index, key=f"edit_cat_{exp['id']}",
        format_func=lambda label: f"{category_emoji(*parse_category_label(label))} {label}",
    )
    category, subcategory = parse_category_label(cat_label)
    with st.form("edit_form", border=False):
        c1, c2 = st.columns(2, gap="small")
        transaction_type = c1.segmented_control(
            "收支类型", TRANSACTION_TYPES, default=exp.get("transaction_type", "支出"),
        )
        payment_method = c2.segmented_control(
            "支付方式", PAYMENT_METHODS, default=exp.get("payment_method", "支付宝"),
        )
        try:
            amount_value = abs(float(exp.get("amount", 0.0)))
        except (TypeError, ValueError):
            amount_value = 0.0
        amount = st.number_input("金额（元）", min_value=0.0, step=1.0, format="%.2f", value=amount_value)
        try:
            default_date = datetime.strptime(exp["date"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            default_date = datetime.now().date()
        expense_date = st.date_input("日期", value=default_date)
        note = st.text_input("备注", value=exp.get("note") or "")
        if st.form_submit_button("💾 保存修改", type="primary", width="stretch"):
            if amount <= 0:
                st.warning("金额必须大于 0")
            else:
                update_expense(
                    exp["id"], amount, category, transaction_type, payment_method,
                    expense_date.strftime("%Y-%m-%d"), note.strip(), subcategory,
                )
                st.session_state["flash"] = ("success", f"已更新账目 ID {exp['id']}")
                st.rerun()


@st.dialog("🗑️ 删除账目")
def delete_dialog(exp: dict) -> None:
    try:
        display_amount = abs(float(exp.get("amount") or 0))
    except (TypeError, ValueError):
        display_amount = 0.0
    st.markdown(
        f"确定要删除 ID **{exp['id']}** 的账目吗？此操作不可恢复。\n\n"
        f"📌 {exp['date']} · {category_label(exp['category'], exp.get('subcategory') or '')} · "
        f"{format_currency(display_amount)} · "
        f"{exp.get('transaction_type', '支出')} · {exp.get('payment_method', '支付宝')}"
    )
    c1, c2 = st.columns(2, gap="small")
    if c1.button("🗑️ 确认删除", width="stretch"):
        delete_expense(exp["id"])
        st.session_state["flash"] = ("success", f"已删除账目 ID {exp['id']}")
        st.rerun()
    if c2.button("取消", width="stretch"):
        st.rerun()


# ======================================================================
# 统计图表
# ======================================================================

def _donut_chart(rows: list[dict], name_key: str, color_map: dict, center_label: str) -> go.Figure:
    labels = [r[name_key] for r in rows]
    values = [float(r["total"]) for r in rows]
    total = sum(values)
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.58,
            sort=False,
            marker=dict(
                colors=[color_map.get(l, "#9ec5f4") for l in labels],
                line=dict(color="#ffffff", width=2),
            ),
            textinfo="percent+label",
            textposition="inside",
            insidetextorientation="horizontal",
            textfont=dict(size=12, color="#ffffff"),
            hovertemplate="%{label}<br>¥%{value:,.2f} · %{percent}<extra></extra>",
        )
    )
    fig.add_annotation(
        x=0.5,
        y=0.5,
        showarrow=False,
        align="center",
        text=(
            f"<span style='font-size:12px;color:{C_MUTED}'>{center_label}</span>"
            f"<br><b style='font-size:17px;color:{C_INK}'>{format_currency(total)}</b>"
        ),
    )
    _base_layout(fig, 370)
    fig.update_layout(
        legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center", font=dict(size=12, color=C_INK_2)),
        margin=dict(t=10, b=40, l=10, r=10),
    )
    return fig


def _trend_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(
        name="收入", x=df["月份"], y=df["收入"], marker_color=C_GREEN,
        hovertemplate="%{x} · 收入 ¥%{y:,.2f}<extra></extra>",
    )
    fig.add_bar(
        name="支出", x=df["月份"], y=df["支出"], marker_color=C_RED,
        hovertemplate="%{x} · 支出 ¥%{y:,.2f}<extra></extra>",
    )
    fig.update_layout(
        barmode="group",
        bargap=0.2,
        bargroupgap=0.05,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08, x=0.5, xanchor="center", font=dict(size=12, color=C_INK_2)),
        xaxis=dict(tickfont=dict(size=11), showgrid=False, linecolor=C_GRID),
        yaxis=dict(gridcolor=C_GRID, zeroline=False, tickprefix="¥", tickformat=",.0f"),
    )
    return _base_layout(fig, 340)


def _category_bar_chart(rows: list[dict]) -> go.Figure:
    sorted_rows = sorted(rows, key=lambda r: float(r["total"]))
    labels = [f"{CATEGORY_EMOJI.get(r['category'], '📦')} {r['category']}" for r in sorted_rows]
    values = [float(r["total"]) for r in sorted_rows]
    height = max(260, 40 + len(labels) * 30)
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(color=C_BLUE, line=dict(width=0)),
            text=[format_currency(v) for v in values],
            textposition="outside",
            textfont=dict(size=12, color=C_INK_2),
            hovertemplate="%{y}<br>¥%{x:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis=dict(gridcolor=C_GRID, zeroline=False, tickprefix="¥", tickformat=",.0f"),
        yaxis=dict(tickfont=dict(size=13)),
        margin=dict(t=10, b=10, l=10, r=86),
    )
    return _base_layout(fig, height)


def _render_stats() -> None:
    st.markdown("---")
    st.markdown("## 📊 统计视图")
    tab_overview, tab_category, tab_type = st.tabs(["📈 总览", "🏷️ 分类统计", "💳 类型与支付"])

    with tab_overview:
        trend_year = st.selectbox("趋势年份", _available_years(), key="trend_year")
        trend_df = monthly_trend_frame(trend_year, get_monthly_trend(trend_year))
        if trend_df[["收入", "支出"]].to_numpy().sum() > 0:
            st.plotly_chart(_trend_chart(trend_df), width="stretch", key="trend_chart")
        else:
            st.info(f"{trend_year} 年暂无收支记录")

        c1, c2 = st.columns(2, gap="medium")
        type_rows = get_type_stats()
        payment_rows = get_payment_stats()
        with c1:
            st.markdown("##### 收支类型分布")
            if type_rows:
                st.plotly_chart(_donut_chart(type_rows, "type", TYPE_COLORS, "总金额"), width="stretch", key="donut_type")
            else:
                st.info("暂无数据")
        with c2:
            st.markdown("##### 支付方式分布")
            if payment_rows:
                st.plotly_chart(_donut_chart(payment_rows, "payment_method", PAYMENT_COLORS, "总金额"), width="stretch", key="donut_pay")
            else:
                st.info("暂无数据")

    with tab_category:
        cat_rows = get_category_stats()
        if cat_rows:
            st.plotly_chart(_category_bar_chart(cat_rows), width="stretch", key="cat_bar")
            st.dataframe(
                stats_table_frame(cat_rows, "category", CATEGORY_EMOJI),
                hide_index=True,
                width="stretch",
                key="cat_table",
                column_config=_stats_column_config("分类"),
            )
            grand = sum(float(r["total"]) for r in cat_rows)
            st.caption(f"合计 {len(cat_rows)} 个分类 · 总金额 {format_currency(grand)}")
        else:
            st.info("暂无分类统计数据")

    with tab_type:
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            st.markdown("##### 按收支类型")
            rows = get_type_stats()
            if rows:
                st.dataframe(
                    stats_table_frame(rows, "type"),
                    hide_index=True,
                    width="stretch",
                    key="type_table",
                    column_config=_stats_column_config("类型"),
                )
            else:
                st.info("暂无数据")
        with c2:
            st.markdown("##### 按支付方式")
            rows = get_payment_stats()
            if rows:
                st.dataframe(
                    stats_table_frame(rows, "payment_method"),
                    hide_index=True,
                    width="stretch",
                    key="pay_table",
                    column_config=_stats_column_config("支付方式"),
                )
            else:
                st.info("暂无数据")


# ======================================================================
# 导出
# ======================================================================

def _render_export() -> None:
    st.markdown("---")
    with st.container(border=True):
        t1, t2, t3, t4, t5 = st.columns([1.3, 2.4, 1, 1.4, 1.1], gap="small", vertical_alignment="bottom")
        t1.markdown("#### 📤 导出账单")
        mode = t2.radio(
            "导出范围", ["当前月份", "全年", "自定义月份组合"],
            horizontal=True, key="export_mode", label_visibility="collapsed",
        )
        today = datetime.now()
        year = int(t3.number_input("年份", min_value=2000, max_value=2100, value=today.year, key="export_year"))

        if mode == "当前月份":
            months = [today.month]
            t4.markdown(
                f"<div style='font-size:13px;color:{C_MUTED};padding-top:8px;'>将导出 {year} 年 {today.month} 月</div>",
                unsafe_allow_html=True,
            )
        elif mode == "全年":
            months = list(range(1, 13))
            t4.markdown(
                f"<div style='font-size:13px;color:{C_MUTED};padding-top:8px;'>将导出 {year} 年全年 12 个月</div>",
                unsafe_allow_html=True,
            )
        else:
            months = t4.multiselect(
                "选择月份", list(range(1, 13)), default=[today.month],
                key="export_months", label_visibility="collapsed",
            )

        if t5.button("生成 Excel", type="primary", width="stretch", key="generate_excel"):
            if not months:
                st.warning("请至少选择一个月份")
            else:
                buf = BytesIO()
                export_expenses_to_excel(buf, months=months, year=year)
                st.session_state["excel_pack"] = (
                    buf.getvalue(),
                    f"记账账单_{year}年{'_'.join(f'{m:02d}' for m in sorted(months))}月.xlsx",
                )

        pack = st.session_state.get("excel_pack")
        if pack:
            data, fname = pack
            d1, d2 = st.columns([1.6, 4], gap="small", vertical_alignment="center")
            d1.download_button(
                "⬇️ 下载 Excel 账单", data=data, file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary", width="stretch", key="download_excel",
            )
            d2.markdown(
                f"<div style='font-size:13px;color:{C_MUTED};padding-top:6px;'>文件已生成：{fname}（{len(data) / 1024:.0f} KB）"
                f"· 含账单明细、分类/类型/支付方式统计、月度汇总与图表</div>",
                unsafe_allow_html=True,
            )


# ======================================================================
# 主流程
# ======================================================================

def main() -> None:
    st.set_page_config(page_title="个人记账工具", page_icon="💰", layout="wide")
    init_db()
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)

    # 清理历史版本遗留的会话键，避免旧状态影响新逻辑
    st.session_state.pop("f_day", None)

    if not _ensure_auth():
        st.stop()

    if not _app_password():
        st.caption(
            "💡 当前未设置访问密码（本地使用免密）。若部署到公网，请在 .streamlit/secrets.toml 中设置 "
            "`APP_PASSWORD`，开启后访问链接需输入密码。"
        )

    today = datetime.now()

    flash = st.session_state.pop("flash", None)
    if flash:
        kind, msg = flash
        (st.success if kind == "success" else st.info)(msg)

    overall = get_overall_summary()
    _render_hero(today, overall)
    _render_kpi(today)

    col_form, col_list = st.columns([3.1, 6.9], gap="medium")
    with col_form:
        _render_add_form(today.date())
    with col_list:
        _render_list_section()

    _render_stats()
    _render_export()


if __name__ == "__main__":
    main()
