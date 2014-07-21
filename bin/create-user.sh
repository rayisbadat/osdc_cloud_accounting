#!/bin/bash
NAME=${1}
USERNAME=${2}
EMAIL=${3}
PASSWD=$(pwgen 20 1)
HOME_DIR=/home/$USERNAME
METHOD=$4
CLOUD=$5
CORE_QUOTA=$6
STORAGE_QUOTA=$7

#Check that we have the required number of params
if   [ -z "$NAME" ]  ||  [ -z "$USERNAME" ] || [ -z "$PASSWD" ] || [ -z "$EMAIL" ] || [ -z "$METHOD" ] || [ -z "$CLOUD" ] || [ -z "$CORE_QUOTA" ] || [ -z "$STORAGE_QUOTA" ]
then
	echo "Usage: $0 ACTUAL_NAME USER_NAME EMAIL METHOD CLOUD CORE_QUOTA  STORAGE_QUOTA"
	echo "Please be sure the group already exists in ldap"
    echo "METHOD: shibboleth, era, openid"
    echo "CLOUD: sullivan, atwood, adler, goldberg"
    echo "CORE_QUOTA: max cores"
    echo "STORAGE_QUOTA: TBs"
	exit 1
fi

/usr/local/sbin/create-ldap-user.sh "$NAME" "$USERNAME" "$PASSWD" "$HOME_DIR" "$STORAGE_QUOTA"
if [ $? -ne 0 ]
then
	echo "$0: create ldap user failed!"
    echo /usr/local/sbin/create-ldap-user.sh "$NAME" "$USERNAME" "$PASSWD" "$HOME_DIR" "$STORAGE_QUOTA"
	exit 1	
fi

/usr/local/sbin/create-cloud-user.sh "$USERNAME" "$PASSWD" "$EMAIL" "$HOME_DIR" "$CORE_QUOTA"
if [ $? -ne 0 ]
then
	echo "$0: create-cloud-user failed"
    echo /usr/local/sbin/create-cloud-user.sh "$USERNAME" "$PASSWD" "$EMAIL" "$HOME_DIR" "$CORE_QUOTA"
    exit 1
fi

/usr/local/sbin/create-gui-creds.sh "$USERNAME" "$PASSWD" "$EMAIL" "$METHOD" "$CLOUD" 
if [ $? -ne 0 ]
then
	echo "$0: create-gui-creds failed"
    echo /usr/local/sbin/create-gui-creds.sh "$USERNAME" "$PASSWD" "$EMAIL" "$METHOD" "$CLOUD" 
    exit 1
fi

