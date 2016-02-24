#!/bin/bash

set_quota() {
    ##Set quota
    radosgw-admin quota set --quota-scope=user --uid=$PROJECT --max-size=$DISK_QUOTA &> /dev/null

    if [ ! "$?" == "0" ]
    then
        echo "ERROR: Could not set quota on $TENANT"
        exit 1
    fi

    ##Enable quota
    radosgw-admin quota enable --quota-scope=user --uid=$PROJECT &> /dev/null
    if [ ! "$?" == "0" ]
    then
        echo "ERROR: Could not enable quota on $TENANT"
        exit 1
    fi

    radosgw-admin user stats --uid=$PROJECT --sync-stats &>/dev/null
}


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

PROJECT=${1}
DISK_QUOTA=${2}

if [ "$PROJECT" == "" ] || [ "$DISK_QUOTA" == "" ]
then
    echo "Usage: $0 PROJECT Disk_Quota_In_Bytes"
    exit 1
fi

set_quota
