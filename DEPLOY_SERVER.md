# 国内云服务器部署指南（随时随地打开链接记账）

> 目标：把记账工具部署到腾讯云/阿里云轻量服务器，手机、电脑浏览器打开链接即用，数据永久保存。
> 全程约 20~30 分钟，只需照着复制粘贴命令。

## 0. 架构说明

```
你的手机/电脑浏览器
        │  http://服务器公网IP:8501（输一次访问密码）
        ▼
云服务器（Ubuntu 22.04）
  └─ streamlit 常驻运行（systemd 管理，重启自动拉起）
       └─ SQLite 数据文件 finance.db（保存在服务器磁盘，永久）
```

## 1. 购买服务器

- 腾讯云轻量应用服务器：https://cloud.tencent.com/product/lighthouse
- 或阿里云轻量：https://www.aliyun.com/product/swas
- 选购建议：**2核2G 足够**（新用户约 ¥99~150/年），系统镜像选 **Ubuntu 22.04 LTS**，地域选离你近的（广州/上海等）
- 购买后记下两个信息：**公网 IP**、**root 密码**（在控制台可重置）

## 2. 防火墙放行 8501 端口

- 腾讯云：控制台 → 轻量应用服务器 → 你的实例 → **防火墙** → 添加规则 → 协议 TCP、端口 `8501`、策略允许
- 阿里云：控制台 → 实例 → **安全组** → 配置规则 → 入方向 → 放行 TCP `8501`

## 3. 把最新代码推到 GitHub（在本地电脑执行）

打开 PowerShell，执行：

```powershell
cd "c:\Users\徐媛媛\Desktop\AI Coding\finance_test1116"
git add -A
git commit -m "添加访问密码门，准备服务器部署"
git push
```

> 如果 GitHub 仓库是**私有**的，第 5 步克隆时需要令牌（见第 5 步说明）。

## 4. 登录服务器（本地 PowerShell）

```powershell
ssh root@你的公网IP
```

首次连接提示 `Are you sure...` 输入 `yes`，然后输入 root 密码（输入时不显示字符，正常现象）。

## 5. 安装 Python 与中文字体（服务器上执行）

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git fonts-noto-cjk
```

`fonts-noto-cjk` 是给 Excel 导出图表用的中文字体，不装图表会显示方框。

## 6. 拉取代码（服务器上执行）

```bash
git clone https://github.com/6sbfjf2js5-lab/finance_cli.git /opt/finance
```

- 仓库是**私有**的话，用令牌方式克隆（GitHub → Settings → Developer settings → Personal access tokens → 生成，勾选 repo 权限）：

```bash
git clone https://你的GitHub用户名:令牌@github.com/6sbfjf2js5-lab/finance_cli.git /opt/finance
```

## 7. 迁移本地已有账目数据（本地 PowerShell）

把本地 finance.db 上传到服务器（如果不需要历史数据可跳过）：

```powershell
scp "c:\Users\徐媛媛\Desktop\AI Coding\finance_test1116\finance.db" root@你的公网IP:/opt/finance/finance.db
```

## 8. 安装依赖（服务器上执行）

```bash
cd /opt/finance
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 9. 设置访问密码（服务器上执行）

```bash
cat > /opt/finance/.streamlit/secrets.toml <<'EOF'
APP_PASSWORD = "换成你自己的密码"
EOF
```

> ⚠️ **务必设置**：不设置密码时应用没有任何保护，任何人拿到链接都能查看和修改你的账目。设置后访问链接需要输入此密码。

## 10. 配置常驻运行（服务器上执行）

```bash
sudo tee /etc/systemd/system/finance.service > /dev/null <<'EOF'
[Unit]
Description=Personal Finance Streamlit App
After=network.target

[Service]
WorkingDirectory=/opt/finance
ExecStart=/opt/finance/.venv/bin/python -m streamlit run app.py --server.port 8501 --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now finance
sudo systemctl status finance
```

看到 `active (running)` 即成功。以后服务器重启，应用也会自动启动。

## 11. 打开链接使用 🎉

浏览器（手机/电脑都行）打开：

```
http://你的公网IP:8501
```

输入第 9 步设置的密码即可开始记账。同一浏览器会话只需输一次。

## 12. 日常更新代码（本地改完推送后，服务器执行）

```bash
cd /opt/finance
git pull
sudo systemctl restart finance
```

## 13. 数据备份（重要！建议每周执行，本地 PowerShell）

```powershell
scp root@你的公网IP:/opt/finance/finance.db "c:\Users\徐媛媛\Desktop\finance_backup_$(Get-Date -Format yyyyMMdd).db"
```

## 14. 常见问题

| 问题 | 解决 |
|---|---|
| 打开链接打不开 | 检查第 2 步防火墙是否放行 8501；服务器上 `sudo systemctl status finance` |
| 看应用运行日志 | `journalctl -u finance -f` |
| 修改密码 | 编辑 `/opt/finance/.streamlit/secrets.toml` 后 `sudo systemctl restart finance` |
| 图表中文变方框 | 确认第 5 步装了 `fonts-noto-cjk`，然后 `sudo systemctl restart finance` |
| 想用域名 + HTTPS（可选） | 域名解析到服务器 IP 后，装 Caddy 执行：`caddy reverse-proxy --from 你的域名 --to :8501`，会自动申请 HTTPS 证书 |
| 端口被占用 | `sudo systemctl stop finance` 后检查 `ss -tlnp \| grep 8501` |
