#!/usr/bin/python
#   Copyright [yyyy] [name of copyright owner]
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#


import os
import sys
import getopt
import ConfigParser
import re

import keystoneclient.v2_0.client as ksclient
import swiftclient

from sqlalchemy import create_engine, insert, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import Table, Column, Text, Float, MetaData, DateTime

from datetime import datetime, timedelta
from pytz import timezone
import pytz

import numpy


class RepCephOSdu:
    def __init__(self, config_file="/etc/osdc_cloud_accounting/settings.py", storage_type='object'):
        """Polls gluster for quotas and save into dict"""
        self.settings = {}

        #read in settings
        Config = ConfigParser.ConfigParser()
        Config.read(config_file)
        sections = ['general','repcephosdu']
        self.settings = {}
        for section in sections:
            options = Config.options(section)
            self.settings[section]={}
            for option in options:
                try:
                    self.settings[section][option] = Config.get(section, option)
                except:
                    sys.stderr.write("exception on [%s] %s!" % section, option)

        self.re_novarc=re.compile('OS_(\S+)=(\S+)')
    
        self.start_time = None
        self.end_time = None
        self.now_time = datetime.now(tz=pytz.timezone(self.settings['general']['timezone']))

        if storage_type == "object":
            self.table_name = self.settings['repcephosdu']['db_object_table']
        if storage_type == "block":
            self.table_name = self.settings['repcephosdu']['db_block_table']


    def get_novarc_creds(self, path=None,debug=None):
        """
            Parse a users novarc file, since I can not figure out how to spoof a user using the admin token
            Retruns the dictionary of key/values (keys in lowercase)
        """

        novarc_creds = {}

        f = open(path,'r')
        novarc = f.read()
        if debug:
            sys.stderr.write( "DEBUG: Read in %s:\n%s" %(path,novarc) )
        f.close()
        
        for key,value in self.re_novarc.findall( novarc ):
            novarc_creds[key.lower()] = value

        if debug:
            sys.stderr.write( "DEBUG: novarc_creds = %s" %(novarc_creds) )

        return novarc_creds


    def get_swift_du_for_tenant(self,username=None, password=None, auth_url=None, tenant_name=None, debug=None):
        """
            Takes the openstack credentials, gets a list of containers and their sizes, returns sum
        """

        keystone = ksclient.Client(username=username, password=password, auth_url=auth_url, tenant_name=tenant_name)
        auth_token=keystone.auth_token
        object_store_url=str(keystone.service_catalog.get_urls(service_type='object-store', endpoint_type='internal')[0])
        os_creds={}
        os_creds['user'] = username
        os_creds['key'] = password
        os_creds['tenant_name'] = tenant_name
        os_creds['authurl'] = auth_url
        os_creds['preauthtoken'] = keystone.auth_token
        os_creds['preauthurl'] = object_store_url

        if debug:
            sys.stderr.write( "DEBUG: os_creds = %s" %(os_creds) )

        swift_conn=swiftclient.client.Connection( **os_creds )

        account_reply = swift_conn.get_account()
        buckets = account_reply[-1]
        if debug:
            sys.stderr.write( "DEBUG: buckets  = %s" %(buckets) )

        total_bucket_du = 0

        for bucket in buckets:
            total_bucket_du += bucket['bytes']
            if debug:
                sys.stderr.write( "DEBUG: %s  = %s; total = %s" %(bucket['name'],bucket['bytes']) )
        
        return total_bucket_du

    def update_db(self, user_name, tenant_name, du, debug, ):
      
        metadata = MetaData()
        table = Table(self.table_name, metadata,
                Column('date', DateTime),   # Date of check
                Column('name', Text),       # Name of Tenant/User 
                Column('value', Float),     # Value in bytes ?
        )
 
        self.write_to_db(table=table, name=tenant_name, du=du, debug=debug )

    def db_connect(self, db):
        try:
            dsn = "mysql://%s:%s@%s/%s" % (self.settings['repcephosdu']['db_user'],
                self.settings['repcephosdu']['db_passwd'], self.settings['repcephosdu']['db_server'], db)
            engine = create_engine(dsn)
            return engine.connect()

        except SQLAlchemyError, e:
            print e

    def write_to_db(self,table=None, name=None, du=None, debug="debug" ):
        """Push it out to a file"""

        conn = self.db_connect(self.settings['repcephosdu']['db_database'])
        insert = []
        insert.append({'date': self.now_time.strftime(self.settings['general']['timeformat']),
                'name': name,
                'value': int(du)
            })
        conn.execute(table.insert(), insert)

    def get_percentile_du(self, start_date=None, end_date=None, name=None, percentile=95):
        """Get the 95th percentile of the du"""
        if start_date is  None or end_date is None:
            sys.stderr.write(
                "ERROR: Start and End Dates no specified in get_95thp_du")
            sys.exit(1)

        my_query = "SELECT value FROM %s where ( date >= '%s' and date <= '%s' ) and name = '%s'" % (
            self.table_name,
            start_date,
            end_date,
            name)

        try:
            dus=[]
            conn = self.db_connect(self.settings['repcephosdu']['db_database'])
            s = text(my_query)
            results = conn.execute(s).fetchall()
            if results:
                for x in results:
                    dus.append(x)
                result = numpy.percentile(a=dus,q=percentile)
                return result
            else:
                return 0

        except SQLAlchemyError:
            sys.stderr.write("Erroring querying the databases\n")
            sys.exit(1)


if __name__ == "__main__":

    #getopt args
    update = False # Update the database
    debug = False  # Debug statements
    novarc = None  # novarc file for the tenant

    try:
        opts, args = getopt.getopt(sys.argv[1:], "", ["debug", "update", "novarc=" ])
    except getopt.GetoptError:
        sys.stderr.write("ERROR: Getopt\n")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("--debug"):
            debug = True
        elif opt in ("--update"):
            update = True 
        elif opt in ("--novarc"):
            novarc = arg

    if len(sys.argv) <= 1:
        sys.stderr.write( "Usage: %s --novarc=/PATH/to/.novarc [--debug] [--update]\n"%(__file__) )
        sys.exit(0)

    if novarc:
        if os.path.isfile(novarc):
            x = RepCephOSdu(storage_type='object')
            novarc_creds = x.get_novarc_creds(novarc, debug=debug)
            swift_du = x.get_swift_du_for_tenant( debug=debug, **novarc_creds)
            print "%s = %s" % (swift_du, novarc_creds)
            if update:
                x.update_db(user_name=novarc_creds['username'], tenant_name=novarc_creds['tenant_name'],  du=swift_du, debug=debug )

            print x.get_percentile_du(start_date='2014-09-15 00:00:00', end_date='2014-09-15 23:59:59', name='admin')
            
