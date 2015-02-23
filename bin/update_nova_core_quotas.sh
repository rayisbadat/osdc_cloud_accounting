#!/bin/bash
USERNAME=${1}
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


if [ -z "$USERNAME" ]
then
    echo "Usage: $0 USERNAME [cores]"
	exit 1
fi
tennant_id=$(/usr/bin/keystone tenant-list 2>/dev/null | grep $USERNAME | perl -ne 'm/\|\s(\S+)\s/ && print "$1"')

if [ "$tennant_id" == "" ]
then
    echo "$0 Error: No user/tennant found for $USERNAME"
    exit 1
fi


if [ -z "$CORES" ]
then
    nova-manage account quota --project=${tennant_id}
    exit 0
fi

cores_int=$(awk  "BEGIN { rounded = sprintf(\"%.0f\", $CORES); print rounded }")
ram=$((2048*$cores_int))
instances=${cores_int}

if [ "$tennant_id" == "" ]
then
    echo "$0 Error: No user/tennant found for $USERNAME"
    exit 1
fi

nova-manage account quota --project=${tennant_id} --key=cores --value=$cores_int &>/dev/null
nova-manage account quota --project=${tennant_id} --key=ram --value=$ram &>/dev/null
nova-manage account quota --project=${tennant_id} --key=instances --value=$instances &>/dev/null
nova-manage account quota --project=${tennant_id} --key=fixed_ips --value=$instances &>/dev/null
nova-manage account quota --project=${tennant_id} --key=floating_ips --value=0 &>/dev/null
