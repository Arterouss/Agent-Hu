#!/usr/bin/env bash
# ==============================================================================
# Setup Cron Automation Helper for Claude Pro Hunter
# Detects absolute path to .venv and hunter.py, then provides or installs crontab
# ==============================================================================

set -e

# Get absolute path of this script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python3"
HUNTER_SCRIPT="${SCRIPT_DIR}/hunter.py"
LOG_FILE="${SCRIPT_DIR}/hunter.log"

echo "=========================================================="
echo "  Claude Pro Invite Link Hunter - Cron Setup Helper       "
echo "=========================================================="
echo "Project Path : ${SCRIPT_DIR}"

if [ ! -f "${PYTHON_BIN}" ]; then
    echo "[!] Warning: Python virtualenv not found at ${PYTHON_BIN}"
    echo "    Creating virtualenv and installing dependencies..."
    python3 -m venv "${SCRIPT_DIR}/.venv"
    "${SCRIPT_DIR}/.venv/bin/pip" install --upgrade pip
    "${SCRIPT_DIR}/.venv/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt"
fi

if [ ! -f "${HUNTER_SCRIPT}" ]; then
    echo "[x] Error: hunter.py not found at ${HUNTER_SCRIPT}"
    exit 1
fi

# Read interval from .env or default to 30
INTERVAL=30
if [ -f "${SCRIPT_DIR}/.env" ]; then
    ENV_INTERVAL=$(grep -E '^CHECK_INTERVAL_MINUTES=' "${SCRIPT_DIR}/.env" | cut -d '=' -f2 | tr -d ' "')
    if [ -n "${ENV_INTERVAL}" ]; then
        INTERVAL="${ENV_INTERVAL}"
    fi
fi

CRON_JOB="*/${INTERVAL} * * * * cd ${SCRIPT_DIR} && ${PYTHON_BIN} ${HUNTER_SCRIPT} >> ${LOG_FILE} 2>&1"

echo ""
echo "Recommended Crontab Line (every ${INTERVAL} minutes):"
echo "----------------------------------------------------------"
echo "${CRON_JOB}"
echo "----------------------------------------------------------"
echo ""

read -p "Do you want to automatically append this to your crontab? [y/N]: " choice
case "$choice" in 
  y|Y )
    # Ensure current crontab exists
    (crontab -l 2>/dev/null || true) | grep -v "${HUNTER_SCRIPT}" > /tmp/cron_temp || true
    echo "${CRON_JOB}" >> /tmp/cron_temp
    crontab /tmp/cron_temp
    rm -f /tmp/cron_temp
    echo "[✓] Crontab successfully installed! Running every ${INTERVAL} minutes."
    crontab -l | grep "hunter.py"
    ;;
  * )
    echo "[i] Skipped automatic installation."
    echo "    You can add it manually anytime by running: crontab -e"
    ;;
esac

