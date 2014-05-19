#!/bin/bash
set -e
set -u

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

while getopts "t:v:g:s:" opt; do
  case "$opt" in
    t)
	tennant_id=$(/usr/bin/keystone tenant-list 2>/dev/null | grep $OPTARG | perl -ne 'm/\|\s(\S+)\s/ && print "$1"')

	if [ "$tennant_id" == "" ]
	then
    		echo "$0 Error: No user/tennant found for $USERNAME"
    		exit 1
	fi
	;;
    v)
        cinder quota-update --volumes $OPTARG $tennant_id
      ;;
    g)
        cinder quota-update --gigabytes $OPTARG $tennant_id
      ;;
    s)
        cinder quota-update --snapshots $OPTARG $tennant_id
      ;;
    *)
	echo "${opt}"
      echo ">> Usage: $0 -t TENANT [-v NUM_VOLUMES] [-g SIZE_IN_GB] [-s NUM_SNAPSHOTS]"
      exit 1
      ;;
    :)
      echo "Option -$OPTARG requires an argument." >&2
      exit 1
      ;;
	
  esac
done

if [ "$tennant_id" != "" ]
then 
	cinder quota-show $tennant_id
	exit 0
fi
if [ $OPTIND -lt 3 ]
then
      echo ">>>Usage: $0 -t TENANT [-v NUM_VOLUMES] [-g SIZE_IN_GB] [-s NUM_SNAPSHOTS]"
      exit 1
fi
