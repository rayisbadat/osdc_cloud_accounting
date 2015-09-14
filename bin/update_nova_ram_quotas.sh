#!/bin/bash
TENANT_NAME=${1}
RAM=${2}

#One day openstack will actually implment this quota feature
#EPHEMERAL=${}

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
    echo "Usage: $0 TENANT_NAME [ram]"
	exit 1
fi
tennant_id=$(/usr/bin/keystone tenant-list 2>/dev/null | grep " $TENANT_NAME " | perl -ne 'm/\|\s(\S+)\s/ && print "$1"')


if [ "$tennant_id" == "" ]
then
    echo "$0 Error: No user/tennant found for $TENANT_NAME"
    exit 1
fi

if [ -z "$RAM" ]
then
    nova quota-show --tenant=${tennant_id}
    exit 0
fi

#force it to int, jic
ram_int=$(awk  "BEGIN { rounded = sprintf(\"%.0f\", $RAM); print rounded }")

nova quota-update  --force --ram $ram_int $tennant_id # &>/dev/null
