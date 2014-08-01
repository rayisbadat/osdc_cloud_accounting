#!/bin/bash

set -x 
username=${1}
shadowExpire=${2}

#Set todays day since epoch
shadowLastChange=$(echo $((`date --utc --date "$1" +%s`/86400)))

#Pull in the ldap info
if [ -e /etc/osdc_cloud_accounting/settings.sh ]
then
    source  /etc/osdc_cloud_accounting/settings.sh
else
    echo "$0 Error: can not locate /etc/osdc_cloud_accounting/settings.sh "
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

#Check that we have the required number of params
if   [ ! -z "$username" ]  &&  [ ! -z "$shadowExpire" ]
then
    change_expired_time
else
    echo "ERROR: $0 \$username \$days_since_epoch"
    exit 1
fi

#Check that we have the required number of params
if [ ! -z "$shadowLastChange" ]
then
    change_lastchange_time
fi
