#!/bin/bash

#set -v
#set -e

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


# the id of the member role
MEMBER_ROLE=$(/usr/bin/keystone role-list 2>/dev/null | perl -ne 'm/\|\s+(\S+)\s+\|\s+_member_/ && print "$1\n"')
if [ -z "$MEMBER_ROLE" ]
then
    echo "$0 Error: Could not determine Member role id for cloud"
    exit 1
fi

USERNAME=$1
TENANT=$2
PASSWORD=$3
EMAIL=$4
HOME_DIR=$5
CLOUD_NAME=$6
if [ -z "$USERNAME" ] || [ -z "$PASSWORD" ] || [ -z "$EMAIL" ] || [ -z "$HOME_DIR" ] || [ -z "$TENANT" ] || [ -z "$CLOUD_NAME" ]
then
	echo "Usage: $0 Username Tenant Password Email Home_Directory_Path Cloud_Name"
	exit 1
fi

function get_id () {
    echo `$@ | awk '/ id / { print $4 }'`
}

NEW_TENANT=$(keystone tenant-get $TENANT 2>/dev/null | grep id | tr -s " " | cut -d" " -f4)

extra_specs="CLOUD:$CLOUD_NAME,EMAIL:$EMAIL"
NEW_USER=$(get_id /usr/bin/keystone user-create --name=$USERNAME \
                                        --pass="$PASSWORD" \
                                        --email=$extra_specs 2>/dev/null)
                                        
# The Member role is used by Horizon and Swift so we need to keep it:                                 
/usr/bin/keystone user-role-add --user $NEW_USER --role $MEMBER_ROLE --tenant_id $NEW_TENANT &>/dev/null
if [ "$?" != "0" ]
then
    echo "ERROR: $0 failed to run: /usr/bin/keystone --debug user-role-add --user $NEW_USER --role $MEMBER_ROLE --tenant_id $NEW_TENANT "
    exit 1
fi

credential_file="$HOME_DIR/.novarc"
touch $credential_file

IDENTITY_URL=$(/usr/bin/keystone catalog --service identity 2>/dev/null | awk '/ publicURL / { print $4 }' | head -n1)

echo "export OS_TENANT_NAME=$TENANT" >> $credential_file
echo "export OS_USERNAME=$USERNAME" >> $credential_file
echo "export OS_PASSWORD=$PASSWORD" >> $credential_file
echo "export OS_AUTH_URL=\"${IDENTITY_URL}/\"" >> $credential_file

#EUCA

INFO_STRING="--os-username $USERNAME --os-password $PASSWORD --os-tenant-name $USERNAME"
#NOVA_INFO_STRING="--username $USERNAME --password $PASSWORD --tenant_name $USERNAME"
#Apparently this changed between versions
NOVA_INFO_STRING=$INFO_STRING

CREDS=$(/usr/bin/keystone $INFO_STRING ec2-credentials-create 2>/dev/null )

EC2_URL=$(/usr/bin/keystone $INFO_STRING catalog --service ec2 2>/dev/null | awk '/ publicURL / { print $4 }')

EC2_ACCESS_KEY=$(echo "$CREDS" | awk '/ access / { print $4 }')

EC2_SECRET_KEY=$(echo "$CREDS" | awk '/ secret / { print $4 }')

echo "export EC2_URL=$EC2_URL" >> $credential_file
echo "export EC2_ACCESS_KEY=$EC2_ACCESS_KEY" >> $credential_file
echo "export EC2_SECRET_KEY=$EC2_SECRET_KEY" >> $credential_file

