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
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError

def tenant_exist(tenant):
    """ Check if tenant exists """
    try:
        subprocess.check_call( ['/usr/local/sbin/does_tenant_exist.sh', tenant ], stdout=open(os.devnull, 'wb') )
        return True
    except subprocess.CalledProcessError, e:
        return False


def create_tenant(tenant, debug=None, run=None):
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


def create_user(username, fields, debug=None,run=None):
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
        if debug:
            pprint.pprint(cmd)
            pprint.pprint(fields)
        if run:
            print(str(cmd))
            result = subprocess.check_call( cmd )
            return True
        else:
            return True
    except subprocess.CalledProcessError, e:
        sys.stderr.write("Error: creating new user %s\n" % username )
        sys.stderr.write("%s\n" % e.output)
        return False


def set_quota(username, tenant, quota_type, quota_value, debug=None,run=None):
    """ Set the quota we assume everything is in base 2 units.
        This should all be handled by salesforceocc long before it gets here"""
   
    if quota_type == 'cinder':
        # update_cinder_quotas takes quota_value in gigabytes
        cmd = ["/usr/local/sbin/update_cinder_quotas.sh",
                "-t %s" % tenant,
                "-g %s" % quota_value,
                "-v %s" % (10 + quota_value/2),
                "-s %s" % (10 + quota_value/2),
            ]
    elif quota_type == 'ceph_swift':
        # Command takes units in bytes
        cmd = ["/usr/local/sbin/update_ceph_quotas.sh",
                "%s" % username,
                "%s" % tenant,
                "%s" % quota_value,
            ]

    #I did a bad thin in this shell script, we used to map tenant=username.
    #So the script asks for username and not tenant
    elif quota_type == 'core':
        cmd = [ '/usr/local/sbin/update_nova_core_quotas.sh',
                '%s' % tenant,
                '%s' % quota_value,
            ]
    else:
        return False 

    #Set quota
    try:
        if debug:
            pprint.pprint(cmd)
        if run:
            result = subprocess.check_call( cmd )
            return True
    except subprocess.CalledProcessError, e:
        sys.stderr.write("ERROR: Could not set %s quota for %s = %s\n" % (quota_type, tenant, quota_value) )
        sys.stderr.write("%s\n" % e.output)
        return False


def toggle_user_locks(approved_members=None, starting_uid=1500, debug=None):
    for p in pwd.getpwall():
        if debug:
            print "DEBUG: User on System %s:%s"%(p.pw_name,p.pw_uid)

        if p.pw_name in approved_members:
            operation="unlock"
        elif p.pw_uid < starting_uid:
            if debug:
                print "DEBUG: Skipping reserved user %s:%s<%s"%(p.pw_name,p.pw_uid,starting_uid)
            continue
        elif p.pw_name=="nobody":
            continue
        else:
            operation="lock"
            print "Disable user %s:%s"%(p.pw_name,p.pw_uid)

        cmd = [
            '/usr/local/sbin/userlock.sh',
             p.pw_name,
             operation,
        ]
        try:
            if debug:
                pprint.pprint(cmd)
            if run:
                result = subprocess.check_call( cmd )
        except subprocess.CalledProcessError, e:
            sys.stderr.write("Error: %s user %s\n" % (operation,username))
            sys.stderr.write("%s\n" % e.output)


def get_tenant_members(tenant=None):
    """ Return list of users in a tenant, the client API wants the user we run as to be a member of every tenant we query :( """
    query = """select c.name as User_Name
        from keystone.project a
            join keystone.assignment b
                on b.target_id = a.id
            join keystone.user c
                on b.actor_id = c.id
        where a.name='%s';
        """ % tenant

    members = set()

    try:
        conn = db_connect(settings['accounts']['novadb'])
        s = text(query)
        results = conn.execute(s)
    except SQLAlchemyError as e:
        sys.stderr.write("ERROR-NUR: Erroring querying the databases: %s\n" % (e) )
        sys.exit(1)


    for row in results:
        try:
            members.add(row[0])
        except KeyError:
            pass
        except ValueError:
            pass

    return members
    
def db_connect(db):
    try:
        dsn = "mysql://%s:%s@%s/%s" % (settings['accounts']['db_user'],
            settings['accounts']['db_passwd'], settings['accounts']['db_server'], db)
        engine = create_engine(dsn)
        return engine.connect()

    except SQLAlchemyError, e:
        sys.stderr.write("Error %s" % (e))
        sys.exit(1)


        
