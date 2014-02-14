#!/bin/bash
USERNAME=${1}
PASSWD=${2}



if [ -z "$USERNAME" ] || [ -z "$PASSWD" ]
then
    echo "Usage: $0 USERNAME PASSWD"
        exit 1
fi

#Pull in the ldap info
if [ -e /etc/osdc_cloud_accounting/settings.sh ]
then
    source  /etc/osdc_cloud_accounting/settings.sh
else
    echo "$0 Error: can not locate /etc/osdc_cloud_accounting/settings "
    exit 1
fi



add_samba_creds() {
    # This is inheriently unsecure. The mhash/nthash is the old easly broken one,
    # Ldap needs to be configured to not allow anonymous query of the passwords.

    LM_PASSWORD=$(perl -e'use Crypt::SmbHash qw(lmhash nthash);' -e "print lmhash('$PASSWD');" )
    NT_PASSWORD=$(perl -e'use Crypt::SmbHash qw(lmhash nthash);' -e "print nthash('$PASSWD');" )
    SALT=$(pwgen 8 1)
    CRYPT_PASSWORD=$(perl -e "print crypt('$PASSWD', '\$6\$$SALT')" )
    SAMBA_SID=$ADC_SID-$((UID_NUM*2+1000))


    echo "
dn: uid=$USERNAME,ou=people,$BASEDN
changetype: modify
replace: sambaLMPassword
sambaLMPassword: $LM_PASSWORD
-
replace: sambaNTPassword
sambaNTPassword: $NT_PASSWORD
-
replace: sambaSID
sambaSID: $SAMBA_SID
-
replace: sambaAcctFlags
sambaAcctFlags: [UX]
" | ldapmodify -a -x -D "$ADMINCN" -w$(cat $LDAP_SECRET) &>/dev/null
    if [ "$?" -ne "0" ]
    then
            echo "$0 Error: ldapmodify failed to add samba creds"
            exit 1
    fi
}

if [ -n "$ADC_SID" ]
then
        add_samba_creds
fi
