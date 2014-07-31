#!/usr/bin/env python
from salesforceocc import SalesForceOCC
import ConfigParser
import pwd
import sys
import subprocess
import getopt
import pprint
import csv
import  os

def tenant_exist(tenant):
    """ Check if tenant exists """
    try:
        subprocess.check_call( ['/usr/local/sbin/does_tenant_exist.sh', tenant ], stdout=open(os.devnull, 'wb') )
        return True
    except subprocess.CalledProcessError, e:
        return False


def create_tenant(tenant, printdebug=None, run=None):
    """ call the bash scripts to create tenants """
    if run:
        try:
            subprocess.check_call( ['/usr/bin/keystone','tenant-create', '--name=%s'%(tenant)], stdout=open(os.devnull, 'wb') )
            return True
        except subprocess.CalledProcessError, e:
            sys.stderr.write("Error creating  new tenant:  %s\n" % username )
            sys.stderr.write("%s\n" % e.output)
            return False
    else:
        return True


def create_user(username, fields, printdebug=None,run=None):
    """ Call create user script """
    if fields['Authentication_Method'] == 'OpenID':
        method = 'openid'
    else:
        method = 'shibboleth'
    
    #If we have an identifier use that, otherwise fallback to email
    #if fields['login_identifier'] == '' or fields['login_identifier'] == None ora not fields['login_identifier']:
    if not fields['login_identifier']:
        login_identifier = fields['Email']
    else:
        login_identifier = fields['login_identifier']

    #Create user
    print "INFO: Creating new user: %s" % username
    cmd = [
        '/usr/local/sbin/create-user.sh',
        fields['Name'],
        fields['username'],
        fields['tenant'],
        login_identifier,
        method,
        settings['tukey']['cloud'],
    ]
    try:
        if printdebug:
            pprint.pprint(cmd)
            pprint.pprint(fields)
        if run:
            result = subprocess.check_call( cmd )
            return True
        else:
            return True
    except subprocess.CalledProcessError, e:
        sys.stderr.write("Error: creating new user %s\n" % username )
        sys.stderr.write("%s\n" % e.output)
        return False


def set_quota(username, tenant, quota_type, quota_value, printdebug=None,run=None):
    """ Set the quota """
   
    if quota_type == 'cinder':
        cmd = ["/usr/local/sbin/update_cinder_quotas.sh",
                "-t %s" % tenant,
                "-g %s" % quota_value,
                "-v %s" % (10 + quota_value/2),
                "-s %s" % (10 + quota_value/2),
            ]
    elif quota_type == 'ceph_swift':
        cmd = ["/usr/local/sbin/update_ceph_quotas.sh",
                "%s" % username,
                "%s" % tenant,
                "%s" % quota_value,
            ]
    else:
        return False 

    #Set quota
    try:
        if printdebug:
            pprint.pprint(cmd)
        if run:
            result = subprocess.check_call( cmd )
            return True
    except subprocess.CalledProcessError, e:
        sys.stderr.write("ERROR: Could not set %s quota for %s = %s\n" % (quota_type, tenant, quota_value) )
        sys.stderr.write("%s\n" % e.output)
        return False

        

if __name__ == "__main__":

    #Load in the CLI flags
    run = True
    printdebug = False
    nih_file = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], "", ["debug", "norun", "nihfile="])
    except getopt.GetoptError:
        sys.stderr.write("ERROR: Getopt\n")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("--debug"):
            printdebug = True
        elif opt in ("--norun"):
            run = False
        elif opt in ("--nihfile"):
            nih_file = arg
            nih_approved_users = {}

    sfocc = SalesForceOCC()
    #read in settings
    Config = ConfigParser.ConfigParser()
    Config.read("/etc/osdc_cloud_accounting/settings.py")
    sections = ['general','salesforceocc','tukey']
    settings = {}
    for section in sections:
        options = Config.options(section)
        settings[section]={}
        for option in options:
            try:
                settings[section][option] = Config.get(section, option)
            except:
                sys.stderr.write("exception on [%s] %s!" % section, option)

    #Load up a list of the users in SF that are approved for this cloud
    sfocc.login(username=settings['salesforceocc']['sfusername'], password=settings['salesforceocc']['sfpassword'])
    contacts = sfocc.get_contacts_from_campaign(campaign_name=settings['general']['cloud'],  statuses=["Approved User", "Application Pending"])
    members_list = sfocc.get_approved_users(campaign_name=settings['general']['cloud'], contacts=contacts)

    if printdebug:
        print "DEBUG: contacts from SF"
        pprint.pprint( contacts ) 
        print "DEBUG: members from SF"
        pprint.pprint( members_list )

    #Load up a nih style csv of approved users.
    #user_name is the actual human name
    #login is the name we care about.
    #phsid is also important eventually
    if nih_file:
        try:
            with open(nih_file, 'r') as handle:
                reader = csv.DictReader(handle, ['user_name', 'login', 'authority', 'role', 'email', 'phone',' status', 'phsid', 'permission_set', 'created', 'updated', 'expires', 'downloader_for'])
                for row in reader:
                    nih_approved_users[row['login'].upper()] = row['phsid']
                    if printdebug:
                        pprint.pprint( nih_approved_users[row['login'].upper()]  )
        except NameError:
            pass
        except IOError as e:
            sys.exit('file %s not found: %s' % (nih_file, e))
        except csv.Error as e:
            sys.exit('file %s, line %d: %s' % (filename, reader.line_num, e))
    

    #Loop through list of members and run the bash scripts that will create the account
    #FIXME: Most of this stuff could be moved into the python, just simpler not to
    for username, fields in members_list.items():
        #Nih style changes....i am doing this wrong
        if nih_file:
            if fields['eRA_Commons_username'].upper()  in nih_approved_users:
                fields['username'] = fields['eRA_Commons_username'].upper()
                username = fields['eRA_Commons_username'].upper()
                fields['login_identifier']="urn:mace:incommon:nih.gov!https://bionimbus-pdc.opensciencedatacloud.org/shibboleth!%s"%(username)
            else:
                continue

        if printdebug:
            print "DEBUG: Username from SF = %s" % (username) 
            
        try:
            user_exists = pwd.getpwnam(username)
        except:
            if fields['tenant']:
                if not tenant_exist(fields['tenant']):
                    if fields['quota_leader']:
                        #Will create the new tenant
                        print "INFO: Creating new tenant %s" % (fields['tenant'])
                        if create_tenant(tenant=fields['tenant'], printdebug=printdebug,run=run):
                            pass
                        else:
                            sys.stderr.write("ERROR: Creating new tenant %s skipping user creation.\n" % fields['tenant'] )
                    else:
                        #Can not create a user with out an existing tenant
                        sys.stderr.write("ERROR: New User %s has no existing tenant %s \n" % (username, fields['tenant']) )
                        continue

            #Create the user
            if username:
                print "INFO: Creating users %s" % username
                user_created = create_user(username=username,fields=fields, printdebug=printdebug, run=run)

            #Set quota if leader
            if user_created and fields['quota_leader']:
                print "INFO: Setting Quotas"
                if fields['object_storage_quota']:
                    set_quota(username=username, tenant=fields['tenant'], quota_type="ceph_swift", quota_value=fields['object_storage_quota'], printdebug=printdebug,run=run)
                if fields['block_storage_quota']:
                    set_quota(username=username, tenant=fields['tenant'], quota_type="cinder", quota_value=fields['object_storage_quota'], printdebug=printdebug,run=run)
                
