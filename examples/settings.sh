export BASEDN=""
export ADMINCN="cn=admin,$BASEDN"
export LDAP_SECRET="/etc/pam_ldap.secret"

export ADC_SID=""

export GLUSTER_VOL="USER-HOME"
export DISK_QUOTA="1TB"

export ACCTCREATION_SSHKEY='~/id_rsa'


export s3creds_db_name="storage"
export s3creds_db_table="$CLOUDNAME_s3_keys"
export s3creds_db_server="mysql-$CLOUDNAME.fqdn.tld"
export s3creds_db_user="reporting"
export s3creds_db_passwd="hunter2"
