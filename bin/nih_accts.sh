#!/bin/bash
XFER_PROG="sftp"
XFER_OPTS="-oLogLevel=ERROR"
DEST_SERVER="wgaftp.ncbi.nlm.nih.gov"
DEST_USER="TP"
DEST_FILE_LIST="authentication_file_phs000235.txt.enc authentication_file_phs000218.txt.enc authentication_file_phs000178.txt.enc"
TARGET_DIR="/root/csv"

dest_passwrod=$(cat /etc/osdc_cloud_accounting/nihcred.txt)
date=$(date +%F-%H%M%S)
decrypt_key=$(cat /etc/osdc_cloud_accounting/nihdecrypt.txt)

compiled_output_file="${TARGET_DIR}/compiled/user_list_${date}"

download_file() {
    for file in $DEST_FILE_LIST
    do
        temp_output_file="${TARGET_DIR}/raw/${file}-${date}"
        sshpass -p${dest_passwrod}  ${XFER_PROG} ${XFER_OPTS} ${DEST_USER}@${DEST_SERVER}:${file} ${temp_output_file}
        #The use of the insecure unix crypt is not my choice, ccyrpt should flush env key after use
        export key=${decrypt_key}
        ccrypt -E key  --unixcrypt   $temp_output_file >> $compiled_output_file
    done
}
create_users(){
    if [[ $(wc -l $compiled_output_file | cut -f1 -d " " ) > 0 ]]
    then
	source /usr/local/src/.SFACCT/bin/activate
    source /etc/osdc_cloud_accounting/admin_auth
	/usr/local/src/osdc_cloud_accounting/bin/sf_acct_create.py --nihfile $compiled_output_file  --debug
    fi
}
download_file
create_users
