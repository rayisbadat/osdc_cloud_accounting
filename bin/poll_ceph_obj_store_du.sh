#!/bin/bash
source  /etc/osdc_cloud_accounting/admin_auth
source  /etc/osdc_cloud_accounting/settings.sh
source /usr/local/src/.SFACCT/bin/activate
cd /usr/local/src/osdc_cloud_accounting/repcephosdu


for username in $(keystone user-list 2>/dev/null | tr -s " "| cut -f3 -d"|"  | grep -Ev " admin | neutron | nova | cinder |glance | ceilometer |\+| name")
do
    novarc=$(getent passwd ${username} | cut -f6 -d":")/.novarc
    if [ -e /etc/osdc_cloud_accounting/project_overrides ]
    then
        ./repcephosdu.py --novarc=${novarc}  --update --project_override_file /etc/osdc_cloud_accounting/project_overrides;
    else
        ./repcephosdu.py --novarc=${novarc}  --update
    fi


done
