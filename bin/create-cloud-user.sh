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
PASSWORD=$2
EMAIL=$3
HOME_DIR=$4
CORE_QUOTA=$5
if [ -z "$USERNAME" ] || [ -z "$PASSWORD" ] || [ -z "$EMAIL" ] || [ -z "$HOME_DIR" ] || [ -z "$CORE_QUOTA" ]
then
	echo "Usage: $0 Username Password Email Home_Directory_Path STORAGE_QUOTA"
	exit 1
fi

function get_id () {
    echo `$@ | awk '/ id / { print $4 }'`
}

NEW_TENANT=$(get_id /usr/bin/keystone tenant-create --name=$USERNAME 2>/dev/null)

NEW_USER=$(get_id /usr/bin/keystone user-create --name=$USERNAME \
                                        --pass="$PASSWORD" \
                                        --email=$EMAIL 2>/dev/null)
                                        
# The Member role is used by Horizon and Swift so we need to keep it:                                 
/usr/bin/keystone user-role-add --user $NEW_USER --role $MEMBER_ROLE --tenant_id $NEW_TENANT &>/dev/null
if [ "$?" != "0" ]
then
    echo "ERROR: $0 failed to run: /usr/bin/keystone --debug user-role-add --user $NEW_USER --role $MEMBER_ROLE --tenant_id $NEW_TENANT "
    exit 1
fi

credential_file="$HOME_DIR/.novarc"
touch $credential_file

#This stupidity is needed to avoid a glusterfs race condition where its still propagating files
#touch $credential_file 2>/dev/null || /bin/true
#touch $credential_file 2>/dev/null || /bin/true
#touch $credential_file 2>/dev/null || /bin/true

IDENTITY_URL=$(/usr/bin/keystone catalog --service identity 2>/dev/null | awk '/ publicURL / { print $4 }')

echo "export OS_TENANT_NAME=$USERNAME" >> $credential_file
echo "export OS_USERNAME=$USERNAME" >> $credential_file
echo "export OS_PASSWORD=$PASSWORD" >> $credential_file
echo "export OS_AUTH_URL=\"${IDENTITY_URL}/\"" >> $credential_file

#EUCA

INFO_STRING="--os_username $USERNAME --os_password $PASSWORD --os_tenant_name $USERNAME"
NOVA_INFO_STRING="--username $USERNAME --password $PASSWORD --tenant_name $USERNAME"

CREDS=$(/usr/bin/keystone $INFO_STRING ec2-credentials-create 2>/dev/null )

EC2_URL=$(/usr/bin/keystone $INFO_STRING catalog --service ec2 2>/dev/null | awk '/ publicURL / { print $4 }')

EC2_ACCESS_KEY=$(echo "$CREDS" | awk '/ access / { print $4 }')

EC2_SECRET_KEY=$(echo "$CREDS" | awk '/ secret / { print $4 }')

echo "export EC2_URL=$EC2_URL" >> $credential_file
echo "export EC2_ACCESS_KEY=$EC2_ACCESS_KEY" >> $credential_file
echo "export EC2_SECRET_KEY=$EC2_SECRET_KEY" >> $credential_file

if [ -e $HOME_DIR/.ssh/authorized_keys ]
then
    nova $NOVA_INFO_STRING keypair-add --pub_key $HOME_DIR/.ssh/authorized_keys $USERNAME  &>/dev/null
fi

#/usr/local/sbin/update_nova_core_quotas.sh $USERNAME $CORE_QUOTA 
