#!/bin/bash

touch_initial_file() {
    #Cant set quota till after first upload
    user_home=$(getent passwd $USERNAME | cut -d":" -f6)
    (cd $user_home; source .novarc; cd /tmp; echo $DISK_QUOTA > .sfquotaset; swift upload ${USERNAME}-sfquotaset .sfquotaset &> /dev/null ; swift delete ${USERNAME}-sfquotaset &> /dev/null; rm .sfquotaset &>/dev/null )
}

set_quota() {
    ##Set quota
    radosgw-admin quota set --quota-scope=user --uid=$tenant_id --max-size=$DISK_QUOTA &> /dev/null

    if [ ! "$?" == "0" ]
    then
        echo "ERROR: Could not set quota on $TENANT"
        exit 1
    fi

    ##Enable quota
    radosgw-admin quota enable --quota-scope=user --uid=$tenant_id &> /dev/null
    if [ ! "$?" == "0" ]
    then
        echo "ERROR: Could not enable quota on $TENANT"
        exit 1
    fi

    radosgw-admin user stats --uid=$tenant_id --sync-stats &>/dev/null
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

USERNAME=${1}
TENANT=${2}
DISK_QUOTA=${3}

if [ "$TENANT" == "" ] || [ "$DISK_QUOTA" == "" ] || [ "$USERNAME" == "" ]
then
    echo "Usage: $0 USERNAME TENANT Disk_Quota_In_Bytes"
    #echo "User and Tenant must exist before hand"
    exit 1
fi

tenant_id=$(/usr/bin/keystone tenant-list 2>/dev/null | grep $TENANT | perl -ne 'm/\|\s(\S+)\s/ && print "$1"')

if [ "$tenant_id" == "" ]
then
    echo "$0 Error: No user/tennant found for $TENANT"
    exit 1
fi

touch_initial_file
set_quota
