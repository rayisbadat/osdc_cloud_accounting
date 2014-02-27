#!/bin/bash
CLOUD=${1}
USERNAME=${2}
PURGE=${3}
HOME_DIR=/glusterfs/users/$USERNAME
RESERVEDNAMES=" adminUser ec2 nova glance swift "

#Pull in the ldap info
if [ -e /usr/local/src/g14-mkaccount/.settings ]
then
    source  /usr/local/src/g14-mkaccount/.settings
else
    echo "Error: can not locate  /usr/local/src/g14-mkaccount/.settings "
    exit 1
fi



check_reserved() {
    if [[  "$RESERVEDNAMES" =~ "$USERNAME" ]]
    then
        echo "ERROR: TRIED DELETING SYSTEM USER!!!!"
        exit 1
    fi
}


remove_nova_tenant() {
    ssh -t lacadmin@${CLOUD}.opensciencedatacloud.org "sudo /usr/local/sbin/delete-user-worker.sh ${FUNCNAME}  ${USERNAME}" 2>/dev/null
}
remove_nova_user() {
    ssh -t lacadmin@${CLOUD}.opensciencedatacloud.org "sudo /usr/local/sbin/delete-user-worker.sh ${FUNCNAME}  ${USERNAME}" 2>/dev/null

}
remove_user() {
    ssh -t lacadmin@${CLOUD}.opensciencedatacloud.org "sudo /usr/local/sbin/delete-user-worker.sh ${FUNCNAME}  ${USERNAME}" 2>/dev/null
}
remove_user_purge() {
    ssh -t lacadmin@${CLOUD}.opensciencedatacloud.org "sudo /usr/local/sbin/delete-user-worker.sh ${FUNCNAME}  ${USERNAME}" 2>/dev/null
}
remove_gui_creds() {
    ssh -t lacadmin@${CLOUD}.opensciencedatacloud.org "sudo /usr/local/sbin/delete-user-worker.sh ${FUNCNAME}  ${USERNAME}" 2>/dev/null

}
remove_quota(){
   ssh -t lacadmin@${CLOUD}.opensciencedatacloud.org -A " ssh -t lacadmin@gluster-controller 'sudo gluster volume quota $GLUSTER_VOL remove /users/$USERNAME'" 2>/dev/null
}

remove_tukey_user() {
    #/usr/local/sbin/delete_tukey_user.sh $USERNAME
    ssh ubuntu@www.opensciencedatacloud.org "/var/www/tukey/tukey_middleware/tools/with_venv.sh python /var/www/tukey/tukey_middleware/tools/create_tukey_user.py  -r $CLOUD $USERNAME" 2>/dev/null

}

#Check that we have the required number of params
if   [ -z "$USERNAME" ] 
then
	echo "Usage: $0 CLOUD USER_NAME [purge] "
	exit 1
fi
if [ -z "$CLOUD" ] 
then
    echo "Need to specify cloud"
    exit 1
fi

if [ "$PURGE" != "purge" ] && [ -n "$PURGE" ]
then
    echo "Only accepted value is 'purge' for third argument"
    exit 1
fi  



check_reserved
remove_nova_user
remove_nova_tenant
remove_gui_creds
remove_quota
remove_tukey_user 
if [ "$PURGE" ]
then
    echo "PURGING"
    remove_user_purge
else
    remove_user
fi