def remove_member_from_tenant(tenant=None, users=None, role="_member_"):
    """  Remove users from the tenant """
    for user in users:
        print "INFO: Removing user %s from tenant %s" % (user, tenant)
        cmd = [
            'keystone',
            'user-role-remove',
            "--user=%s"%(user),
            "--tenant=%s"%(tenant),
            "--role=%s"%(role),
        ]
        try:
            result = subprocess.check_call( cmd )
        except subprocess.CalledProcessError, e:
            sys.stderr.write("Error: Removing  user %s to tenant %s\n" % (username,tenant) )
            sys.stderr.write("%s\n" % e.output)
    

def add_member_to_tenant(tenant=None, users=None, role="_member_", debug=None):
    """ Add users to the tenant """  
    for user in users:
        print "INFO: Adding user %s to tenant %s" % (user, tenant)
        cmd = [
            'keystone',
            'user-role-add',
            "--user=%s"%(user),
            "--tenant=%s"%(tenant),
            "--role=%s"%(role),
        ]
        if debug:
            pprint.pprint( cmd )
        try:
            result = subprocess.check_call( cmd )
        except subprocess.CalledProcessError, e:
            sys.stderr.write("Error: Adding  user %s to tenant %s\n" % (user,tenant) )
            sys.stderr.write("%s\n" % e.output)
        


