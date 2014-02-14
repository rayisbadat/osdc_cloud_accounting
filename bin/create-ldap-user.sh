#!/bin/bash
###
## Author: Ray Powell <rpowell1@uchicago.edu>
## License: Apache2
## Comment: Script requires the cpu utility be configured on target servers, and /etc/skel setup.
##          mkdir --mode=700 /etc/skel/.ssh
####

NAME=${1}
USERNAME=${2}
PASSWD=${3}
HOME_DIR=${4}
STORAGE_QUOTA=${5}
DEFAULT_SHELL=/bin/bash
UID_NUM=$(getent passwd $USERNAME | cut -f3 -d":" )

#Pull in the ldap info
if [ -e /etc/osdc_cloud_accounting/settings.sh ]
then
    source  /etc/osdc_cloud_accounting/settings.sh
else
    echo "$0 Error: can not locate /etc/osdc_cloud_accounting/settings "
    exit 1
fi


#Check that we have the required number of params
if   [ -z "$NAME" ]  ||  [ -z "$USERNAME" ] || [ -z "$PASSWD" ] || [ -z "$HOME_DIR" ] || [ -z "$STORAGE_QUOTA" ]
then
	echo "Usage: $0 ACTUAL_NAME USER_NAME PASSWORD HOME_DIR STORAGE_QUOTA"
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
add: objectClass
objectClass: sambaSamAccount
-
add: sambaLMPassword
sambaLMPassword: $LM_PASSWORD
-
add: sambaNTPassword
sambaNTPassword: $NT_PASSWORD
-
add: sambaSID
sambaSID: $SAMBA_SID
-
add: sambaAcctFlags
sambaAcctFlags: [UX]
" | ldapmodify -a -x -D "$ADMINCN" -w$(cat $LDAP_SECRET) &>/dev/null
    if [ "$?" -ne "0" ]
    then
	    echo "$0 Error: ldapmodify failed for CIFS creds"
	    exit 1
    fi
}
create_user() {
    /usr/sbin/cpu useradd -s${DEFAULT_SHELL} -Gsudo_apt -m $USERNAME  &>/dev/null
    if [ "$?" -ne "0" ]
    then
	    echo "$0 Error: cpu useradd failed"
	    exit 1
    fi

    #create the user readable one
    echo "username=$USERNAME" > $HOME_DIR/smbpassword.txt
    echo "password=$PASSWD" >> $HOME_DIR/smbpassword.txt
    chmod o-rwx $HOME_DIR &>/dev/null
}

set_quota(){
    gluster volume quota $GLUSTER_VOL limit-usage /users/${USERNAME} ${STORAGE_QUOTA} &>/dev/null
}

##Actually run commands
create_user
set_quota

if [ -n "$ADC_SID" ]
then
	add_samba_creds
fi

