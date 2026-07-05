# finance_cli

个人记账工具（基于 Python + Streamlit + SQLite）。

**主要功能**
- 添加账目：金额、收支类型（收入/支出）、支付方式（支付宝/微信）、分类、日期、备注
- 支持的分类：餐饮、零食、交通、购物、娱乐、王者荣耀、电话费、水电费、居住、家居用品、奶茶饮料、投资理财、医药、人情世故、教育培训、父母家庭开支、其他
- 列表与筛选：按月份、分类、收支类型、支付方式过滤和查看账目
- 删除账目：通过账目 ID 删除记录
- 统计视图：按分类、收支类型与支付方式展示统计表与图表
- 导出 Excel：生成包含账单明细、分类统计、类型统计、支付方式统计与图表的 Excel 文件

**快速开始**
1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 在项目目录运行应用：

```bash
streamlit run app.py
```

3. 在浏览器打开 http://localhost:8501 并使用页面表单添加、筛选或导出账单。

**项目结构**
- app.py：Streamlit 页面与交互逻辑
- db.py：SQLite 初始化、模式（schema）检查与 CRUD 接口
- models.py：收支类型、支付方式与分类常量列表
- services.py：数据格式化与表格/统计准备函数
- exporter.py：导出 Excel（含图表）实现
- finance.db：本地 SQLite 数据库（运行时生成）
- .streamlit/：Streamlit 配置（部署时使用）

**数据库与向后兼容性**
- 程序启动时会自动创建数据库，并在需要时通过 ALTER TABLE 为旧数据库添加 `transaction_type` 与 `payment_method` 字段以保持向后兼容。

**导出说明**
- 导出文件包含以下工作表：`账单明细`、`分类统计`、`类型统计`、`支付方式统计`、`统计图`。
- 图表以图片形式嵌入 Excel 文件。

**测试**
- 项目内含单元测试（位于 `tests/`），可运行：

```bash
python -m unittest discover -v
```

**部署（Streamlit Community Cloud）**
- 推荐将仓库推送到 GitHub，然后在 https://share.streamlit.io 上按照 `STREAMLIT_DEPLOY.md` 中的步骤部署。

**后续改进建议**
- 自动根据 `收支类型` 将金额显示为正/负
- 添加更多支付方式或自定义分类管理界面
- 将持久层从本地 SQLite 替换为云数据库以支持多人在线使用

如需我将 README 内容发布到仓库并运行测试，请告诉我。
