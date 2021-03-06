#!/bin/bash
#
# lib/masakari
# Functions to control the configuration and operation of the **Masakari** service

# Dependencies:
# ``functions`` file
# ``DEST``, ``STACK_USER`` must be defined
# ``SERVICE_{HOST|PROTOCOL|TOKEN}`` must be defined

# ``stack.sh`` calls the entry points in this order:
#
# install_masakari
# configure_masakari
# init_masakari
# start_masakari
# stop_masakari
# cleanup_masakari

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set +o xtrace

# Functions
# ---------

# setup_masakari_logging() - Adds logging configuration to conf files
function setup_masakari_logging {
    local CONF=$1
    iniset $CONF DEFAULT debug $ENABLE_DEBUG_LOG_LEVEL
    iniset $CONF DEFAULT use_syslog $SYSLOG
    if [ "$LOG_COLOR" == "True" ] && [ "$SYSLOG" == "False" ]; then
        # Add color to logging output
        setup_colorized_logging $CONF DEFAULT tenant user
    fi
}

# create_masakari_accounts() - Set up common required masakari accounts

# Tenant               User       Roles
# ------------------------------------------------------------------
# service              masakari     admin        # if enabled

function create_masakari_accounts {
    if [[ "$ENABLED_SERVICES" =~ "masakari" ]]; then

        create_service_user "masakari" "admin"

        local masakari_service=$(get_or_create_service "masakari" \
            "ha" "OpenStack High Availability")
        get_or_create_endpoint $masakari_service \
            "$REGION_NAME" \
            "http://$SERVICE_HOST:$MASAKARI_SERVICE_PORT/v1/\$(tenant_id)s" \
            "http://$SERVICE_HOST:$MASAKARI_SERVICE_PORT/v1/\$(tenant_id)s" \
            "http://$SERVICE_HOST:$MASAKARI_SERVICE_PORT/v1/\$(tenant_id)s"
    fi
}

# stack.sh entry points
# ---------------------

# cleanup_masakari() - Remove residual data files, anything left over from previous
# runs that a clean run would need to clean up
function cleanup_masakari {
# Clean up dirs
    rm -fr $MASAKARI_AUTH_CACHE_DIR/*
    rm -fr $MASAKARI_CONF_DIR/*
}

# iniset_conditional() - Sets the value in the inifile, but only if it's
# actually got a value
function iniset_conditional {
    local FILE=$1
    local SECTION=$2
    local OPTION=$3
    local VALUE=$4

    if [[ -n "$VALUE" ]]; then
        iniset ${FILE} ${SECTION} ${OPTION} ${VALUE}
    fi
}

# configure_masakari() - Set config files, create data dirs, etc
function configure_masakari {
    setup_develop $MASAKARI_DIR

    # Create the masakari conf dir and cache dirs if they don't exist
    sudo install -d -o $STACK_USER ${MASAKARI_CONF_DIR} ${MASAKARI_AUTH_CACHE_DIR}

    # Copy api-paste file over to the masakari conf dir
    cp $MASAKARI_LOCAL_API_PASTE_INI $MASAKARI_API_PASTE_INI

    # Copy policy.json file over to the masakari conf dir
    cp $MASAKARI_LOCAL_POLICY_JSON $MASAKARI_POLICY_JSON

    # (Re)create masakari conf files
    rm -f $MASAKARI_CONF

    # (Re)create masakari api conf file if needed
    if is_service_enabled masakari-api; then
        oslo-config-generator --namespace keystonemiddleware.auth_token \
                          --namespace masakari \
                          --namespace oslo.db \
                          > $MASAKARI_CONF

        # Set common configuration values (but only if they're defined)
        iniset $MASAKARI_CONF DEFAULT masakari_api_workers "$API_WORKERS"
        iniset $MASAKARI_CONF database connection `database_connection_url masakari`
        setup_masakari_logging $MASAKARI_CONF

        configure_auth_token_middleware $MASAKARI_CONF masakari $MASAKARI_AUTH_CACHE_DIR
    fi

    # Set os_privileged_user credentials (used for connecting nova service)
    iniset $MASAKARI_CONF DEFAULT os_privileged_user_name nova
    iniset $MASAKARI_CONF DEFAULT os_privileged_user_auth_url "${KEYSTONE_AUTH_PROTOCOL}://${KEYSTONE_AUTH_HOST}/identity_admin"
    iniset $MASAKARI_CONF DEFAULT os_privileged_user_password "$SERVICE_PASSWORD"
    iniset $MASAKARI_CONF DEFAULT os_privileged_user_tenant "$SERVICE_PROJECT_NAME"
    iniset $MASAKARI_CONF DEFAULT graceful_shutdown_timeout "$SERVICE_GRACEFUL_SHUTDOWN_TIMEOUT"
}

# install_masakari() - Collect source and prepare
function install_masakari {
    setup_develop $MASAKARI_DIR
}

# init_masakari() - Initializes Masakari Database as a Service
function init_masakari {
    # (Re)Create masakari db
    recreate_database masakari

    # Initialize the masakari database
    $MASAKARI_MANAGE db sync

    # Add an admin user to the 'tempest' alt_demo tenant.
    # This is needed to test the guest_log functionality.
    # The first part mimics the tempest setup, so make sure we have that.
    ALT_USERNAME=${ALT_USERNAME:-alt_demo}
    ALT_TENANT_NAME=${ALT_TENANT_NAME:-alt_demo}
    get_or_create_project ${ALT_TENANT_NAME} default
    get_or_create_user ${ALT_USERNAME} "$ADMIN_PASSWORD" "default" "alt_demo@example.com"
    get_or_add_user_project_role Member ${ALT_USERNAME} ${ALT_TENANT_NAME}

    # The second part adds an admin user to the tenant.
    ADMIN_ALT_USERNAME=${ADMIN_ALT_USERNAME:-admin_${ALT_USERNAME}}
    get_or_create_user ${ADMIN_ALT_USERNAME} "$ADMIN_PASSWORD" "default" "admin_alt_demo@example.com"
    get_or_add_user_project_role admin ${ADMIN_ALT_USERNAME} ${ALT_TENANT_NAME}
}

# start_masakari() - Start running processes, including screen
function start_masakari {
    run_process masakari-api "$MASAKARI_BIN_DIR/masakari-api --config-file=$MASAKARI_CONF --debug"
    run_process masakari-engine "$MASAKARI_BIN_DIR/masakari-engine --config-file=$MASAKARI_CONF --debug"
}

# stop_masakari() - Stop running processes
function stop_masakari {
    # Kill the masakari screen windows
    local serv
    for serv in masakari-engine masakari-api; do
        stop_process $serv
    done
}

# Dispatcher for masakari plugin
if is_service_enabled masakari; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        echo_summary "Installing Masakari"
        install_masakari
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        echo_summary "Configuring Masakari"
        configure_masakari

        if is_service_enabled key; then
            create_masakari_accounts
        fi

    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        # Initialize masakari
        init_masakari

        # Start the masakari API and masakari taskmgr components
        echo_summary "Starting Masakari"
        start_masakari
    fi

    if [[ "$1" == "unstack" ]]; then
        stop_masakari
        cleanup_masakari
    fi
fi

# Restore xtrace
$XTRACE

# Tell emacs to use shell-script-mode
## Local variables:
## mode: shell-script
## End:

