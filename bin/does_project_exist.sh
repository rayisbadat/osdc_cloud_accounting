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
    echo "Usage: $0 PROJECT"
    exit 1
fi

openstack project show $PROJECT &>/dev/null 
if [ ! "$?"  == "0" ]
then
    echo "no"
    exit 1
else
    echo "yes"
    exit 0
fi
