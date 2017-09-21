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


USERNAME=$1
PROJECT=$2
PASSWORD=$3
EMAIL=$4
HOME_DIR=$5
if [ -z "$USERNAME" ] || [ -z "$PASSWORD" ] || [ -z "$EMAIL" ] || [ -z "$HOME_DIR" ] || [ -z "$PROJECT" ]
then
	echo "Usage: $0 Username Tenant Password Email Home_Directory_Path Cloud_Name"
	exit 1
fi

set -e
set -u

if [ "$DOMAIN" != "" ]
then
    openstack user create --domain $DOMAIN --project $PROJECT --password $PASSWORD --email $EMAIL $USERNAME > /dev/null
else
    openstack user create  --project $PROJECT --password $PASSWORD --email $EMAIL $USERNAME > /dev/null
fi
openstack role add --user $USERNAME --project $PROJECT $ROLE  > /dev/null
                                        
credential_file="$HOME_DIR/.novarc"
[ ! -e $HOME_DIR ] && mkdir $HOME_DIR  
touch $credential_file

IDENTITY_URL=$(openstack catalog show keystone -f shell | perl -ne 'm|public(?:\S+)?:\s*(h\S+)| && print "$1\n"')

echo "export OS_PROJECT_NAME=$PROJECT" >> $credential_file
echo "export OS_TENANT_NAME=$PROJECT" >> $credential_file
echo "export OS_USERNAME=$USERNAME" >> $credential_file
echo "export OS_PASSWORD=$PASSWORD" >> $credential_file
echo "export OS_AUTH_URL=\"${IDENTITY_URL}/\"" >> $credential_file
[ "$IDENTITY_API_VERSION" != "" ] && echo "export OS_IDENTITY_API_VERSION=$IDENTITY_API_VERSION" >> $credential_file
[ "$IMAGE_API_VERSION" != "" ] && echo "export OS_IMAGE_API_VERSION=$IMAGE_API_VERSION" >> $credential_file
#Defaults
[ "$DOMAIN" != "" ] && echo 'export OS_DOMAIN_NAME="default"' >> $credential_file; true
[ "$DOMAIN" != "" ] && echo 'export OS_PROJECT_DOMAIN_NAME="default"' >> $credential_file; true
[ "$DOMAIN" != "" ] && echo 'export OS_USER_DOMAIN_NAME="default"' >> $credential_file; true