if __name__ == "__main__":

    #Load in the CLI flags
    run = True
    debug = False
    nih_file = False
    tukey = True
    approved_members = set()
    set_ceph_quota = True

    try:
        opts, args = getopt.getopt(sys.argv[1:], "", ["debug", "norun", "nihfile=", "nocephquota"])
    except getopt.GetoptError:
        sys.stderr.write("ERROR: Getopt\n")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("--debug"):
            debug = True
        elif opt in ("--norun"):
            run = False
        elif opt in ("--nihfile"):
            nih_file = arg
            nih_approved_users = {}
        elif opt in ("--notukey"):
            tukey = False
        elif opt in ("--nocephquota"):
            set_ceph_quota = False
	

    sfocc = SalesForceOCC()
    #read in settings
    Config = ConfigParser.ConfigParser()
    Config.read("/etc/osdc_cloud_accounting/settings.py")
    sections = ['general','salesforceocc','tukey', 'accounts']
    settings = {}
    for section in sections:
        options = Config.options(section)
        settings[section]={}
        for option in options:
            try:
                settings[section][option] = Config.get(section, option)
            except:
                sys.stderr.write("exception on [%s] %s!" % section, option)

    #One offs:
    try:
        settings['accounts']['managed_tenants']=settings['accounts']['managed_tenants'].split(',')
        managed_tenants={}
        # Loop through managed tenants in config and initialize
        #Setting to set() since we need to do intersections and differences
        for managed_tenant in settings['accounts']['managed_tenants']:
            managed_tenants[managed_tenant]=set()
            if debug:
                print "DEBUG: created managed tenant: %s" % (managed_tenant)
                pprint.pprint( managed_tenants )
    except:
        pass

    #Load up a list of the users in SF that are approved for this cloud
    sfocc.login(username=settings['salesforceocc']['sfusername'], password=settings['salesforceocc']['sfpassword'])
    contacts = sfocc.get_contacts_from_campaign(campaign_name=settings['salesforceocc']['campaign'],  statuses=["Approved User", "Application Pending"])
    members_list = sfocc.get_approved_users(campaign_name=settings['salesforceocc']['campaign'], contacts=contacts)

    if debug:
        print "DEBUG: contacts from SF"
        pprint.pprint( contacts ) 
        print "DEBUG: members from SF"
        pprint.pprint( members_list )

    #Load up a nih style csv of approved users.
    #user_name is the actual human name
    #login is the name we care about.
    #phsid is also important eventually
    if nih_file:
        
        if debug:
            print "DEBUG: maned_tenants:" 
            pprint.pprint(settings['accounts']['managed_tenants'])

        try:
            with open(nih_file, 'r') as handle:
                reader = csv.DictReader(handle, ['user_name', 'login', 'authority', 'role', 'email', 'phone',' status', 'phsid', 'permission_set', 'created', 'updated', 'expires', 'downloader_for'])
                # Loop through csv and load the user info
                # we are loading the phsids as an array
                for row in reader:
                    try:
                        if type(nih_approved_users[row['login'].upper()]) is not list:
                            nih_approved_users[row['login'].upper()]=[]
                    except KeyError:
                        nih_approved_users[row['login'].upper()]=[]
                    #add in phsid to array
                    nih_approved_users[row['login'].upper()].append(row['phsid'])

                    #Create a list of who belongs to what managed tenant for later parsing
                    if row['phsid'].split(".")[0] in settings['accounts']['managed_tenants']:
                        managed_tenants[row['phsid'].split(".")[0]].add(row['login'].upper())

                        
        except IOError as e:
            sys.exit('file %s not found: %s' % (nih_file, e))
        except csv.Error as e:
            sys.exit('file %s, line %d: %s' % (filename, reader.line_num, e))
    

    #Loop through list of members and run the bash scripts that will create the account
    #FIXME: Most of this stuff could be moved into the python, just simpler not to
    print "Creating New Users:"
    for username, fields in members_list.items():
        #Nih style changes....i am doing this wrong
        if nih_file:
            if fields['eRA_Commons_username'].upper()  in nih_approved_users:
                fields['username'] = fields['eRA_Commons_username'].upper()
                username = fields['eRA_Commons_username'].upper()
                fields['login_identifier']="urn:mace:incommon:nih.gov!https://bionimbus-pdc.opensciencedatacloud.org/shibboleth!%s"%(username)
            else:
                continue

        if debug:
            print "DEBUG: Username from SF = %s" % (username) 

        #At some point we need to disable inactive users
        approved_members.add(username)
        
        try:
            user_exists = pwd.getpwnam(username)
        except:
            user_exists = None

        if not user_exists:
            if fields['tenant']:
                if not tenant_exist(fields['tenant']):
                    if fields['quota_leader']:
                        #Will create the new tenant
                        print "INFO: Creating new tenant %s" % (fields['tenant'])
                        if create_tenant(tenant=fields['tenant'], debug=debug,run=run):
                            add_member_to_tenant(role='quota_leader', tenant=fields['tenant'],users=[username] )
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
                user_created = create_user(username=username,fields=fields, debug=debug, run=run)

    #Apply Quotas
    print "Setting Quotas"
    for username, fields in members_list.items():
        #Nih style changes....i am doing this wrong
        if nih_file:
            if fields['eRA_Commons_username'].upper()  in nih_approved_users:
                fields['username'] = fields['eRA_Commons_username'].upper()
                username = fields['eRA_Commons_username'].upper()
                fields['login_identifier']="urn:mace:incommon:nih.gov!https://bionimbus-pdc.opensciencedatacloud.org/shibboleth!%s"%(username)
            else:
                continue

        if debug:
            print "DEBUG: Username from SF = %s" % (username) 

        try:
            user_exists = pwd.getpwnam(username)
        except:
            user_exists = None

        #Set storage quota if leader
        if user_exists and fields['quota_leader']:
            if fields['object_storage_quota'] and set_ceph_quota:
                set_quota(username=username, tenant=fields['tenant'], quota_type="ceph_swift", quota_value=fields['object_storage_quota'], debug=debug,run=run)
            if fields['block_storage_quota']:
                #takes quota in GibaBytes
                set_quota(username=username, tenant=fields['tenant'], quota_type="cinder", quota_value=fields['block_storage_quota'], debug=debug,run=run)
            if fields['core_quota']:
                set_quota(username=username, tenant=fields['tenant'], quota_type="core", quota_value=fields['core_quota'], debug=debug,run=run)
   
    #Lock users
    print "Locking/Unlocking Users:"
    try:
        starting_uid=int(settings['general']['starting_uid'])
    except KeyError:
        starting_uid=1500
    toggle_user_locks(approved_members=approved_members,starting_uid=starting_uid,debug=debug,) 

    #Fix the tenants for manged groups
    #csv_tenant_members = 
    #approved_tenant_members
    #current_tenant_members =  currently on system as memebrs
    #valid_tenant_memebers = they are the ones we are keeping in the tennat
    #invalid_tenant_members = users we need to remove from a tenant
    #additional_tenant_members = users we need to add
    print "Adjusting tenant membership:" 
    for tenant_name, csv_tenant_members in managed_tenants.items():
        #Intersection of CSV and SalesForce
        approved_tenant_members = csv_tenant_members.intersection( approved_members )
        #Current users in tenant
        current_tenant_members = get_tenant_members(tenant=tenant_name)
        #Keep these user in tenant, they are still valid
        valid_tenant_members = current_tenant_members.intersection(approved_tenant_members)
        #We need to remove these users from the tenant
        invalid_tenant_members = current_tenant_members.difference(valid_tenant_members)
        #We need to add these users to the tenant
        additional_tenant_members = approved_tenant_members.difference( valid_tenant_members ) 

        if debug:
            print tenant_name
            pprint.pprint( approved_tenant_members ) 
            pprint.pprint( valid_tenant_members ) 
            pprint.pprint( invalid_tenant_members ) 
            pprint.pprint( additional_tenant_members ) 
       
        remove_member_from_tenant(tenant=tenant_name, users=invalid_tenant_members)
        add_member_to_tenant(tenant=tenant_name, users=additional_tenant_members)
        
        
        
        
        

