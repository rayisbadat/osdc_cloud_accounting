#!/bin/bash
NAME=${1}
USERNAME=${2}
TENANT=${3}
EMAIL=${4}
PASSWD=$(pwgen 20 1)
METHOD=$5
TUKEY_CLOUD_NAME=$6
CLOUD_NAME=$7


if [ -e /etc/osdc_cloud_accounting/settings.sh ]
then
    source  /etc/osdc_cloud_accounting/settings.sh
else
    echo "$0 Error: can not locate /etc/osdc_cloud_accounting/settings.sh "
    exit 1
fi

#Check that we have the required number of params
if   [ -z "$NAME" ]  ||  [ -z "$USERNAME" ] || [ -z "$TENANT" ] || [ -z "$EMAIL" ] || [ -z "$PASSWD" ] || [ -z "$METHOD" ] || [ -z "$TUKEY_CLOUD_NAME" ]
then
	echo "Usage: $0 ACTUAL_NAME USER_NAME TENANT EMAIL METHOD TUKEY_NAME [CLOUD_NAME] "
	echo "Please be sure the group already exists in ldap"
    echo "METHOD: shibboleth, era, openid"
    echo "TUKEY_NAME: sullivan, atwood, adler, goldberg, tcga"
    echo "Cloud Name: Cloud  Name as in conf file settings['general']['cloud']"
	exit 1
fi

if [ -z "CLOUD_NAME" ]
then
    CLOUD_NAME=${TUKEY_CLOUD_NAME}  
fi

set -e
set -u

HOME_DIR="${HOME_DIR_ROOT}/$USERNAME"

#/usr/local/sbin/create-ldap-user.sh "$NAME" "$USERNAME" "$PASSWD" "$HOME_DIR"
#if [ $? -ne 0 ]
#then
#	echo "$0: create ldap user failed!"
#    echo /usr/local/sbin/create-ldap-user.sh "$NAME" "$USERNAME" "$PASSWD" "$HOME_DIR"
#	exit 1	
#fi

/usr/local/sbin/create-cloud-user.sh "$USERNAME" "$TENANT" "$PASSWD" "$EMAIL" "$HOME_DIR"
if [ $? -ne 0 ]
then
	echo "$0: create-cloud-user failed"
    echo /usr/local/sbin/create-cloud-user.sh "$USERNAME" "$TENANT" "$PASSWD" "$EMAIL" "$HOME_DIR"
    exit 1
fi

#/usr/local/sbin/create-gui-creds.sh "$USERNAME" "$PASSWD" "$EMAIL" "$METHOD" "$TUKEY_CLOUD_NAME"
#if [ $? -ne 0 ]
#then
#	echo "$0: create-gui-creds failed"
#    echo /usr/local/sbin/create-gui-creds.sh "$USERNAME" "$PASSWD" "$EMAIL" "$METHOD" "$CLOUD" 
#    exit 1
#fi

