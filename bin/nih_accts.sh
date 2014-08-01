#!/bin/bash
XFER_PROG="sftp"
XFER_OPTS="-oLogLevel=ERROR"
DEST_SERVER="wgaftp.ncbi.nlm.nih.gov"
DEST_USER="TP"
DEST_FILE_LIST="authentication_file_phs000235.txt authentication_file_phs000218.txt authentication_file_phs000178.txt"
TARGET_DIR="/root/csv"

dest_passwrod=$(cat /etc/osdc_cloud_accounting/nihcred.txt)
date=$(date +%F-%H%M%S)

compiled_output_file="${TARGET_DIR}/compiled/user_list_${date}"

download_file() {
    for file in $DEST_FILE_LIST
    do
        temp_output_file="${TARGET_DIR}/raw/${file}-${date}"
        sshpass -p${dest_passwrod}  ${XFER_PROG} ${XFER_OPTS} ${DEST_USER}@${DEST_SERVER}:${file} ${temp_output_file}
        cat $temp_output_file >> $compiled_output_file
    done
}
create_users(){
    if [[ $(wc -l $compiled_output_file | cut -f1 -d " " ) > 0 ]]
    then
	source /usr/local/src/.SFACCT/bin/activate
	/usr/local/src/osdc_cloud_accounting/bin/sf_acct_create.py --nihfile $compiled_output_file 
    fi
}
download_file
create_users
