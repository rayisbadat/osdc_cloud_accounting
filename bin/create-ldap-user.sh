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
DEFAULT_SHELL=/bin/bash

#Pull in the ldap info
if [ -e /etc/osdc_cloud_accounting/settings.sh ]
then
    source  /etc/osdc_cloud_accounting/settings.sh
else
    echo "$0 Error: can not locate /etc/osdc_cloud_accounting/settings.sh "
    exit 1
fi


#Check that we have the required number of params
if   [ -z "$NAME" ]  ||  [ -z "$USERNAME" ] || [ -z "$PASSWD" ] || [ -z "$HOME_DIR" ]
then
	echo "Usage: $0 ACTUAL_NAME USER_NAME PASSWORD HOME_DIR STORAGE_QUOTA"
	exit 1
fi


create_user() {
    /usr/sbin/cpu useradd -s${DEFAULT_SHELL} -m $USERNAME  &>/dev/null
    if [ "$?" -ne "0" ]
    then
	    echo "$0 Error: cpu useradd failed"
        echo /usr/sbin/cpu useradd -s${DEFAULT_SHELL} -m $USERNAME
	    exit 1
    fi

    chmod o-rwx $HOME_DIR &>/dev/null
}

create_qrcode() {
    reset_totp.sh $USERNAME
}

##Actually run commands
create_user
#Yes this is neccessary because something is stupid.  Turn it off or dont recycle
## And randomly getent function will give inconsistant results from ldap.
[ -x '/etc/init.d/nscd' ] && /etc/init.d/nscd restart &>/dev/null

create_qrcode
