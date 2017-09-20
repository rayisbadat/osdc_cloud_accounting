#!/bin/bash

#
#
#
#

set -e
set -u


#Pull in the ldap info
if [ -e /etc/osdc_cloud_accounting/settings.sh ]
then
    source  /etc/osdc_cloud_accounting/settings.sh
else
    echo "$0 Error: can not locate /etc/osdc_cloud_accounting/settings.sh "
    exit 1
fi


generate_qr_code() {
    uuid=$(uuidgen)
    qrcode_out=/var/www/qrcode/${uuid}.svg
    string=$( python -c "import pyotp; print( pyotp.totp.TOTP('$totp_secret').provisioning_uri('$username', issuer_name='$issuer_name') )" )
    $( python -c "import pyqrcode; pyqrcode.create('$string').svg('${qrcode_out}', scale=8)" )
    totp_url="$TOTP_URL/$uuid.svg"
}

create_google_auth_file() {

    echo "${totp_secret}
\" RATE_LIMIT 3 30
\" WINDOW_SIZE 17
\" DISALLOW_REUSE
\" TOTP_AUTH
" > /home/${username}/.google_authenticator

    chown ${username}:${username} /home/${username}/.google_authenticator
    chmod 0400 /home/${username}/.google_authenticator



}

print_info() {

    #Echo to screen
    echo "Username: ${username} Secret: ${totp_url}"

}


username=${1}
totp_secret=$( python -c 'import pyotp; print( pyotp.random_base32() );' )
issuer_name=$(hostname)

generate_qr_code
create_google_auth_file
print_info
