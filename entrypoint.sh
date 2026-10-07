#!/bin/sh
set -e
#######################
# Todo: When application is migrated to new JSON API, please remove --disable-api from commands
#######################

# Default settings
CONFIG_FILE="${STUDIP_CONFIG_FILE:-./.config/config.json}"
CRON_SCHEDULE="${CRON_INTERVAL:-${CRON_SCHEDULE:-0 8,13,19 * * *}}"
RUN_ON_STARTUP="${STUDIP_RUN_ON_STARTUP:-true}"

# If a custom command is provided (and not starting with standard start commands), execute it directly
if [ $# -gt 0 ] && [ "$1" != "crond" ] && [ "$1" != "start" ]; then
    exec "$@"
fi

echo "=========================================="
echo " Starting studip-sync container"
echo " Date/Time: $(date)"
echo " Config file: ${CONFIG_FILE}"
echo " Cron interval: ${CRON_SCHEDULE}"
echo "=========================================="

CONFIG_DIR="$(dirname "${CONFIG_FILE}")"
mkdir -p "${CONFIG_DIR}"

# Step 1: When no config file is present, initialize it
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "Config file not found at '${CONFIG_FILE}'."

    # If environment variables for configuration are set, initialize from env
    if [ -n "${STUDIP_USERNAME:-${STUDIP_USER:-${STUDIP_LOGIN:-}}}" ]; then
        echo "Initializing configuration from environment variables..."
        python3 studip_sync.py --init-from-env --config "${CONFIG_FILE}"
    else
        echo "Please create it manually by running: python3 studip_sync.py --init --config '${CONFIG_FILE}'"
        echo "Waiting for the config file to appear..."
         # Allow 'docker stop' to terminate the container cleanly
        trap 'echo "Received stop signal, exiting."; exit 0' TERM INT
        while [ ! -f "${CONFIG_FILE}" ]; do
                sleep 5 &
                wait $!
        done

        trap - TERM INT
        echo "Config file detected, continuing..."
#        echo "Running studip_sync.py --init..."
#        python3 studip_sync.py --init --config "${CONFIG_FILE}" || {
#            echo "Initialization failed or was cancelled."
#        }
    fi
fi

if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: No configuration file exists at '${CONFIG_FILE}'."
    echo "Please mount a configuration file or provide environment variables in docker compose."
    exit 1
fi

# Step 2: At startup run studip_sync.py --full --config ./.config/config.json
if [ "${RUN_ON_STARTUP}" = "true" ] || [ "${RUN_ON_STARTUP}" = "1" ]; then
    echo "Running startup sync: studip_sync.py --full --config ${CONFIG_FILE}"
    python3 studip_sync.py --full --disable-api --config "${CONFIG_FILE}" || {
        echo "Warning: Startup sync encountered an issue, continuing to cron scheduler..."
    }
fi

# Step 3: Setup periodic sync via cron job: studip_sync.py --recent --config ./.config/config.json
if [ "${CRON_SCHEDULE}" != "none" ] && [ "${CRON_SCHEDULE}" != "off" ] && [ "${CRON_SCHEDULE}" != "disabled" ] && [ "${CRON_SCHEDULE}" != "0" ]; then
    echo "Configuring periodic cron sync: studip_sync.py --recent --disable-api --config ${CONFIG_FILE}"
    echo "Schedule: ${CRON_SCHEDULE}"

    mkdir -p /etc/crontabs /var/spool/cron/crontabs
    CRON_FILE="/etc/crontabs/root"

    cat <<EOF > "${CRON_FILE}"
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
${CRON_SCHEDULE} cd /app && python3 studip_sync.py --recent --disable-api --config "${CONFIG_FILE}" > /proc/1/fd/1 2> /proc/1/fd/2
EOF

    # Mirror to /var/spool/cron/crontabs if not symlinked
    if [ ! -L "/var/spool/cron/crontabs/root" ]; then
        cp "${CRON_FILE}" /var/spool/cron/crontabs/root 2>/dev/null || true
    fi

    echo "Crontab installed successfully:"
    cat "${CRON_FILE}"
    echo "Starting cron daemon (crond in foreground)..."
    exec crond -f -l 2
else
    echo "Cron schedule disabled. Container finished initial run."
fi
