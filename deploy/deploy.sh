#!/usr/bin/env bash
set -euo pipefail

# =========================
# 配置区：按需改这里
# =========================
REPO_URL="${REPO_URL:-git@github.com:chunji1234567/inventory_system.git}"   # 你的仓库地址（ssh 或 https）
BRANCH="${BRANCH:-main}"                                                  # 分支
APP_DIR="${APP_DIR:-/srv/inventory_system}"                               # 部署目录
APP_USER="${APP_USER:-admin}"                                             # 运行用户（一般就是 admin）
APP_GROUP="${APP_GROUP:-admin}"
SERVICE_NAME="${SERVICE_NAME:-inventory}"                                 # systemd 服务名
BIND_ADDR="${BIND_ADDR:-127.0.0.1:8000}"                                  # gunicorn 监听地址
DJANGO_SETTINGS="${DJANGO_SETTINGS:-config.settings}"                     # Django settings 模块
WSGI_APP="${WSGI_APP:-config.wsgi:application}"                           # WSGI 入口
PY_BIN="${PY_BIN:-/usr/local/bin/python3.10}"                             # Python 路径（你已装好 3.10.13）
# =========================

log(){ echo -e "\n\033[1;32m==>\033[0m $*"; }
warn(){ echo -e "\n\033[1;33m[WARN]\033[0m $*"; }
die(){ echo -e "\n\033[1;31m[ERR]\033[0m $*"; exit 1; }

need_cmd(){ command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"; }

is_root(){
  [[ "${EUID}" -eq 0 ]]
}

pkg_install_yum(){
  local pkgs=("$@")
  sudo yum install -y "${pkgs[@]}"
}

ensure_basic_tools(){
  log "Install base packages (git, curl, gcc, python build deps if needed)..."
  pkg_install_yum git curl ca-certificates openssl openssl-devel \
    gcc make zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel \
    libffi-devel xz-devel

  # ensure pip/venv available via compiled python; system python packages not required
}

install_nginx(){
  if systemctl list-unit-files | grep -q '^nginx\.service'; then
    log "nginx already installed"
    return 0
  fi

  log "Install nginx (may be excluded by yum policy, try disableexcludes)..."
  if sudo yum install -y nginx --disableexcludes=all; then
    :
  else
    warn "nginx install failed with disableexcludes=all, try normal yum install..."
    sudo yum install -y nginx
  fi

  log "Enable & start nginx"
  sudo systemctl enable --now nginx
}

clone_or_update_repo(){
  log "Prepare app directory: ${APP_DIR}"
  sudo mkdir -p "${APP_DIR}"
  sudo chown -R "${APP_USER}:${APP_GROUP}" "$(dirname "${APP_DIR}")" || true
  sudo chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"

  if [[ -d "${APP_DIR}/.git" ]]; then
    log "Repo already exists, pulling latest (${BRANCH})..."
    cd "${APP_DIR}"
    git fetch --all
    git checkout "${BRANCH}"
    git pull origin "${BRANCH}"
  else
    log "Cloning repo..."
    rm -rf "${APP_DIR:?}/"*
    git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
  fi
}

setup_venv_and_deps(){
  log "Setup venv"
  [[ -x "${PY_BIN}" ]] || die "Python not found at ${PY_BIN}. Set PY_BIN or install python3.10."
  cd "${APP_DIR}"

  if [[ -d venv ]]; then
    log "venv exists, reusing"
  else
    "${PY_BIN}" -m venv venv
  fi

  # shellcheck disable=SC1091
  source venv/bin/activate

  log "Upgrade pip"
  pip install -U pip wheel setuptools

  if [[ -f requirements.txt ]]; then
    log "Install backend dependencies from requirements.txt"
    pip install -r requirements.txt
  else
    warn "requirements.txt not found. Install minimal deps: django + gunicorn"
    pip install "django>=4.2,<5.0" gunicorn
  fi
}

django_prepare(){
  cd "${APP_DIR}"
  # shellcheck disable=SC1091
  source venv/bin/activate

  export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS}"

  log "Django check"
  python manage.py check

  log "Run migrations"
  python manage.py migrate --noinput

  log "Collect static"
  python manage.py collectstatic --noinput || die "collectstatic failed. Ensure STATIC_ROOT is set in settings.py"

  log "Show DB file (if sqlite)"
  if [[ -f db.sqlite3 ]]; then
    ls -l db.sqlite3 || true
  fi
}

write_systemd_service(){
  log "Write systemd service: ${SERVICE_NAME}.service"
  sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null <<EOF
[Unit]
Description=Inventory System Gunicorn Service
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${APP_DIR}
Environment=PATH=${APP_DIR}/venv/bin
Environment=DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS}
ExecStart=${APP_DIR}/venv/bin/gunicorn --workers 3 --bind ${BIND_ADDR} ${WSGI_APP}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  sudo systemctl daemon-reexec
  sudo systemctl daemon-reload
  sudo systemctl enable --now "${SERVICE_NAME}"
  sudo systemctl restart "${SERVICE_NAME}"
  sudo systemctl status "${SERVICE_NAME}" --no-pager || true
}

write_nginx_conf(){
  log "Write nginx reverse proxy config"
  sudo mkdir -p /etc/nginx/conf.d

  # 先备份可能存在的 default 配置（有些系统默认页在别处，这里只处理 conf.d）
  if [[ -f /etc/nginx/conf.d/default.conf ]]; then
    sudo mv /etc/nginx/conf.d/default.conf "/etc/nginx/conf.d/default.conf.bak.$(date +%s)"
  fi

  sudo tee /etc/nginx/conf.d/inventory.conf >/dev/null <<EOF
server {
    listen 80;
    server_name _;

    client_max_body_size 20M;

    location /static/ {
        alias ${APP_DIR}/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    location / {
        proxy_pass http://${BIND_ADDR};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

  sudo nginx -t
  sudo systemctl reload nginx
}

self_check(){
  log "Self-check (local)"
  curl -I "http://127.0.0.1" || true
  curl -I "http://127.0.0.1/static/admin/css/base.css" || true

  echo
  echo "✅ Deploy finished."
  echo "Next steps:"
  echo "1) Ensure ALLOWED_HOSTS includes your public IP/domain in config/settings.py"
  echo "2) Open Security Group inbound TCP 80 (and 443 if HTTPS)"
  echo "3) Visit: http://<PublicIP>/  (or your route like /inventory/)"
}

main(){
  need_cmd sudo
  need_cmd git
  need_cmd curl

  ensure_basic_tools
  install_nginx
  clone_or_update_repo
  setup_venv_and_deps
  django_prepare
  write_systemd_service
  write_nginx_conf
  self_check
}

main "$@"
