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

cmd_ran=0

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
        cinder quota-update --volumes $OPTARG $tennant_id &> /dev/null
        cmd_ran=1
      ;;
    g)
        gigabytes=$(python -c "import math; print int(math.ceil($OPTARG*(2**30)/(1000**3)))")
        cinder quota-update --gigabytes $gigabytes $tennant_id &> /dev/null
        cmd_ran=1
      ;;
    s)
        cinder quota-update --snapshots $OPTARG $tennant_id &> /dev/null
        cmd_ran=1
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
if [ $OPTIND -eq 1 ]; 
then 
    echo "No options were passed"; 
    echo ">> Usage: $0 -t TENANT [-v NUM_VOLUMES] [-g SIZE_IN_GiB] [-s NUM_SNAPSHOTS]"
    exit 1
fi


if [[ "$tennant_id" != "" ]] && [[ $cmd_ran -eq 0 ]]
then 
	cinder quota-show $tennant_id
	exit 0
fi
if [ $OPTIND -lt 3 ]
then
      echo ">>>Usage: $0 -t TENANT [-v NUM_VOLUMES] [-g SIZE_IN_GiB] [-s NUM_SNAPSHOTS]"
      exit 1
fi
