#!/bin/bash

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


CREDS_FILE="s3cred.txt"


tenant=${1}
username=${2}

set -e
set -u


if [ -z "$username" ] || [ -z "$tenant" ]
then
	echo "Usage: $0 tenant useranme"
	exit 1
fi
touch_initial_file() {
    #Cant set quota till after first upload
    user_home=$(getent passwd $username | cut -d":" -f6)
    (cd $user_home; source .novarc; cd /tmp; echo "42" > .sfquotaset; swift upload sfquotaset .sfquotaset &> /dev/null ; swift delete sfquotaset &> /dev/null )
}


find_tenant_uuid() {
    tenant_uuid=$(keystone tenant-get $tenant | perl -n -e'm/\|\s+id\s+\|\s+(\S+)\s+\|/ && print "$1"')
}

    
create_s3_creds() {
    json=$(radosgw-admin key create --uid=${tenant_uuid} --key-type=s3 --gen-access-key)
    access_key=$(echo $json | perl -00n -e 'undef $/; ' -e 'm|\"access_key\": "([^"]+)"|ms && print "$1\n";')
    secret_key=$(echo $json | perl -00n -e 'undef $/; ' -e 'm|\"secret_key\": "([^"]+)"|ms && print "$1\n";')
}

write_out_creds() {
    sudo su - $username  -c "echo -e access_key=${access_key}\\\nsecret_key=${secret_key} >> ${CREDS_FILE}" 
}


touch_initial_file
find_tenant_uuid
create_s3_creds
write_out_creds

