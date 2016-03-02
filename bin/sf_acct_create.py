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


def create_ceph_s3_creds(tenant, username, ceph_auth_type=None,  debug=None, run=None):
    """ Create the s3creds for a the tenant, generally only called for quota leader
        user_type: [keystone]|ceph .If object store uses keystone or ceph method for user creation.  
        Keystone doesnt create user till first objectis written and so we do silly stuff.
    """

    if ceph_auth_type == "ceph_ceph":
        cmd = [ '/usr/local/sbin/create_ceph_s3_creds-native.py', tenant , username ]

    elif ceph_auth_type == "ceph_keystone":
        cmd = [ '/usr/local/sbin/create_ceph_s3_creds.sh', tenant , username ]
    else:
        return False

    #Set quota
    if debug:
        print "INFO: %s cmd:" % (__name__) 
        pprint.pprint(cmd)

    if run:
        try:
            subprocess.check_call(cmd, stdout=open(os.devnull, 'wb'))
            return True

        except subprocess.CalledProcessError, e:
            sys.stderr.write("Error creating  new rados key for tenant:  %s\n" % tenant )
            sys.stderr.write("%s\n" % e.output)
            return False

        else:
            return True


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
            subprocess.check_call( ['/usr/bin/keystone','tenant-create', '--name=%s'%(tenant)], stdout=open(os.devnull, 'wb'),stderr=open(os.devnull, 'wb') )
            return True
        except subprocess.CalledProcessError, e:
            sys.stderr.write("Error creating  new tenant:  %s\n" % username )
            sys.stderr.write("%s\n" % e.output)
            return False
    else:
        return True

