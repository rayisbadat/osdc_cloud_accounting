#!/bin/bash

username=${1}

if [ "$2" == "unlock" ]
then
    operation="unlock"
    shadowExpire=-1
else
    operation="lock"
    shadowExpire=1
fi

#Set todays day since epoch
#shadowLastChange=$(( `date --utc --date "$1" +%s`/ 86400 ))
shadowLastChange=$(( `date +%s`/ 86400 ))

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



change_lastchange_time() {
    echo "dn: uid=$username,ou=people,$BASEDN
changetype: modify
replace: shadowLastChange
shadowLastChange: $shadowLastChange" | ldapmodify -a -x -D "$ADMINCN" -w$(cat $LDAP_SECRET) &>/dev/null
    if [ "$?" -ne "0" ]
    then
        echo "ldapmodify failed"
        exit 1
    fi
}


change_expired_time() {
    echo "dn: uid=$username,ou=people,$BASEDN
changetype: modify
replace: shadowExpire
shadowExpire: $shadowExpire" | ldapmodify -a -x -D "$ADMINCN" -w$(cat $LDAP_SECRET) &>/dev/null
    if [ "$?" -ne "0" ]
    then
        echo "ldapmodify failed"
        exit 1
    fi
}

toggle_user_in_keystone() {

    if [ "$operation" == "unlock" ] 
    then
        keystone_op="true"
    else
        keystone_op="false"
    fi

    keystone user-update --enabled $keystone_op  $username &>/dev/null
    if [ "$?" -ne "0" ]
    then
        echo "keystone failed to toggle enable/disable for user $username"
        exit 1
    fi
    
}


#Check that we have the required number of params
if   [ -z "$username" ]
then
    echo "ERROR: $0 \$username (lock)|unlock"
    exit 1
fi

change_expired_time
toggle_user_in_keystone
change_lastchange_time
