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

#from keystoneclient.auth.identity import v3
#from keystoneclient.auth.identity import v2
#from keystoneclient import session
from keystoneclient.v3 import client #, users, role_assignments, roles

from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client

def get_project_members_v2(project,debug=None):
    """ Return list of users in a tenant, the client API wants the user we run as to be a member of every tenant we query :( """
    #load in Admin creds
    #Get the ENV overrides
    admin_auth_creds = dict()
    admin_auth_creds['username'] = os.environ.get('OS_USERNAME')
    admin_auth_creds['password'] = os.environ.get('OS_PASSWORD')
    admin_auth_creds['auth_url'] = os.environ.get('OS_AUTH_URL')
    if os.environ.get('OS_TENANT_NAME') and not os.environ.get('OS_PROJECT_NAME'):
        admin_auth_creds['tenant_name'] = os.environ.get('OS_TENANT_NAME')
    elif os.environ.get('OS_PROJECT_NAME'):
        admin_auth_creds['project_name'] = os.environ.get('OS_PROJECT_NAME')
    if os.environ.get('OS_PROJECT_DOMAIN_NAME'):
        admin_auth_creds['project_domain_name'] = os.environ.get('OS_PROJECT_DOMAIN_NAME')
    if os.environ.get('OS_USER_DOMAIN_NAME'):
        admin_auth_creds['user_domain_name'] = os.environ.get('OS_USER_DOMAIN_NAME')

    #RAY FIXME: This works for Liberty, might need v3 for mitaka?
    ## Index of the  auth_url endpoint ?
    #auth = v2.Password(**admin_auth_creds)
    #sess = session.Session(auth=auth)
    #keystone_client = client.Client(session=sess)

    auth = v3.Password( **admin_auth_creds )
    sess = session.Session(auth=auth)
    keystone_client = client.Client(session=sess)
    
    #Find the project's id
    for kp in keystone_client.projects.list():
        if kp.name == project:
            project_id = kp.id
    #Find _member_ role id
    for kr in keystone_client.roles.list():
        if kr.name == "_member_":
            role_id = kr.id

    #Get assignments
    user_names = set()
    for assignment in keystone_client.role_assignments.list(project=project_id, role=role_id):
        if hasattr(assignment, 'user'):
            user_names.add( keystone_client.users.get( user=assignment.user['id'] ).name )

    return user_names
    
        
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
        if debug:
            print "DEBUG: No known ceph_auth_type specified:" % ( ceph_auth_type ) 
        return False

    if debug:
        print "DEBUG: create_ceph_s3_creds %s cmd:" % (__name__) 
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
        subprocess.check_call( ['/usr/local/sbin/does_project_exist.sh', tenant ], stdout=open(os.devnull, 'wb') )
        return True
    except subprocess.CalledProcessError, e:
        return False


def create_project(tenant, debug=None, run=None, domain=None):
    """ call the bash scripts to create tenants """
    if run:
        try:
            if domain:
                cmd = ['openstack','project', 'create', '--domain=%s'%(domain), '%s'%(tenant)]
            else:
                cmd = ['openstack','project', 'create', '%s'%(tenant)]
                
            subprocess.check_call( cmd , stdout=open(os.devnull, 'wb'),stderr=open(os.devnull, 'wb') )
            return True
        except subprocess.CalledProcessError, e:
            sys.stderr.write("Error creating  new tenant:  %s\n" % username )
            sys.stderr.write("CMD:  %s\n" % cmd )
            sys.stderr.write("%s\n" % e.output)
            return False
    else:
        return True

