"""收支类型、支付方式与分类常量，以及展示用图标与颜色。"""

TRANSACTION_TYPES = ["收入", "支出"]
PAYMENT_METHODS = ["支付宝", "微信"]

CATEGORIES = [
    "餐饮",
    "美食",
    "交通",
    "购物",
    "娱乐",
    "王者荣耀",
    "电话费",
    "水电费",
    "居住",
    "家居用品",
    "奶茶饮料",
    "投资理财",
    "好评返现收入",
    "医药",
    "人情世故",
    "教育培训",
    "父母家庭开支",
    "AI支出",
    "其他",
]

# 分类展示图标
CATEGORY_EMOJI = {
    "餐饮": "🍚",
    "早餐": "🌅",
    "午餐": "☀️",
    "晚餐": "🌙",
    "买菜": "🥬",
    "酸奶": "🥛",
    "化妆品": "💄",
    "美食": "🍽️",
    "零食": "🍿",
    "詹记": "🍪",
    "蛋糕/糕点": "🍰",
    "交通": "🚇",
    "购物": "🛍️",
    "娱乐": "🎬",
    "王者荣耀": "🎮",
    "电话费": "📱",
    "水电费": "💡",
    "居住": "🏠",
    "家居用品": "🛋️",
    "奶茶饮料": "🧋",
    "投资理财": "📈",
    "好评返现收入": "🧧",
    "医药": "💊",
    "人情世故": "🎁",
    "教育培训": "📚",
    "父母家庭开支": "👨‍👩‍👧",
    "AI支出": "🤖",
    "其他": "📦",
}

# 收支类型与支付方式展示色（与 dataviz 参考色板一致）
TYPE_COLORS = {"收入": "#0ca30c", "支出": "#e34948"}
PAYMENT_COLORS = {"支付宝": "#2a78d6", "微信": "#1baf7a"}

# 分类细分：大类 -> 子类列表（统计仍按大类汇总）
CATEGORY_SUBCATEGORIES = {
    "餐饮": ["早餐", "午餐", "晚餐", "买菜", "酸奶"],
    "购物": ["化妆品"],
    "美食": ["零食", "詹记", "蛋糕/糕点"],
}

# 子类 -> 大类
SUBCATEGORY_PARENT: dict[str, str] = {
    sub: parent for parent, subs in CATEGORY_SUBCATEGORIES.items() for sub in subs
}


def category_label(category: str, subcategory: str = "") -> str:
    """展示名：小类~大类，如「早餐~餐饮」。"""
    if subcategory:
        return f"{subcategory}~{category}"
    return category


def category_emoji(category: str, subcategory: str = "") -> str:
    """优先使用小类图标，其次大类。"""
    return CATEGORY_EMOJI.get(subcategory) or CATEGORY_EMOJI.get(category, "📦")


def category_options() -> list[tuple[str, str, str]]:
    """记账表单的分类选项：(展示名, 大类, 小类)。"""
    options: list[tuple[str, str, str]] = []
    for cat in CATEGORIES:
        subs = CATEGORY_SUBCATEGORIES.get(cat)
        if subs:
            for sub in subs:
                options.append((category_label(cat, sub), cat, sub))
        else:
            options.append((cat, cat, ""))
    return options


def parse_category_label(label: str) -> tuple[str, str]:
    """把「早餐~餐饮」解析为 (大类, 小类)。"""
    if "~" in label:
        sub, cat = label.rsplit("~", 1)
        return cat, sub
    return label, ""
