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
import keystoneclient.v2_0.client as ksclient
import swiftclient
import ConfigParser
from datetime import datetime, timedelta
from pytz import timezone
import pytz
import re


class RepSwiftDu:
    def __init__(self, config_file="/etc/osdc_cloud_accounting/settings.py"):
        """Polls gluster for quotas and save into dict"""
        self.settings = {}

        #read in settings
        Config = ConfigParser.ConfigParser()
        Config.read(config_file)
        sections = ['general','repswiftquota']
        for section in sections:
            options = Config.options(section)
            for option in options:
                try:
                    self.settings[option] = Config.get(section, option)
                except:
                    sys.stderr.write("ERROR: exception on [%s] %s!" % (section, option))
        self.now_time = datetime.now(tz=pytz.timezone('UTC'))
        self.re_novarc=re.compile('OS_(\S+)=(\S+)')

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
        keystone = ksclient.Client(username=username, password=password, auth_url=auth_url, tenant_name=tenant_name)
        auth_token=keystone.auth_token
        object_store_url=str(keystone.service_catalog.get_urls(service_type='object-store', endpoint_type='internal')[0])
        swift_creds={}
        swift_creds['user'] = username
        swift_creds['key'] = password
        swift_creds['tenant_name'] = tenant_name
        swift_creds['authurl'] = auth_url
        swift_creds['preauthtoken'] = keystone.auth_token
        swift_creds['preauthurl'] = object_store_url

        if debug:
            sys.stderr.write( "DEBUG: swift_creds = %s" %(swift_creds) )

        swift_conn=swiftclient.client.Connection( **swift_creds )

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

if __name__ == "__main__":

    #Load in the CLI flags
    x = RepSwiftDu()
    novarc_creds = x.get_novarc_creds('/etc/osdc_cloud_accounting/admin_auth')
    x.get_swift_du_for_tenant( **novarc_creds)
    print x.get_swift_du_for_tenant( **novarc_creds)
