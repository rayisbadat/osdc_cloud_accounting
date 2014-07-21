#!/bin/bash

touch_initial_file(){
    #Cant set quota till after first upload
    tenant_home=$(getent passwd $TENANT | cut -d":" -f6)
    (cd $tenant_home; source .novarc; cd /tmp; echo $DISK_QUOTA > .quota; swift upload quota .quota &> /dev/null ; swift delete quota &> /dev/null )

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

TENANT=${1}
DISK_QUOTA=${2}

if [ -z "$TENANT" ]
then
    echo "Usage: $0 USERNAME/TENANT Disk_Quota_In_Bytes"
    echo "If ~{USERNAME|TENANT}/.novarc doesnt exist or no file has ever been upload quota will fail.  'su -'  to a valid user, and then `swift upload .quota`"
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
