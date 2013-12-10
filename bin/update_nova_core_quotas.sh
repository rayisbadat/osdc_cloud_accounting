#!/bin/bash
USERNAME=${1}
CORES=${2}

source /etc/osdc_cloud_accounting/admin_auth
if [ -z "$USERNAME" ] || [ -z "$CORES" ]
then
    echo "Usage: $0 USERNAME cores"
	exit 1
fi
tennant_id=$(keystone tenant-list | grep $USERNAME | perl -ne 'm/\|\s(\S+)\s/ && print "$1"')
ram=$((2048*$CORES))
instances=${CORES}

if [ "$tennant_id" == "" ]
then
    echo "No user/tennant found for $USERNAME"
    exit 1
fi

nova-manage account quota --project=${tennant_id} --key=cores --value=$CORES
nova-manage account quota --project=${tennant_id} --key=ram --value=$ram
nova-manage account quota --project=${tennant_id} --key=instances --value=$instances
nova-manage account quota --project=${tennant_id} --key=fixed_ips --value=$instances
