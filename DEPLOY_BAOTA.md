# 宝塔面板部署指南（记账工具上线，随时随地打开链接使用）

> 用宝塔面板把记账工具部署到云服务器。全程照着点、照着复制粘贴即可，约 30~40 分钟。
> 最终效果：手机/电脑浏览器打开 `http://服务器IP:8501`（或绑定域名后 `https://你的域名`），输入密码即可记账。

## 架构说明

```
你的手机/电脑浏览器
        │  http://IP:8501 或 https://域名（宝塔反向代理）
        ▼
云服务器（宝塔面板管理）
  └─ streamlit 常驻运行（宝塔"进程守护管理器"守护，重启自动拉起）
       └─ SQLite 数据 finance.db（存于服务器磁盘，永久保存）
```

## 第 0 步：先把最新代码推到 GitHub（本地执行一次）

服务器上拉取的是 GitHub 仓库的代码，所以部署前先在本地把最新代码推送上去。本地 PowerShell 执行：

```powershell
cd "c:\Users\徐媛媛\Desktop\AI Coding\finance_test1116"
git add -A
git commit -m "准备宝塔部署"
git push
```

> 第一次 push 可能会弹出浏览器让你登录 GitHub，登录授权即可。

## 第 1 步：准备服务器

1. 购买云服务器（腾讯云/阿里云轻量均可）：
   - 配置：**2核2G** 足够（新用户约 ¥99~150/年）
   - 系统：**Ubuntu 22.04 LTS**（或 Debian 12）
   - 记下：**公网 IP**、**root 密码**
2. 在云厂商控制台放行端口（腾讯云叫"防火墙"、阿里云叫"安全组"）：
   - `22`（SSH，一般默认已放行）
   - `8501`（Streamlit 应用端口）
   - `80`、`443`（绑定域名时才需要）
   - `8888` 或面板安装时提示的端口（宝塔面板端口，装完面板再放行也行）

## 第 2 步：安装宝塔面板

1. 本地 PowerShell 登录服务器：

```powershell
ssh root@你的公网IP
```

2. 打开宝塔官网获取最新安装命令：https://www.bt.cn/new/download.html
   选择 **Ubuntu/Debian** 版，复制安装命令（形如下面，以官网当前显示为准）：

```bash
wget -O install.sh https://download.bt.cn/install/install-ubuntu_6.0.sh && sudo bash install.sh
```

3. 安装完成后，终端会显示**面板地址、用户名、密码**（形如 `http://IP:端口/安全入口`），**截图保存**。
4. 浏览器打开面板地址登录。首次登录会引导安装环境套件——**全部跳过**（我们只需要 Nginx，后面单独装）。

## 第 3 步：面板放行端口

宝塔面板 → 左侧【安全】→ 添加端口规则：

- `8501`（应用端口）
- 若宝塔面板端口未放行，也一并放行

> 注意：云厂商控制台和宝塔面板**两处都要放行** 8501，缺一处就打不开。

## 第 4 步：把代码放到服务器

**方式 A（推荐，用 Git）**：面板 → 左侧【终端】，执行：

```bash
# 如果仓库是公开的：
git clone https://github.com/6sbfjf2js5-lab/finance_cli.git /www/wwwroot/finance

# 如果仓库是私有的（GitHub → Settings → Developer settings → Personal access tokens 生成令牌，勾选 repo 权限）：
git clone https://你的GitHub用户名:令牌@github.com/6sbfjf2js5-lab/finance_cli.git /www/wwwroot/finance
```

**方式 B（不用 Git）**：本地把项目打包成 zip → 面板 → 【文件】→ 进入 `/www/wwwroot` → 上传 zip → 右键解压，把解压出的文件夹改名为 `finance`。

## 第 5 步：迁移本地账目数据（可选但强烈建议）

本地 PowerShell 执行（把本地的账目数据库传到服务器）：

```powershell
scp "c:\Users\徐媛媛\Desktop\AI Coding\finance_test1116\finance.db" root@你的公网IP:/www/wwwroot/finance/finance.db
```

> 如果你不用迁移历史数据，跳过本步，服务器会从空账本开始。

## 第 6 步：安装依赖

面板 → 【终端】，执行：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git fonts-noto-cjk
cd /www/wwwroot/finance
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> `fonts-noto-cjk` 是中文字体，不装的话导出 Excel 的图表中文会变方框。

## 第 7 步：设置访问密码

面板 → 【文件】→ 进入 `/www/wwwroot/finance/.streamlit` 目录 → 新建文件 `secrets.toml`，内容：

```toml
APP_PASSWORD = "换成你自己的密码"
```

> ⚠️ 不设置密码 = 任何人拿到链接都能看你的账目，务必设置。

## 第 8 步：用进程守护管理器常驻运行（关键）

1. 面板 → 【软件商店】→ 搜索安装 **"进程守护管理器"**（Supervisor）
2. 安装后打开，点【添加守护进程】：

| 设置项 | 填写内容 |
|---|---|
| 名称 | finance |
| 启动用户 | root |
| 运行目录 | /www/wwwroot/finance |
| 启动命令 | `/www/wwwroot/finance/.venv/bin/python -m streamlit run app.py --server.port 8501 --server.headless true` |
| 进程数量 | 1 |

3. 保存并启动。看到状态为**运行中**即成功。
4. 浏览器打开 `http://你的公网IP:8501`，输入第 7 步的密码 → **部署完成 🎉**
   - 若提示端口被占用或启动失败：面板【终端】执行 `ss -tlnp | grep 8501` 查看占用，再查守护进程日志

## 第 9 步（可选）：绑定域名 + HTTPS

1. 域名解析：在你的域名服务商处添加 A 记录，指向服务器公网 IP
2. 面板 → 软件商店 → 安装 **Nginx**
3. 面板 → 【网站】→【添加站点】：域名填你的域名，PHP 版本选**纯静态**，创建
4. 进入站点【设置】→【反向代理】→ 添加：
   - 代理名称：finance
   - 目标 URL：`http://127.0.0.1:8501`
   - 发送域名：`$host`
5. 站点【设置】→【SSL】→【Let's Encrypt】→ 一键申请证书，勾选"强制 HTTPS"
6. 之后访问 `https://你的域名` 即可，且**建议关闭 8501 端口的公网访问**（面板【安全】删除 8501 规则；反向代理走本机不受影响）

## 第 10 步：日常更新代码

本地改完代码 → `git push` → 面板【终端】：

```bash
cd /www/wwwroot/finance
git pull
```

再到【进程守护管理器】重启 finance 进程即可（Streamlit 通常也会自动重载）。

## 第 11 步：数据备份（重要！）

面板 → 【计划任务】→ 添加 Shell 脚本任务，周期选每天凌晨：

```bash
cp /www/wwwroot/finance/finance.db /www/backup/finance_$(date +%Y%m%d).db
```

定期用宝塔【文件】把备份下载到本地电脑，双保险。

## 常见问题

| 问题 | 排查 |
|---|---|
| 打不开 8501 | 云厂商防火墙 + 宝塔【安全】两处都要放行；守护进程是否"运行中" |
| 看应用日志 | 进程守护管理器 → 日志；或终端 `journalctl -u supervisor -f` |
| 修改密码 | 改 `/www/wwwroot/finance/.streamlit/secrets.toml` 后重启守护进程 |
| 更新代码后页面没变 | 浏览器 Ctrl+F5；重启 finance 守护进程 |
| 面板装不上 | 换系统重装（推荐 Ubuntu 22.04 / Debian 12 纯净系统） |
