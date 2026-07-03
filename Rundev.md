# Rundev

## 项目启动步骤

1. 打开项目目录：
   ```powershell
   cd "c:\Users\徐媛媛\Desktop\AI Coding\finance_cli"
   ```

2. 启用或创建 Python 虚拟环境（如果尚未创建）：
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. 安装依赖：
   ```powershell
   python -m pip install -r requirements.txt
   ```

4. 启动 Streamlit 应用：
   ```powershell
   python -m streamlit run app.py
   ```

5. 在浏览器中打开：
   ```text
   http://localhost:8501
   ```

## 说明

- 应用文件入口：`app.py`
- 数据库文件：`finance.db`
- 导出功能会生成 Excel 文件并下载到本地
- 如果要停止应用，可以在终端中按 `Ctrl+C`
