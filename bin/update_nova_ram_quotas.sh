#!/bin/bash
PROJECT=${1}
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

if [ -z "$PROJECT" ]
then
    echo "Usage: $0 PROJECT [ram]"
	exit 1
fi
if [ -z "$RAM" ]
then
    openstack quota show $PROJECT
    exit 0
fi

#force it to int, jic
ram_int=$(awk  "BEGIN { rounded = sprintf(\"%.0f\", $RAM); print rounded }")

openstack quota set --ram $ram_int $PROJECT &>/dev/null
