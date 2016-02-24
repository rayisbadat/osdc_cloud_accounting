#!/bin/bash

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


CREDS_FILE="s3cred.txt"


tenant=${1}
username=${2}

set -e
set -u

db_name=${s3creds_db_name}
db_server=${s3creds_db_server}
db_table=${s3creds_db_table}
db_user=${s3creds_db_user}
db_passwd=${s3creds_db_passwd}


if [ -z "$username" ] || [ -z "$tenant" ]
then
	echo "Usage: $0 tenant useranme"
	exit 1
fi
touch_initial_file() {
    #Cant set quota till after first upload
    user_home=$(getent passwd $username | cut -d":" -f6)
    #There is some kind of ldap lag i need to work around, until then breaking generallness
    #user_home=/home/${username}
    #Need to ensure the user exists due to how keystone+ceph inegration works.
    (cd $user_home; source .novarc; cd /tmp; echo "42" > .sfquotaset; swift upload ${username}-sfquotaset .sfquotaset  &> /dev/null ; swift delete ${username}-sfquotaset &> /dev/null; rm .sfquotaset &>/dev/null)
}


find_tenant_uuid() {
    tenant_uuid=$(keystone tenant-get $tenant 2>/dev/null | perl -n -e'm/\|\s+id\s+\|\s+(\S+)\s+\|/ && print "$1"')
}

    
create_s3_creds() {
    json=$(radosgw-admin key create --uid=${tenant_uuid} --key-type=s3 --gen-access-key)
    ceph_user_id=$(echo $json | perl -00n -e 'undef $/; ' -e 'm|\"user_id\": "([^"]+)",|ms && print "$1\n";')
    access_key=$(echo $json | perl -00n -e 'undef $/; ' -e 'm|\"access_key\": "([^"]+)",\s+\"secret_key\": "([^"]+)"\s*}\s*],|ms && print "$1\n";')
    secret_key=$(echo $json | perl -00n -e 'undef $/; ' -e 'm|\"access_key\": "([^"]+)",\s+\"secret_key\": "([^"]+)"\s*}\s*],|ms && print "$2\n";')
}

write_out_creds() {
    sudo su - $username  -c "echo -e [[${tenant}]]\\\naccess_key=${access_key}\\\nsecret_key=${secret_key}\\\n >> ${CREDS_FILE}" 
}

push_to_db() {

    secret_key_hashed=$( python -c "import bcrypt;print bcrypt.hashpw('$secret_key', bcrypt.gensalt())" )

    mysql -h$db_server -u$db_user -p$db_passwd $db_name << EOF
    INSERT INTO ${db_table} 
    (created_at,updated_at,deleted_at,username,tenant_name,tenant_uuid,ceph_user_id,access_key,secret_key_hash,deleted) 
    VALUES 
    (NOW(),NOW(),NOW(),"$username","$tenant","$tenant_uuid","$ceph_user_id","$access_key","$secret_key_hashed",'0')
EOF
    

}

compare_hashes() {
    python -c "import bcrypt;password=\"${secret_key}\";hashed=\"$secret_key_hashed\"; print( bcrypt.hashpw(password, hashed) == hashed )"
}

service nscd restart &>/dev/null || /bin/true
sleep 5s

#touch_initial_file
find_tenant_uuid
create_s3_creds
write_out_creds
push_to_db
