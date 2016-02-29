#!/bin/bash
NAME=${1}
USERNAME=${2}
TENANT=${3}
EMAIL=${4}
PASSWD=$(pwgen 20 1)
HOME_DIR=/home/$USERNAME
METHOD=$5
CLOUD=$6

#Check that we have the required number of params
if   [ -z "$NAME" ]  ||  [ -z "$USERNAME" ] || [ -z "$PASSWD" ] || [ -z "$EMAIL" ] || [ -z "$METHOD" ] || [ -z "$CLOUD" ] || [ -z "$TENANT" ]
then
	echo "Usage: $0 ACTUAL_NAME USER_NAME TENANT EMAIL METHOD CLOUD "
	echo "Please be sure the group already exists in ldap"
    echo "METHOD: shibboleth, era, openid"
    echo "CLOUD: sullivan, atwood, adler, goldberg, tcga"
	exit 1
fi

/usr/local/sbin/create-ldap-user.sh "$NAME" "$USERNAME" "$PASSWD" "$HOME_DIR"
if [ $? -ne 0 ]
then
	echo "$0: create ldap user failed!"
    echo /usr/local/sbin/create-ldap-user.sh "$NAME" "$USERNAME" "$PASSWD" "$HOME_DIR"
	exit 1	
fi

/usr/local/sbin/create-cloud-user.sh "$USERNAME" "$TENANT" "$PASSWD" "$EMAIL" "$HOME_DIR" "$CLOUD"
if [ $? -ne 0 ]
then
	echo "$0: create-cloud-user failed"
    echo /usr/local/sbin/create-cloud-user.sh "$USERNAME" "$TENANT" "$PASSWD" "$EMAIL" "$HOME_DIR"
    exit 1
fi

/usr/local/sbin/create-gui-creds.sh "$USERNAME" "$PASSWD" "$EMAIL" "$METHOD" "$CLOUD" 
if [ $? -ne 0 ]
then
	echo "$0: create-gui-creds failed"
    echo /usr/local/sbin/create-gui-creds.sh "$USERNAME" "$PASSWD" "$EMAIL" "$METHOD" "$CLOUD" 
    exit 1
fi

