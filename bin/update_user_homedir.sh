#!/bin/bash

if [ -e /etc/osdc_cloud_accounting/admin_auth ]
then
    source  /etc/osdc_cloud_accounting/admin_auth
else
    echo "Error: can not locate /etc/osdc_cloud_accounting/admin_auth"
    exit 1
fi

if [ -e /etc/osdc_cloud_accounting/settings.sh ]
then
    source  /etc/osdc_cloud_accounting/settings.sh
else
    echo "Error: can not locate /etc/osdc_cloud_accounting/settings "
    exit 1
fi



USERNAME=${1}
HOMEDIR=${2}


update_homedir() {
        echo "
dn: uid=$USERNAME,ou=people,$BASEDN
changetype: modify
replace: homeDirectory
homeDirectory: $HOMEDIR
"  | ldapmodify -a -x -D "$ADMINCN" -w$(cat $LDAP_SECRET) &>/dev/null
        if [ "$?" -ne "0" ]
        then
            echo "ERROR: changing user $USERNAME homedir in ldap"
            exit 4
        fi 
}

#Check that we have the required number of params
if   [ -z "$USERNAME" ] 
then
    echo "No username specified"
	echo "Usage: $0 USER_NAME /path/to/home/dir "
	exit 1
fi
if   [ -z "$HOMEDIR" ] 
then
    echo "No HOMEDIR specified"
	echo "Usage: $0 USER_NAME /path/to/home/dir "
	exit 1
fi

update_homedir
