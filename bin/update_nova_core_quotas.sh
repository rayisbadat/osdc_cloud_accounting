#!/bin/bash
PROJECT=${1}
CORES=${2}

if [ -e /etc/osdc_cloud_accounting/admin_auth ]
then
    source  /etc/osdc_cloud_accounting/admin_auth
else
    echo "$0 Error: can not locate /etc/osdc_cloud_accounting/admin_auth"
    exit 1
fi

if [ -e /etc/osdc_cloud_accounting/settings.sh ]
then
    source  /etc/osdc_cloud_accounting/settings.sh
else
    echo "$0 Error: can not locate /etc/osdc_cloud_accounting/settings "
    exit 1
fi


if [ -z "$PROJECT" ]
then
    echo "Usage: $0 PROJECT [cores]"
	exit 1
fi

if [ -z "$CORES" ]
then
    openstack quota show $PROJECT
    exit 0
fi

#Cores
cores_int=$(awk  "BEGIN { rounded = sprintf(\"%.0f\", $CORES); print rounded }")
instances=${cores_int}

openstack quota set --cores $cores_int --instances $instances --fixed-ips $instances $PROJECT &>/dev/null
neutron quota-update --port $instances --tenant_id $( openstack project show  $PROJECT -fshell | grep '^id="' | cut -f2 -d'"' ) &>/dev/null
