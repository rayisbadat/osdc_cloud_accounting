#!/bin/bash
#Change the .eucarc file to point to api.bionimbus-pdc.opensciencedatacloud.org

set -e
USERNAME=${1}
EMAIL=${2}

source ~/admin_auth

if [ -z "$USERNAME" ] 
then
	echo $0 USERNAME [\'EMAIL@TLD\']
	exit 1
fi

EUCARC=/mnt/glusterfs/users/${USERNAME}/.eucarc

MEMBER_ROLE=$(keystone role-list | perl -n -e 'm/\|\s+(\S+)\s+\|\s+memberRole\s\|/ && print $1')
TENANT=$(perl -n -e 'm|OS_TENANT_NAME=(\S+)| && print "$1"' $EUCARC )
USERNAME=$(perl -n -e 'm|OS_USERNAME=(\S+)| && print "$1"' $EUCARC )
PASSWORD=$(perl -n -e 'm|OS_PASSWORD=(\S+)| && print "$1"' $EUCARC ) 
HOMEDIR=$(getent passwd $USERNAME | cut -f6 -d":")

if [ -z "$EMAIL" ]
then
	EMAIL=$(ldapsearch -x -w$(cat /etc/pam_ldap.secret)  -D "cn=admin,dc=bionimbus,dc=nih,dc=uchicago,dc=edu" uid=$USERNAME mail 2>/dev/null | perl -ne 'm/mail:\s+(\S+)/ && print "$1\n"')
fi

if [ -z "$EMAIL" ]
then
	echo No valid email found
	exit 1
fi



function get_id () {
    echo `$@ | awk '/ id / { print $4 }'`
}

create_tenant() {
	NEW_TENANT=$(get_id keystone tenant-create --name=$TENANT)
}

create_user() {
	NEW_USER=$(get_id keystone user-create --name=$USERNAME --pass="$PASSWORD" --email=$EMAIL)
}

add_member_role() {
	keystone user-role-add --user $NEW_USER --role $MEMBER_ROLE --tenant_id $NEW_TENANT
}

create_novarc()
{
	grep OS_ $HOMEDIR/.eucarc | perl -p -e 's/bionimbus-pdc.opensciencedatacloud.org/api.bionimbus-pdcv2.opensciencedatacloud.org/;' -e 's/cloud-controller/api.bionimbus-pdcv2.opensciencedatacloud.org/;'  > $HOMEDIR/.novarc
	chown $USERNAME $HOMEDIR/.novarc
}

echo $USERNAME
echo $TENANT
echo $PASSWORD
echo $MEMBER_ROLE
echo $HOMEDIR

create_tenant
create_user
add_member_role
create_novarc
