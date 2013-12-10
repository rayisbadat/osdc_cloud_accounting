#!/bin/bash

#set -v
#set -e

source  /etc/osdc_cloud_accounting//admin_auth

# the id of the member role
MEMBER_ROLE=$(keystone role-list | perl -ne 'm/\|\s+(\S+)\s+\|\s+Member/ && print "$1\n"')
if [ -z "$MEMBER_ROLE" ]
then
    echo "Error: Could not determine Member role id for cloud"
    exit 1
fi

USERNAME=$1
PASSWORD=$2
EMAIL=$3
HOME_DIR=$4
if [ -z "$USERNAME" ] || [ -z "$PASSWORD" ] || [ -z "$EMAIL" ] || [ -z "$HOME_DIR" ]
then
	echo "Usage: $0 Username Password Email Home_Directory_Path"
	exit 1
fi


function get_id () {
    echo `$@ | awk '/ id / { print $4 }'`
}

NEW_TENANT=$(get_id keystone tenant-create --name=$USERNAME)

NEW_USER=$(get_id keystone user-create --name=$USERNAME \
                                        --pass="$PASSWORD" \
                                        --email=$EMAIL)
                                        
# The Member role is used by Horizon and Swift so we need to keep it:                                 
keystone user-role-add --user $NEW_USER --role $MEMBER_ROLE --tenant_id $NEW_TENANT

credential_file="$HOME_DIR/.eucarc"
touch $credential_file

#This stupidity is needed to avoid a glusterfs race condition where its still propagating files
touch $credential_file 2>/dev/null || /bin/true
touch $credential_file 2>/dev/null || /bin/true
touch $credential_file 2>/dev/null || /bin/true

IDENTITY_URL=$(keystone catalog --service identity | awk '/ publicURL / { print $4 }')

echo "export OS_TENANT_NAME=$USERNAME" >> $credential_file
echo "export OS_USERNAME=$USERNAME" >> $credential_file
echo "export OS_PASSWORD=$PASSWORD" >> $credential_file
echo "export OS_AUTH_URL=\"${IDENTITY_URL}/\"" >> $credential_file

#EUCA

INFO_STRING="--os_username $USERNAME --os_password $PASSWORD --os_tenant_name $USERNAME"
NOVA_INFO_STRING="--username $USERNAME --password $PASSWORD --tenant_name $USERNAME"

CREDS=$(keystone $INFO_STRING ec2-credentials-create)

EC2_URL=$(keystone $INFO_STRING catalog --service ec2 | awk '/ publicURL / { print $4 }')

EC2_ACCESS_KEY=$(echo "$CREDS" | awk '/ access / { print $4 }')

EC2_SECRET_KEY=$(echo "$CREDS" | awk '/ secret / { print $4 }')

echo "export EC2_URL=$EC2_URL" >> $credential_file
echo "export EC2_ACCESS_KEY=$EC2_ACCESS_KEY" >> $credential_file
echo "export EC2_SECRET_KEY=$EC2_SECRET_KEY" >> $credential_file

if [ -e $HOME_DIR/.ssh/authorized_keys ]
then
    nova $NOVA_INFO_STRING keypair-add --pub_key $HOME_DIR/.ssh/authorized_keys $USERNAME
fi


