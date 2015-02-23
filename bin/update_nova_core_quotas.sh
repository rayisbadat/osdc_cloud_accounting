#!/bin/bash
TENANT_NAME=${1}
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


if [ -z "$TENANT_NAME" ]
then
    echo "Usage: $0 TENANT_NAME [cores]"
	exit 1
fi
tennant_id=$(/usr/bin/keystone tenant-list 2>/dev/null | grep $TENANT_NAME | perl -ne 'm/\|\s(\S+)\s/ && print "$1"')


if [ "$tennant_id" == "" ]
then
    echo "$0 Error: No user/tennant found for $TENANT_NAME"
    exit 1
fi


if [ -z "$CORES" ]
then
    nova quota-show --tenant=${tennant_id}
    exit 0
fi

cores_int=$(awk  "BEGIN { rounded = sprintf(\"%.0f\", $CORES); print rounded }")
ram=$((2048*$cores_int))
instances=${cores_int}

if [ "$tennant_id" == "" ]
then
    echo "$0 Error: No user/tennant found for $TENANT_NAME"
    exit 1
fi


nova quota-update  --cores $cores_int $tennant_id # &>/dev/null
nova quota-update  --ram $ram $tennant_id # &>/dev/null
nova quota-update  --instances $instances $tennant_id # &>/dev/null
nova quota-update  --fixed-ips $instances $tennant_id # &>/dev/null
