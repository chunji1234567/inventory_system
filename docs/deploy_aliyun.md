# 阿里云部署脚本使用指南

1. **准备服务器**：全新 Ubuntu / Alibaba Cloud Linux / CentOS 机器即可，确保能 `sudo`。开放安全组 80/443 端口。
2. **安装 Git 并拉仓库**（若服务器上尚未有项目）：
   ```bash
   sudo apt-get update && sudo apt-get install -y git   # CentOS 用 yum
   git clone https://github.com/chunji1234567/inventory_system.git
   cd inventory_system
   ```
3. **编辑 `deploy/deploy.sh` 配置区**：根据需要覆盖 `REPO_URL`、`BRANCH`、`APP_DIR`、`APP_USER`、`SERVICE_NAME` 和数据库相关的 `.env`。脚本会自动：
   - 检测 `apt` 或 `yum`，安装 Python3/venv、编译依赖、git、curl、libpq-dev、nginx 等；
   - 创建运行用户（不存在时）；
   - 创建并更新虚拟环境，安装 `requirements.txt`；
   - 运行 `python manage.py migrate/collectstatic`；
   - 写入 systemd 服务与 Nginx 反向代理。
4. **运行脚本**：
   ```bash
   chmod +x deploy/deploy.sh
   ./deploy/deploy.sh
   ```
5. **部署后**：
   - 在 `.env` 中配置 `POSTGRES_*` 或 `DATABASE_URL` 并重启服务：`sudo systemctl restart inventory`
   - 凭域名/IP 访问，首次登陆前执行 `python manage.py createsuperuser`（可在 `APP_DIR` 下 `source venv/bin/activate` 后运行）。
6. **启用 HTTPS**：完成基础部署后可用 certbot/Let’s Encrypt，为 `/etc/nginx/conf.d/inventory.conf` 增加 443 server 块并 reload。
