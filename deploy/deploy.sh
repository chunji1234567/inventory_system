#!/usr/bin/env bash
set -euo pipefail

# =========================
# 配置区：按需改这里
# =========================
REPO_URL="${REPO_URL:-https://github.com/chunji1234567/inventory_system.git}"  # 推荐 https；也可改 ssh
BRANCH="${BRANCH:-main}"

APP_DIR="${APP_DIR:-/srv/inventory_system}"

# 默认用当前登录用户（避免 admin/chunjiwang 混乱）
APP_USER="${APP_USER:-$(whoami)}"
APP_GROUP="${APP_GROUP:-$(id -gn)}"

SERVICE_NAME="${SERVICE_NAME:-inventory}"              # systemd 服务名
BIND_ADDR="${BIND_ADDR:-127.0.0.1:8000}"               # gunicorn 监听地址（host:port）
DJANGO_SETTINGS="${DJANGO_SETTINGS:-config.settings}"
WSGI_APP="${WSGI_APP:-config.wsgi:application}"

# Python 路径：优先 python3.11，否则 python3
PY_BIN="${PY_BIN:-}"
# =========================

log(){ echo -e "\n\033[1;32m==>\033[0m $*"; }
warn(){ echo -e "\n\033[1;33m[WARN]\033[0m $*"; }
die(){ echo -e "\n\033[1;31m[ERR]\033[0m $*"; exit 1; }

need_cmd(){ command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"; }

pkg_install_yum(){
  local pkgs=("$@")
  sudo yum install -y "${pkgs[@]}"
}
pkg_install_apt(){
  local pkgs=("$@")
  sudo apt-get install -y "${pkgs[@]}"
}

detect_pkg_manager(){
  if command -v apt-get >/dev/null 2>&1; then
    PKG_MANAGER="apt"; return 0
  fi
  if command -v yum >/dev/null 2>&1; then
    PKG_MANAGER="yum"; return 0
  fi
  die "Unsupported OS: need apt-get or yum"
}

ensure_basic_tools(){
  detect_pkg_manager

  if [[ -z "${PY_BIN}" ]]; then
    PY_BIN="$(command -v python3.11 || true)"
    [[ -n "${PY_BIN}" ]] || PY_BIN="$(command -v python3 || true)"
  fi
  [[ -x "${PY_BIN}" ]] || die "python3 not found. Install python3 (or set PY_BIN)"

  if [[ "${PKG_MANAGER}" == "apt" ]]; then
    log "Update apt cache"
    sudo apt-get update -y
    log "Install base packages via apt"
    pkg_install_apt git curl ca-certificates build-essential python3-venv python3-pip libpq-dev pkg-config
  else
    log "Install base packages via yum"
    pkg_install_yum git curl ca-certificates openssl openssl-devel \
      gcc make zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel \
      libffi-devel xz-devel python3 python3-pip postgresql-devel
  fi
}

install_nginx(){
  if command -v nginx >/dev/null 2>&1; then
    log "nginx already installed"
  else
    detect_pkg_manager
    if [[ "${PKG_MANAGER}" == "apt" ]]; then
      log "Install nginx via apt"
      sudo apt-get install -y nginx
    else
      log "Install nginx via yum"
      sudo yum install -y nginx || sudo yum install -y nginx --disableexcludes=all
    fi
  fi

  log "Enable & start nginx"
  sudo systemctl enable --now nginx
}

# 确保目录权限统一（避免 dubious ownership）
prepare_app_dir(){
  log "Prepare app directory: ${APP_DIR}"
  sudo mkdir -p "${APP_DIR}"
  sudo chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
}

# Git 安全设置 + 忽略 chmod 导致的 filemode 变化
git_safety_config(){
  # 对当前用户生效
  git config --global --add safe.directory "${APP_DIR}" || true
  git config --global core.fileMode false || true
}

# 核心：部署推荐策略 = 永远对齐远端（服务器不保留 tracked 文件本地改动）
clone_or_sync_repo(){
  prepare_app_dir

  if [[ -d "${APP_DIR}/.git" ]]; then
    log "Repo exists, syncing to origin/${BRANCH} (hard reset)..."
    cd "${APP_DIR}"

    # 先加 safety 配置（避免报 dubious ownership）
    git_safety_config

    # 强制对齐远端（不再被本地改动卡住）
    git fetch origin
    git checkout "${BRANCH}"
    git reset --hard "origin/${BRANCH}"
    git clean -fd
  else
    log "Cloning repo..."
    # 不做 rm -rf 清空，避免误删 .env/venv 等（首次部署一般是空目录）
    git_safety_config
    git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
    sudo chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
  fi
}

setup_venv_and_deps(){
  log "Setup venv & install deps"
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
  log "Django prepare"
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

# 读取你的 .env（没有也不会报错）
EnvironmentFile=-${APP_DIR}/.env

# PATH 要完整，否则一些命令找不到
Environment="PATH=${APP_DIR}/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
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

  # 用 upstream 更稳（未来你改 unix socket 也好扩展）
  sudo tee /etc/nginx/conf.d/inventory.conf >/dev/null <<EOF
upstream inventory_app {
    server ${BIND_ADDR};
}

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
        proxy_pass http://inventory_app;
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

  echo
  echo "✅ Deploy finished."
  echo "Next steps:"
  echo "1) Ensure ALLOWED_HOSTS includes your public IP/domain (in settings or .env)"
  echo "2) Open Security Group inbound TCP 80 (and 443 if HTTPS)"
  echo "3) Visit: http://<PublicIP>/"
}

main(){
  need_cmd sudo
  need_cmd curl

  ensure_basic_tools
  need_cmd git

  install_nginx

  # 统一用当前用户执行脚本（避免 sudo -u 混乱）；目录 owner 也统一
  clone_or_sync_repo
  setup_venv_and_deps
  django_prepare
  write_systemd_service
  write_nginx_conf
  self_check
}

main "$@"
