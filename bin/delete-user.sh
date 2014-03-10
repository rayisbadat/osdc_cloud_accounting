#!/bin/bash
USERNAME=${1}
CLOUD=${2}
PURGE=${3}
HOME_DIR=/glusterfs/users/$USERNAME
RESERVEDNAMES=" adminUser ec2 nova glance swift "

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

if [ -z "$USERNAME" ] || [ -z "$CLOUD" ] 
then
    echo "Usage: $0 USERNAME CLOUD [PURGE]"
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
    tenant_id=$( keystone tenant-list | grep " $USERNAME "  | cut -f2 -d" " )
    if [ "$tenant_id" == "" ]
    then
        echo "ERROR: Can not establish tenan_id of user: $USERNAME"
        #exit 2
    fi
    keystone tenant-delete $tenant_id
    if [ "$?" != "0" ]
    then
        echo "ERROR: Error deleteing tenant: $USERNAME $tenant_id"
        #exit 2
    fi

}
remove_nova_user() {
    user_id=$( keystone user-list | grep " $USERNAME "  | cut -f2 -d" " )
    if [ "$user_id" == "" ]
    then
        echo "ERROR: Can not user_id of user: $USERNAME"
        #exit 3
    fi
    keystone user-delete $user_id
    if [ "$?" != "0" ]
    then
        echo "ERROR: Error deleteing user: $USERNAME $user_id"
        #exit 3
    fi
}
remove_user() {
        /usr/sbin/cpu usermod -G"$USERNAME"  $USERNAME 2>/dev/null && /usr/sbin/cpu userdel ${REMOVE_OPT} $USERNAME 2>/dev/null && /usr/sbin/cpu groupdel $USERNAME 2>/dev/null
        if [ "$?" -ne "0" ]
        then
            echo "ERROR: removing user $USERNAME from ldap group $group failed"
            exit 4
        fi
}
remove_user_purge() {
    REMOVE_OPT='--removehome'
    remove_user
}
remove_gui_creds() {
    if [[   "$USERNAME" =~ ".." ]] || [[ "$USERNAME" =~ "/" ]]
    then
        echo "ERROR: Bad character(s) detected in username $USERNAME, possible error could delete system files "
        exit 6
    fi
    if [ -d /var/lib/cloudgui/users/$USERNAME ]
    then
        rm -rf /var/lib/cloudgui/users/$USERNAME
    fi
}
remove_home_dir() {
    if [[   "$USERNAME" =~ ".." ]] || [[ "$USERNAME" =~ "/" ]]
    then
        echo "ERROR: Bad character(s) detected in username $USERNAME, possible error could delete system files "
        exit 7
    fi
    if [ -d $HOME_DIR ]
    then
        rm -rf $HOME_DIR
    fi
}
remove_quota(){
    gluster volume quota $GLUSTER_VOL remove /users/$USERNAME 2>/dev/null
}

remove_tukey_user() {
    ssh -i $ACCTCREATION_SSHKEY  ubuntu@www.opensciencedatacloud.org "/var/www/tukey/tukey_middleware/tools/with_venv.sh python /var/www/tukey/tukey_middleware/tools/create_tukey_user.py -r $CLOUD $USERNAME" 2>/dev/null

}


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


