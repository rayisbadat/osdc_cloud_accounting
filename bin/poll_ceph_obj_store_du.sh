#!/bin/bash
source  /etc/osdc_cloud_accounting/admin_auth
source  /etc/osdc_cloud_accounting/settings.sh
source /usr/local/src/.SFACCT/bin/activate
cd /usr/local/src/osdc_cloud_accounting/repcephosdu


for username in $(keystone user-list | tr -s " "| cut -f3 -d"|"  | grep -Ev " admin | neutron | nova | cinder |glance | ceilometer |\+| name")
do
    novarc=$(getent passwd ${username} | cut -f6 -d":")/.novarc
    ./repcephosdu.py --novarc=${novarc}  --update
done
