#!/bin/bash

cinder_allocated=$(cinder list --all_tenants | tr -s " " | cut -d"|" -f5 | grep -v "+" | perl -lan -e '$core = $1 if m|(\d+)|;' -e '$sum+=$core;' -e'print "+$core=\n$sum";'| tail -n1)
actually_used=$(ceph df | perl -ne 'm|volumes\s+\d+\s+(\S+)| && print "$1\n"')

echo "Currently ${cinder_allocated}GB of Cinder Blocks are provisioned with $actually_used of data written to them"
