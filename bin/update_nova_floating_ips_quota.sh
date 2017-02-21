#!/bin/bash
PROJECT=${1}
IPS=${2}

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
    echo "Usage: $0 PROJECT [ips]"
    exit 1
fi

if [ -z "$IPS" ]
then
    openstack quota show $PROJECT
    exit 0
fi

ips_int=$(awk  "BEGIN { rounded = sprintf(\"%.0f\", $IPS); print rounded }")
openstack quota set --floating-ips $ips_int $PROJECT &>/dev/null