def create_user(username,cloud,fields, debug=None,run=None,create_s3_creds=False):
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
        cloud
        
    ]
    try:
        if debug:
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
    elif quota_type == 'ceph_keystone':
        # Command takes units in bytes
        cmd = ["/usr/local/sbin/update_ceph_s3_quotas.sh",
                "%s" % username,
                "%s" % tenant,
                "%s" % quota_value,
            ]
    elif quota_type == 'ceph_ceph':
        # Command takes units in bytes
        cmd = ["/usr/local/sbin/update_ceph_s3_quotas-native.sh",
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
    elif quota_type == 'ram':
        cmd = [ '/usr/local/sbin/update_nova_ram_quotas.sh',
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


def get_tenant_members(tenant=None,users_cloud=None,debug=None):
    """ Return list of users in a tenant, the client API wants the user we run as to be a member of every tenant we query :( """

    query = """select c.name as User_Name
        from keystone.project a
            join keystone.assignment b
                on b.target_id = a.id
            join keystone.user c
                on b.actor_id = c.id
        where 
            a.name='%s'
        """ % (tenant)    

    if users_cloud:
        query += """ and c.extra like '{"email": "CLOUD:%s,%%'""" % (users_cloud)

    members = set()

    if debug:
        print query

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


        
def remove_member_from_tenant(tenant=None, users=None, role="_member_", debug=None, run=None):
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
        if debug:
            print "DEBUG: Removing %s from tenant %s and role %s" %(user,tenant,role)
            pprint.pprint(cmd)

        if run:
            try:
                result = subprocess.check_call( cmd , stderr=open(os.devnull, 'wb'))
            except subprocess.CalledProcessError, e:
                sys.stderr.write("Error: Removing  user %s to tenant %s\n" % (username,tenant) )
                sys.stderr.write("%s\n" % e.output)
        

def add_member_to_tenant(tenant=None, users=None, role="_member_", ceph_auth_type=None, debug=None, run=None,create_s3_creds=False):
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
            print "DEBUG: Adding %s to tenant %s and role %s" %(user,tenant,role)
            pprint.pprint( cmd )

        if run:
            try:
                result = subprocess.check_call( cmd, stderr=open(os.devnull, 'wb')  )
            except subprocess.CalledProcessError, e:
                sys.stderr.write("Error: Adding  user %s to tenant %s\n" % (user,tenant) )
                sys.stderr.write("%s\n" % e.output)

            if create_s3_creds:
                create_ceph_s3_creds(tenant=tenant,username=user,ceph_auth_type=ceph_auth_type,debug=debug,run=run)
            

def adjust_managed_tenants(managed_tenants=None,users_cloud=None,ceph_auth_type=None,debug=None,run=None):
    #Fix the tenants for manged groups
    #csv_tenant_members = 
    #approved_tenant_members
    #current_tenant_members =  currently on system as memebrs
    #valid_tenant_memebers = they are the ones we are keeping in the tennat
    #invalid_tenant_members = users we need to remove from a tenant
    #additional_tenant_members = users we need to add
    if debug:
        pprint.pprint( managed_tenants.items()  )

    for tenant_name, csv_tenant_members in managed_tenants.items():
        #Intersection of CSV and SalesForce
        approved_tenant_members = csv_tenant_members.intersection( approved_members )
        #Current users in tenant
        current_tenant_members = get_tenant_members(tenant=tenant_name,users_cloud=users_cloud,debug=debug)
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
       
        remove_member_from_tenant(tenant=tenant_name, users=invalid_tenant_members, debug=debug, run=run)
        add_member_to_tenant(tenant=tenant_name, users=additional_tenant_members,ceph_auth_type=ceph_auth_type, debug=debug, run=run)

def adjust_tenants(members_list=None,users_cloud=None,ceph_auth_type=None,debug=None,run=None,create_s3_creds=False):
    #Build tenant lists
    for username, fields in members_list.items():
        if fields['tenant'] not in tenant_members:
            tenant_members[fields['tenant']]=[]
        tenant_members[fields['tenant']].append(username)

        if fields['subtenants']:
            for subtenant in fields['subtenants'].split(','):
                if subtenant not in tenant_members:
                    tenant_members[subtenant]=[]
                tenant_members[subtenant].append(username)

    if debug:
        print "DEBUG: adjusting_tenants tenant_members"
        pprint.pprint(tenant_members)  

    for tenant in tenant_members.keys():
        members=tenant_members[tenant]

        #Build lists of who is currently, needs to be added, needs to be removed
        current_members=get_tenant_members(tenant,users_cloud=users_cloud,debug=debug)
        members_to_add=set(members)-set(current_members)
        members_to_remove=set(current_members)-set(members)

        if debug:
            print "DEBUG: adjusting_tenants current tenant list"
            pprint.pprint( tenant ) 
            pprint.pprint( members )
            pprint.pprint( current_members )
            pprint.pprint( members_to_add )
            pprint.pprint( members_to_remove )

        #remove and add as needed
        add_member_to_tenant(tenant=tenant, users=members_to_add, role="_member_", debug=debug, run=run, create_s3_creds=create_s3_creds)
        remove_member_from_tenant(tenant=tenant, users=members_to_remove, role="_member_", debug=debug, run=run)
        

def adjust_quotas(members_list=None,debug=None,run=None):
    """ Adjusts tenants quotas """

    for username, fields in members_list.items():

        if debug:
            print "DEBUG: Username from SF = %s" % (username) 

        try:
            user_exists = pwd.getpwnam(username)
        except:
            user_exists = None

        #Set storage quota if leader
        if user_exists and fields['quota_leader']:
            if ( fields['object_storage_quota'] or fields['object_storage_quota']==0) and set_ceph_quota:
                set_quota(username=username, tenant=fields['tenant'], quota_type=ceph_auth_type, quota_value=fields['object_storage_quota'], debug=debug,run=run)

            if ( fields['block_storage_quota'] or fields['block_storage_quota']==0 ) and set_cinder_quota:
                #takes quota in GibaBytes
                set_quota(username=username, tenant=fields['tenant'], quota_type="cinder", quota_value=fields['block_storage_quota'], debug=debug,run=run)

            if fields['core_quota'] or fields['core_quota']==0:
                set_quota(username=username, tenant=fields['tenant'], quota_type="core", quota_value=fields['core_quota'], debug=debug,run=run)

            if fields['ram_quota'] or fields['ram_quota']==0:
                set_quota(username=username, tenant=fields['tenant'], quota_type="ram", quota_value=fields['ram_quota'], debug=debug,run=run)
            elif fields['ram_quota'] is None and fields['core_quota']:
                ram_quota=fields['core_quota']*3*1024
                set_quota(username=username, tenant=fields['tenant'], quota_type="ram", quota_value=ram_quota, debug=debug,run=run)


if __name__ == "__main__":

    #Load in the CLI flags
    run = True
    debug = False
    nih_file = False
    tukey = True
    approved_members = set()
    tenant_members = dict()
    set_ceph_quota = True
    create_s3_creds = False
    set_cinder_quota = True
    ceph_auth_type = None
    multicloud = False

    try:
        opts, args = getopt.getopt(sys.argv[1:], "", ["debug", "norun", "nihfile=", "nocephquota", "ceph-keystone-s3", "ceph-native-s3", "nocinderquota"])
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
        elif opt in ("--nocinderquota"):
            set_cinder_quota = False
        elif opt in ("--nocephquota"):
            set_ceph_quota = False
        #ceph-keystone-s3 uses keystone/swift with ceph object store (legacy)
        elif opt in ("--ceph-keystone-s3"):
            create_s3_creds = True
            ceph_auth_type="ceph_keystone"
        #ceph-native-s3 uses radosgw-admin for direct creation of s3 users/subusers via ceph api
        elif opt in ("--ceph-native-s3"):
            create_s3_creds = True
            ceph_auth_type="ceph_ceph"
        #Some of our clouds share backends but have different frontends, this scans for this marker
        elif opt in ("--multicloud"):
            multicloud=True
	

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

    if multicloud:
        users_cloud = settings['general']['cloud']
    else:
        users_cloud = None
    


    #Load up a list of the users in SF that are approved for this cloud
    sfocc.login(username=settings['salesforceocc']['sfusername'], password=settings['salesforceocc']['sfpassword'])
    contacts = sfocc.get_contacts_from_campaign(campaign_name=settings['salesforceocc']['campaign'],  statuses=["Approved User", "Application Pending","CDIS System User"])
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

                for username, fields in members_list.items():
                    #Nih style changes....i am doing this wrong
                    if nih_file:
                        if fields['eRA_Commons_username'].upper()  in nih_approved_users:
                            new_username=fields['eRA_Commons_username'].upper()
                            members_list[new_username] = members_list.pop( username )
                            members_list[new_username]['username'] = new_username
                            members_list[new_username]['login_identifier'] = "urn:mace:incommon:nih.gov!https://bionimbus-pdc.opensciencedatacloud.org/shibboleth!%s"%(new_username)
                        else:
                            continue


                        
        except IOError as e:
            sys.exit('file %s not found: %s' % (nih_file, e))
        except csv.Error as e:
            sys.exit('file %s, line %d: %s' % (filename, reader.line_num, e))
    


    #Loop through list of members and run the bash scripts that will create the account
    #FIXME: Most of this stuff could be moved into the python, just simpler not to
    print "Creating New Users:"
    for username, fields in members_list.items():

        #I fail at a good flow for creating new tenant+user combo vs existing tenant+new user
        user_created = None

        if nih_file:
            if fields['eRA_Commons_username'].upper()  in nih_approved_users:
                pass
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
                            print "INFO: Creating users %s" % username
                            user_created = create_user(username=username,cloud=settings['general']['cloud'], fields=fields, debug=debug, run=run)
                            add_member_to_tenant(role='quota_leader', tenant=fields['tenant'],users=[username], debug=debug, run=run)
                            if create_s3_creds:
                                create_ceph_s3_creds(tenant=fields['tenant'],username=username,ceph_auth_type=ceph_auth_type,debug=debug,run=run)
                        else:
                            sys.stderr.write("ERROR: Creating new tenant %s skipping user creation.\n" % fields['tenant'] )
                    else:
                        #Can not create a user with out an existing tenant
                        sys.stderr.write("ERROR: New User %s has no existing tenant %s \n" % (username, fields['tenant']) )
                        continue
        
            #Create the user in existing tenant
            if username and not user_created:
                print "INFO: Creating users %s" % username
                create_user(username=username,cloud=settings['general']['cloud'],fields=fields, debug=debug, run=run)
                if create_s3_creds:
                    create_ceph_s3_creds(tenant=fields['tenant'],ceph_auth_type=ceph_auth_type,username=username,debug=debug,run=run)

    #Apply Quotas
    print "Setting Quotas"
    adjust_quotas(members_list=members_list,debug=debug,run=run)     

    #adjust tenants and subtenant membership        
    print "Adjusting tenant membership"
    adjust_tenants(members_list=members_list,users_cloud=users_cloud,debug=debug,run=run,create_s3_creds=create_s3_creds,ceph_auth_type=ceph_auth_type)     

    #Lock users
    print "Locking/Unlocking Users:"
    try:
        starting_uid=int(settings['general']['starting_uid'])
    except KeyError:
        starting_uid=1500
    toggle_user_locks(approved_members=approved_members,starting_uid=starting_uid,debug=debug) 

    print "Adjusting managed tenant membership:" 
    adjust_managed_tenants(managed_tenants=managed_tenants,users_cloud=users_cloud,ceph_auth_type=ceph_auth_type, debug=debug,run=run)

    
