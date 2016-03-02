#!/bin/bash
USERNAME=${1}
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


if [ -z "$USERNAME" ]
then
    echo "Usage: $0 USERNAME [ips]"
    exit 1
fi

tennant_id=$(/usr/bin/keystone tenant-list 2>/dev/null | grep " $USERNAME " | perl -ne 'm/\|\s(\S+)\s/ && print "$1"')


if [ "$tennant_id" == "" ]
then
    echo "$0 Error: No user/tennant found for $USERNAME"
    exit 1
fi

if [ -z "$IPS" ]
then
    #nova-manage account quota --project=${tennant_id}
    nova quota-show --tenant  ${tennant_id}
    
    exit 0
fi

ips_int=$(awk  "BEGIN { rounded = sprintf(\"%.0f\", $IPS); print rounded }")
nova quota-update  --floating_ips $ips_int  ${tennant_id} #&>/dev/null
