#!/bin/bash

# ===============================================================
# Frappe-Critic Development Environment Setup
# ===============================================================

# Disable proxy
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy

# --- Environment Version ---
FRAPPE_BRANCH="version-15"
ERPNEXT_BRANCH="version-15"
HRMS_BRANCH="version-15"

set -e

export PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple/"
export PIP_TRUSTED_HOST="pypi.tuna.tsinghua.edu.cn"

run_with_retry() {
  local attempts=3
  local delay=8
  local count=1

  until "$@"; do
    if [ "${count}" -ge "${attempts}" ]; then
      return 1
    fi
    echo "Command failed. Retrying in ${delay}s (${count}/${attempts}): $*"
    sleep "${delay}"
    count=$((count + 1))
  done
}

init_bench_with_retry() {
  local target_dir="$1"
  local attempts=3
  local delay=8
  local count=1

  until bench init --frappe-branch ${FRAPPE_BRANCH} --skip-redis-config-generation --no-procfile "${target_dir}"; do
    if [ "${count}" -ge "${attempts}" ]; then
      return 1
    fi
    rm -rf "${target_dir}"
    echo "bench init failed. Retrying in ${delay}s (${count}/${attempts})"
    sleep "${delay}"
    count=$((count + 1))
  done
}

echo "--- Step 1: Initialize Bench ---"
BENCH_DIR="frappe-bench"
if [ ! -f "${BENCH_DIR}/sites/common_site_config.json" ]; then
  shopt -s dotglob nullglob
  bench_files=("${BENCH_DIR}"/*)
  if [ -d "${BENCH_DIR}" ] && [ ${#bench_files[@]} -eq 0 ]; then
    TEMP_BENCH_DIR="${BENCH_DIR}-init"
    rm -rf "${TEMP_BENCH_DIR}"
    init_bench_with_retry "${TEMP_BENCH_DIR}"
    mv "${TEMP_BENCH_DIR}"/* "${BENCH_DIR}/"
    rmdir "${TEMP_BENCH_DIR}"
  else
    init_bench_with_retry "${BENCH_DIR}"
  fi
fi
cd "${BENCH_DIR}"

if ! ./env/bin/python -c "import frappe" 2>/dev/null; then
  bench pip install -e apps/frappe
fi

fix_asset_link() {
  local app_name="$1"
  local expected_target="$2"
  local link_path="sites/assets/${app_name}"

  if [ -L "${link_path}" ]; then
    local current_target
    current_target="$(readlink "${link_path}")"
    if [ "${current_target}" != "${expected_target}" ]; then
      rm "${link_path}"
      ln -s "${expected_target}" "${link_path}"
    fi
  fi
}

fix_asset_link "frappe" "/home/frappe/frappe-bench/apps/frappe/frappe/public"

# Configure Docker services connection
bench set-mariadb-host mariadb
bench set-redis-cache-host redis://redis:6379
bench set-redis-queue-host redis://redis:6379
bench set-redis-socketio-host redis://redis:6379

echo "--- Step 2: Get Apps ---"
if [ ! -d "apps/erpnext" ]; then
  bench get-app --skip-assets erpnext --branch ${ERPNEXT_BRANCH}
fi
if [ ! -d "apps/hrms" ]; then
  bench get-app --skip-assets hrms --branch ${HRMS_BRANCH}
fi

echo "--- Step 3: Create Site ---"
if [ ! -d "sites/hrms.localhost" ]; then
  bench new-site hrms.localhost --force --mariadb-root-password 123 --admin-password admin
fi

echo "--- Step 4: Install Apps ---"
if ! bench --site hrms.localhost execute-app-cmd --app erpnext --cmd "import frappe; print('ok')" 2>/dev/null; then
  bench --site hrms.localhost install-app erpnext hrms
fi

echo "--- Step 5: Install Semgrep ---"
if ! command -v semgrep &> /dev/null; then
  pip install semgrep==1.45.0 -i https://mirrors.aliyun.com/pypi/simple/
fi

echo "--- Step 6: Install Frappe Critic ---"
if [ ! -d "apps/frappe_critic" ]; then
  # 使用软链接确保宿主机修改实时同步
  ln -s /workspace/frappe_critic ./apps/frappe_critic
fi
# 使用 -e 模式安装（Editable）
bench pip install -e apps/frappe_critic

# 2. 【关键修复】重新生成干净的 apps.txt，防止名称粘连
# 这样操作可以确保每个 App 占据独立的一行，彻底解决 erpnextfrappe_critic 报错
printf "frappe\nerpnext\nhrms\nfrappe_critic\n" > sites/apps.txt

# 3. 注册 Python 环境
bench pip install -e apps/frappe_critic

# 4. 执行站点安装
if ! bench --site hrms.localhost execute-app-cmd --app frappe_critic --cmd "import frappe_critic; print('ok')" 2>/dev/null; then
  bench --site hrms.localhost install-app frappe_critic
fi

echo "--- Step 7: Start Bench ---"
# 确保 Procfile 存在并移除 redis 冲突
if [ ! -f "Procfile" ]; then
  bench setup procfile
fi
sed -i '/redis/d;/watch/d' Procfile

# 设定默认站点并关闭多租户，确保 127.0.0.1 可直接访问
bench use hrms.localhost
bench set-config -g dns_multitenant 0

# 启动服务
bench start

# Keep container running
tail -f /dev/null
