# Streamlit Community Cloud 部署指南

## 1. 前提准备
- 你需要一个 GitHub 账号
- 你的项目已经在本地完成并可运行
- Streamlit Cloud 是国外服务，国内访问可能略慢

## 2. 必要文件
确保项目包含以下文件：

- `app.py`：Streamlit 程序入口
- `requirements.txt`：记录运行依赖
- `.gitignore`：忽略不需要上传的文件
- `.streamlit/config.toml`：Streamlit 配置文件

如果你已经有这些文件，就可以直接部署。

## 3. 将项目上传到 GitHub
1. 在本地项目目录打开终端。确保当前目录是项目根目录：
   ```powershell
   cd "c:\Users\徐媛媛\Desktop\AI Coding\finance_cli"
   ```
2. 如果你还没有初始化 Git 仓库，执行：
   ```powershell
   git init
   git add .
   git commit -m "初始化记账工具项目"
   ```
3. 在 GitHub 上创建一个新的仓库，例如 `finance_cli`。
4. 将本地仓库关联到 GitHub：
   ```powershell
   git remote add origin https://github.com/<你的用户名>/finance_cli.git
   git branch -M main
   git push -u origin main
   ```

### 示例命令
以下示例把仓库推送到用户名为 `yourname` 的 GitHub：
```powershell
git remote add origin https://github.com/yourname/finance_cli.git
git branch -M main
git push -u origin main
```

### 如果你已经有 Git 仓库并想直接推送
```powershell
git add .
git commit -m "更新部署配置"
git push
```

## 4. 在 Streamlit Community Cloud 上部署
1. 打开：`https://share.streamlit.io`
2. 点击 `Sign in`，选择 `GitHub` 登录。
3. 登录后选择 `New app`。
4. 填写仓库信息：
   - Repository：你的仓库
   - Branch：`main`
   - Main file path：`app.py`
5. 点击 `Deploy`，等待部署完成。

## 5. 访问你的在线网址
- 部署成功后，Streamlit Cloud 会给出一个类似 `https://<用户名>-<项目名>.streamlit.app` 的网址。
- 复制这个网址即可在浏览器中访问你的应用。

## 6. 后续更新流程
每次你在本地修改了项目后：
```powershell
git add .
git commit -m "更新描述"
git push
```
Streamlit Cloud 会自动检测 GitHub 更新并重新部署。

## 7. 额外注意
- 如果你使用图表导出功能，`openpyxl` 和 `matplotlib` 在 `requirements.txt` 中已经列出，无需额外安装。
- `finance.db` 作为本地 SQLite 数据库不建议上传。如果你想让 Cloud 上的数据持久化，需要改成支持远程数据库或使用云存储。

## 8. 可选优化
- 如果你希望在 Cloud 上保存用户数据，后续可以改用 PostgreSQL 或 MySQL
- 想要自定义域名，可以在 Streamlit Cloud 中绑定域名