def create_user(username,cloud,fields,is_nih_cloud=False,debug=None,run=None):
    """ Call create user script """
    if fields['Authentication_Method'] == 'OpenID':
        method = 'openid'
    else:
        method = 'shibboleth'
    
    
    #If we have an identifier use that, otherwise fallback to email
    if not fields['login_identifier']:
        login_identifier = fields['Email']
    else:
        login_identifier = fields['login_identifier']

    #Create user
    print "INFO: Creating new user: %s" % username
    cmd = [
        '/usr/local/sbin/create-user.sh',
        fields['Name'],
        username,
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

def remove_member_from_tenant(tenant=None, users=None, role="_member_", debug=None, run=None):
    """  Remove users from the tenant """
    for user in users:
        if user == 'admin':
            continue

        print "INFO: Removing user %s from tenant %s" % (user, tenant)
        cmd = [ 'openstack', 
                'role',
                'remove', 
                '--project=%s'%(tenant),
                '--user=%s'%(user),
                '%s'%(role) 
        ]
        if debug:
            print "DEBUG: Removing %s from tenant %s and role %s" %(user,tenant,role)
            pprint.pprint(cmd)

        if run:
            try:
                #result = subprocess.check_call( cmd , stderr=open(os.devnull, 'wb'))
                result = subprocess.check_call( cmd )
            except subprocess.CalledProcessError, e:
                sys.stderr.write("Error: Removing  user %s from tenant %s\n" % (user,tenant) )
                sys.stderr.write("%s\n" % e.output)
        

def add_member_to_project(project=None, users=None, role="_member_", ceph_auth_type=None, debug=None, run=None,create_s3_creds=False, domain=None):
    """ Add users to the project """  
    for user in users:
        print "INFO: Adding user %s to project %s" % (user, project)

        cmd = [ 'openstack',
                'role',
                'add', 
                '--project=%s'%(project),
                '--user=%s'%(user),
                '%s'%(role) 
        ]

        if debug:
            print "DEBUG: Adding %s to project %s and role %s" %(user,project,role)
            pprint.pprint( cmd )

        if run:
            try:
                #result = subprocess.check_call( cmd, stderr=open(os.devnull, 'wb')  )
                result = subprocess.check_call( cmd )
            except subprocess.CalledProcessError, e:
                sys.stderr.write("Error: Adding  user %s to project %s\n" % (user,project) )
                sys.stderr.write(">%s\n" % e.output)

            if create_s3_creds:
                create_ceph_s3_creds(tenant=project,username=user,ceph_auth_type=ceph_auth_type,debug=debug,run=run)
            

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
        current_tenant_members = get_project_members_v2(project=tenant_name,debug=debug)
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
        add_member_to_project(project=tenant_name, users=additional_tenant_members,ceph_auth_type=ceph_auth_type, domain=settings['openstack']['domain'], debug=debug, run=run)

def adjust_tenants(members_list=None,list_of_approved_user_names=None,users_cloud=None,ceph_auth_type=None,debug=None,run=None,create_s3_creds=False):
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

    #if debug:
    #    print "DEBUG: adjusting_tenants tenant_members"
    #    pprint.pprint(tenant_members)  

    for tenant in tenant_members.keys():
        if debug:
            print "DEBUG: adjusting_tenants tenant_members for tenant %s" %(tenant)
            pprint.pprint(tenant_members[tenant])  

        if list_of_approved_user_names is not None:
            members=set( tenant_members[tenant] ) & set(list_of_approved_user_names)
        else:
            members=set( tenant_members[tenant] )

        if debug:
            print "DEBUG: adjusting_tenants: members"
            pprint.pprint(members)  

        #Build lists of who is currently, needs to be added, needs to be removed
        current_members=get_project_members_v2(tenant,debug=debug)
        members_to_add=set(members)-set(current_members)
        members_to_remove=set(current_members)-set(members)

        if debug:
            print "DEBUG: adjusting_tenants current tenant list"
            print "DEBUG: adjusting_tenants current tenant list - tenant"
            pprint.pprint( tenant ) 
            print "DEBUG: adjusting_tenants current tenant list - members"
            pprint.pprint( members )
            print "DEBUG: adjusting_tenants current tenant list - current_members"
            pprint.pprint( current_members )
            print "DEBUG: adjusting_tenants current tenant list - members_to_add"
            pprint.pprint( members_to_add )
            print "DEBUG: adjusting_tenants current tenant list - members_to_remove"
            pprint.pprint( members_to_remove )

        #remove and add as needed
        add_member_to_project(project=tenant, users=members_to_add, role="_member_", debug=debug, run=run, ceph_auth_type=ceph_auth_type, create_s3_creds=create_s3_creds,domain=settings['openstack']['domain'])
        remove_member_from_tenant(tenant=tenant, users=members_to_remove, role="_member_", debug=debug, run=run)
        

def adjust_quotas(members_list=None,debug=None,run=None):
    """ Adjusts tenants quotas """

    for username, fields in members_list.items():

        if debug:
            print "DEBUG: Username from SF = %s" % (username) 

        user_exists = get_user_exists(username=username)

        if debug:
            print "DEBUG: Username %s exists? %s " % (username,user_exists) 

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



def load_in_nih_file(settings=None,nih_approved_users=None,managed_tenants=None,members_list=None):
    #Load up a nih style csv of approved users.
    #user_name is the actual human name
    #login is the name we care about.
    #phsid is also important eventually
        
        if debug:
            print "DEBUG: load_in_nih_file maned_tenants start:" 
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

                if debug:
                    print "DEBUG: load_in_nih_file maned_tenants middle:" 
                    pprint.pprint(managed_tenants)


                for username, fields in members_list.items():
                    #Nih style changes....i am doing this wrong
                    if nih_file:
                        if fields['eRA_Commons_username'].upper()  in nih_approved_users:
                            new_username=fields['eRA_Commons_username'].upper()
                            members_list[new_username] = members_list.pop( username )
                            members_list[new_username]['username'] = new_username
                            members_list[new_username]['login_identifier'] = "urn:mace:incommon:nih.gov!https://bionimbus-pdc.opensciencedatacloud.org/shibboleth!%s"%(new_username)
                            try:
                                del members_list[username]
                            except KeyError:
                                pass
                        else:
                            continue
                if debug:
                    print "DEBUG: nih style members_list:" 
                    pprint.pprint(members_list)
                        
        except IOError as e:
            sys.exit('file %s not found: %s' % (nih_file, e))
        except csv.Error as e:
            sys.exit('file %s, line %d: %s' % (filename, reader.line_num, e))

        return (nih_approved_users,managed_tenants,members_list)


def load_in_other_file(other_file=None,debug=None):
        try:
            with open(other_file, 'r') as handle:
                reader = csv.DictReader(handle, ['user_name','login','email', 'status', 'phsid' ])
                # Loop through csv and load the user info
                # we are loading the phsids as an array
                for row in reader:
                    try:
                        if type(other_approved_users[row['login'].lower()]) is not list:
                            other_approved_users[row['login'].lower()]=[]
                    except KeyError:
                        other_approved_users[row['login'].lower()]=[]
                    #add in phsid to array
                    other_approved_users[row['login'].lower()].append(row['phsid'])

                if debug:
                    print "DEBUG: load_in_other_file : other_approved_users" 
                    pprint.pprint(other_approved_users)


        except IOError as e:
            sys.exit('file %s not found: %s' % (nih_file, e))
        except csv.Error as e:
            sys.exit('file %s, line %d: %s' % (filename, reader.line_num, e))

        return other_approved_users


def get_user_exists(username=None, user_checker="openstack", debug=None):
    """Checks if user exists and returns True or None"""    

    user_exists = None

    if user_checker == "openstack":
        try:
            subprocess.check_call( ['openstack','user', 'show', '%s'%(username)], stdout=open(os.devnull, 'wb'),stderr=open(os.devnull, 'wb') )
        except subprocess.CalledProcessError, e:
            user_exists = None
        else:
            user_exists = True

    elif user_checker == "pwd":
        try:
            user_exists = pwd.getpwnam(username)
        except:
            user_exists = None

    return user_exists


if __name__ == "__main__":

    #Load in the CLI flags
    run = True
    debug = False
    is_nih_cloud=False
    nih_file = False
    other_file = False
    tukey = True
    approved_members = set()
    tenant_members = dict()
    set_ceph_quota = True
    create_s3_creds = False
    set_cinder_quota = True
    ceph_auth_type = None
    multicloud = False
    user_checker = "openstack"

    try:
        opts, args = getopt.getopt(sys.argv[1:], "", ["debug", "norun", "nihfile=", "otherfile=", "nocephquota", "ceph-keystone-s3", "ceph-native-s3", "nocinderquota","multicloud","notukey"])
    except getopt.GetoptError:
        sys.stderr.write("ERROR: Getopt\n")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("--debug"):
            debug = True
        elif opt in ("--norun"):
            run = False
        elif opt in ("--nihfile"):
            is_nih_cloud=True
            nih_file = arg
            nih_approved_users = {}
        elif opt in ("--otherfile"):
            is_nih_cloud=True
            other_file = arg
            other_approved_users = {}
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
    sections = ['general','salesforceocc','tukey', 'accounts','openstack']
    settings = {}
    for section in sections:
        options = Config.options(section)
        settings[section]={}
        for option in options:
            try:
                settings[section][option] = Config.get(section, option)
                if settings[section][option]=='None':
                    settings[section][option] = None
            except:
                sys.stderr.write("exception on [%s] %s!" % section, option)

    #One offs:
    try:
        settings['accounts']['managed_tenants']=settings['accounts']['managed_tenants'].split(',')
        managed_tenants={}
        # Loop through managed tenants in config and initialize
        #Setting to set() since we need to do intersections and differences
        for managed_tenant in settings['accounts']['managed_tenants']:
            if managed_tenant:
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

    #Kludge to deal wiht add/removing from tenants and quotas
    if nih_file or other_file:
        list_of_approved_user_names = []
    else:
        list_of_approved_user_names = None

    if nih_file:
        nih_approved_users,managed_tenants,members_list=load_in_nih_file(settings=settings,nih_approved_users=nih_approved_users,managed_tenants=managed_tenants,members_list=members_list)
        list_of_approved_user_names += nih_approved_users.keys()
    if other_file:
        other_approved_users=load_in_other_file(other_file=other_file,debug=debug)
        list_of_approved_user_names += other_approved_users.keys()

    if debug:
        print "DEBUG: list_of_approved_user_names"
        pprint.pprint( list_of_approved_user_names )




    #Loop through list of members and run the bash scripts that will create the account
    #FIXME: Most of this stuff could be moved into the python, just simpler not to
    print "Creating New Users:"
    if debug:
        try:
            print "DEBUG: nih_approved_users"
            pprint.pprint( nih_approved_users ) 
        except:
            pass
        try:
            print "DEBUG: other_approved_users"
            pprint.pprint( other_approved_users ) 
        except:
            pass
        print "DEBUG: memers_list.items()"
        pprint.pprint( members_list.items() ) 
        
        

    for username, fields in members_list.items():

        #I fail at a good flow for creating new tenant+user combo vs existing tenant+new user
        user_created = None
        user_exists = None
        
        if nih_file or other_file:
            if nih_file and ( fields['eRA_Commons_username'].upper()  in nih_approved_users):
                if debug:
                    print "DEBUG: eRA_Commons_username from SF(%s) in nih_file(%s) " % (username,fields['eRA_Commons_username'].upper()) 
                    pass
            elif other_file and ( fields['username'].lower() in other_approved_users):
                if debug:
                    print "DEBUG: Username from SF(%s) in other_file(%s) " % (username,fields['username'].lower()) 
                    pass
            elif other_file and ( fields['eRA_Commons_username'].lower() in other_approved_users):
                #I have no clue if this will create duplication issues 
                #newusername.lower() is cause im stupid, and read in lower in oen spot, but apply normal other 
                newusername=fields['eRA_Commons_username']
                members_list[newusername] = members_list.pop( username  )
                list_of_approved_user_names.remove( newusername.lower() )
                list_of_approved_user_names.append( newusername )
                members_list[newusername]['username']=newusername
                username=newusername
                if debug:
                    print "DEBUG: eRA_Commons_username from SF(%s) in other_file(%s) " % (username,fields['eRA_Commons_username'])
                    pass
            else:
                if debug:
                    print "DEBUG: Username from SF(%s) not in any files" % (username) 
                continue


        #At some point we need to disable inactive users
        approved_members.add(username)
        if debug:
            print "DEBUG: Username (%s) added to approved_members." % (username) 
       
        user_exists = get_user_exists(username=username)
        if debug:
            print "DEBUG: Username %s exists? %s " % (username,user_exists) 

        if not user_exists:
            if debug:
                print "DEBUG: Username %s does not exist" % (username) 

            if fields['tenant']:
                if not tenant_exist(fields['tenant']):
                    if fields['quota_leader']:
                        #Will create the new tenant
                        print "INFO: Creating new tenant %s" % (fields['tenant'])
                        if create_project(tenant=fields['tenant'], debug=debug,run=run,domain=settings['openstack']['domain']):
                            print "INFO: Creating users %s" % username
                            user_created = create_user(username=username,cloud=settings['general']['cloud'], fields=fields, is_nih_cloud=is_nih_cloud, debug=debug, run=run)
                            add_member_to_project(role='quota_leader', project=fields['tenant'],users=[username], debug=debug, run=run,domain=settings['openstack']['domain'])
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
                create_user(username=username,cloud=settings['general']['cloud'],fields=fields,is_nih_cloud=is_nih_cloud, debug=debug, run=run)
                if create_s3_creds:
                    create_ceph_s3_creds(tenant=fields['tenant'],ceph_auth_type=ceph_auth_type,username=username,debug=debug,run=run)

    ##Apply Quotas
    print "Setting Quotas"
    adjust_quotas(members_list=members_list,debug=debug,run=run)     

    ##adjust tenants and subtenant membership        
    print "Adjusting tenant membership"
    adjust_tenants(members_list=members_list,
        list_of_approved_user_names=list_of_approved_user_names,
        users_cloud=users_cloud,
        create_s3_creds=create_s3_creds,ceph_auth_type=ceph_auth_type,
        debug=debug,run=run)

    #Lock users
    print "Locking/Unlocking Users:"
    try:
        starting_uid=int(settings['general']['starting_uid'])
    except KeyError:
        starting_uid=1500
    toggle_user_locks(approved_members=approved_members,starting_uid=starting_uid,debug=debug) 

    print "Adjusting managed tenant membership:" 
    if managed_tenants:
        adjust_managed_tenants(managed_tenants=managed_tenants,users_cloud=users_cloud,ceph_auth_type=ceph_auth_type, debug=debug,run=run)

    
