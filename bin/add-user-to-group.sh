#!/bin/bash

if [ -e /etc/osdc_cloud_accounting/admin_auth ]
then
    source  /etc/osdc_cloud_accounting/admin_auth
else
    echo "Error: can not locate /etc/osdc_cloud_accounting/admin_auth"
    exit 1
fi


#Pull in the ldap info
if [ -e /etc/osdc_cloud_accounting/settings.sh ]
then
    source  /etc/osdc_cloud_accounting/settings.sh
else
    echo "Error: can not locate /etc/osdc_cloud_accounting/settings "
    exit 1
fi

USERNAME=${1}
GROUP=${2}


RESERVEDNAMES=" adminUser ec2 nova glance swift "

check_reserved() {
    if [[  "$RESERVEDNAMES" =~ "$USERNAME" ]]
    then
        echo "ERROR: TRIED DELETING SYSTEM USER!!!!"
        exit 1
    fi
}
add_user_to_ldap_groups() {
        echo "dn: cn=$GROUP,ou=group,$BASEDN
changetype: modify
add: memberUid
memberUid: $USERNAME"  | ldapmodify -a -x -D "$ADMINCN" -w$(cat $LDAP_SECRET) &>/dev/null
        if [ "$?" -ne "0" ]
        then
            echo "ERROR: adding user $USERNAME to ldap group $group failed"
            exit 4
        fi 
}

#Check that we have the required number of params
if   [ -z "$USERNAME" ] 
then
	echo "Usage: $0 USER_NAME GROUP "
	exit 1
fi

check_reserved
add_user_to_ldap_groups
