#!/bin/bash

if [ -z "$1" ]
then
    echo "USAGE: $0 tenant_name"
    exit 1
fi

set -e
set -u

tenant_name=$1

uuid=$( keystone tenant-get $tenant_name 2>/dev/null| perl -n -e 'm/id\s+\|\s+(\S+)/ && print "$1\n"' )
radosgw-admin user stats --uid=$uuid



