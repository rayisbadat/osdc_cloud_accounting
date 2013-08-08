import os 
import sys
import getopt
import ConfigParser
import pprint

from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError

#keystone libs
from keystoneclient.v2_0 import client as kc_client
from keystoneclient.v2_0 import users, tenants
from keystoneclient.exceptions import AuthorizationFailure, Unauthorized

#Nova calls
### I am worried about the level of control this has
from novaclient.v1_1 import client as nc_client
from novaclient.v1_1 import flavors,images

#All this just to convert dates
from datetime import datetime, timedelta, date
from pytz import timezone
import pytz

#The gluster poller
from pollgluster import PollGluster

# Here are the email package modules we'll need
import smtplib
from email.mime.text import MIMEText
from email.mime.message import MIMEMessage
from email.mime.base  import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.encoders import encode_base64
import mimetypes



class UserUsageStat:
    """This is an object to store a users info"""
    def __init__(self, username, corehrs=0, du=0):
        self.username=username
        self.corehrs=corehrs
        self.du=du


class TenantsStats:
    """Class stores the tenants users"""
    def __init__(self, name, uuid=None):
        self.name=name
        self.uuid=uuid
        self.members={}
        self.corehrs=0
        self.du=0

    def add_member(self, username, corehrs=0, du=0):
        self.members[username] = UserUsageStat(username=username, corehrs=corehrs, du=du)

    def set_tenant_stat(self, corehrs=0, du=0):
        self.corehrs = corehrs
        self.du = du

    def update_member(self, username, corehrs=None, du=None):
        if corehrs is not None:
            self.members[username].corehrs=corehrs
        if du is not None:
            self.members[username].du=du

    def list_members(self):
        members_list = []
        for key,value in self.members.items():
            members_list.append(key)
        return members_list

    def sum_tenant_corehrs(self):
        corehrs=0
        for key,value in self.members.items():
            if value.corehrs is not None:
                corehrs += value.corehrs
        return corehrs

    def sum_tenant_du(self):
        du=0
        for key,value in self.members.items():
            if value.du is not None:
                du += value.du
        return du

    def get_tenant_du(self):
        return self.du

    def get_tenant_corehrs(self):
        return self.corehrs

    def get_csv(self,tenant_reporting=True):
        csv = []
        if tenant_reporting is True:
            csv.append( "(%s),,%s,%s" % (self.name, self.get_tenant_corehrs(),
                self.get_tenant_du()) )
            for key,value in self.members.items():
                csv.append( "(%s),%s,%s,%s" % (self.name, key, value.corehrs, value.du) )
        else:
            for key,value in self.members.items():
                if self.name == key:
                    csv.append( "(%s),%s,%s,%s" % (self.name, key, value.corehrs, value.du) )
            

        return csv


class NovaUserReporting:
    def __init__(self,config_file):
        """INit the function"""
        #Dict of settings
        self.settings={}
        self.cloud_tenants = {}

        #Stores the csv
        self.csv = []

        #read in settings
        Config = ConfigParser.ConfigParser()
        Config.read(config_file)
        sections =  Config.sections()
        for section in sections:
            options = Config.options(section)
            for option in options:
                try:
                    self.settings[option] = Config.get(section, option)
                except:
                    sys.stderr.write("exception on [%s] %s!" % section,option)


        #Get the ENV overrides
        self.override_nova_creds_with_env('OS_USERNAME')
        self.override_nova_creds_with_env('OS_PASSWORD')
        self.override_nova_creds_with_env('OS_AUTH_URL')
        self.override_nova_creds_with_env('OS_TENANT_NAME')

        #Should we do tenant auditing
        self.tenant_reporting = True

    def set_tenant_reporting(self,value):
        self.tenant_reporting = value
    
    def override_nova_creds_with_env(self,keyname):
       #Get the nova auth stuff if not already
        try:
            self.settings[keyname]
        except KeyError:
            try:
                self.settings[keyname] = os.environ.get(keyname)
            except KeyError:
                sys.stderr.write("ERROR: KeyError on pulling ENV\n")
                sys.exit(1)

    def set_time_range(self,start_date=None, end_date=None):
        """ Set the time range """
        
        # Set time zone and localize inputs
        try:
            self.timezone = pytz.timezone(self.settings['timezone'])
        except KeyError:
            self.timezone = pytz.tzinfo()

        localize_timezone = timezone(self.settings['timezone'])

        try:
            self.start_time = localize_timezone.localize(
                (
                    datetime.strptime(start_date,self.settings['timeformat']
                    )
                )
            )
        except ValueError:
            sys.stderr.write("ERROR: Start time not in proper format '%s'\n" % (
                self.settings['timeformat']
            ))
            sys.exit(1)

        try:
            self.end_time = localize_timezone.localize(
                datetime.strptime(end_date,self.settings['timeformat'])
            )
        except ValueError:
            sys.stderr.write("ERROR: End time not in proper format '%s'\n" % (
                self.settings['timeformat']
            ))
            sys.exit(1)

        self.now_time = datetime.now(tz=pytz.timezone('UTC'))



        #Ceiling is either NOW() or the specified date
        if self.end_time < self.now_time:
            self.cieling_time = self.end_time
        else:
            self.cieling_time = self.now_time

    def db_connect(self,db):
        try:
            dsn = "mysql://%s:%s@%s/%s" % ( self.settings['uid'], 
                self.settings['pwd'], self.settings['server'], db)
            engine = create_engine(dsn)
            return engine.connect()

        except SQLAlchemyError, e:
            sys.stderr.write("Error %d: %s" % (e.args[0], e.args[1]))
            sys.exit(1)
        
    def get_corehrs(self, user_id=None, tenant_id=None):
        """Fetch the core hrs for a uuid, can be by tenant or user"""
        corehrs_total =0;
        query_base = """SELECT
                        created_at,
                        updated_at,
                        deleted_at,
                        deleted,
                        id,
                        internal_id,
                        user_id,
                        project_id,
                        image_ref,
                        kernel_id,
                        ramdisk_id,
                        server_name,
                        launch_index,
                        key_name,
                        key_data,
                        power_state,
                        vm_state,
                        memory_mb,
                        vcpus,
                        hostname,
                        host,
                        user_data,
                        reservation_id,
                        scheduled_at,
                        launched_at,
                        terminated_at,
                        display_name,
                        display_description,
                        availability_zone,
                        locked,
                        os_type,
                        launched_on,
                        instance_type_id,
                        vm_mode,
                        uuid,
                        architecture,
                        root_device_name,
                        access_ip_v4,
                        access_ip_v6,
                        config_drive,
                        task_state,
                        default_ephemeral_device,
                        default_swap_device,
                        progress,
                        auto_disk_config,
                        shutdown_terminate,
                        disable_terminate,
                        root_gb,
                        ephemeral_gb,
                        cell_name

                    from nova.instances where vm_state != 'error' and
                    (
                        ( launched_at >= '%s' and launched_at <= '%s' )
                        or
                        ( created_at >= '%s' and created_at <= '%s' )
                        or
                        ( terminated_at >= '%s' and terminated_at <= '%s' )
                        or
                        ( deleted_at >= '%s' and deleted_at <= '%s' )
                        or
                        ( terminated_at is NULL and deleted_at is NULL and deleted = '0')
                    )
                    """ % (self.start_time.strftime(self.settings['timeformat']), self.cieling_time.strftime(self.settings['timeformat']), 
                            self.start_time.strftime(self.settings['timeformat']), self.cieling_time.strftime(self.settings['timeformat']),
                            self.start_time.strftime(self.settings['timeformat']), self.cieling_time.strftime(self.settings['timeformat']),
                            self.start_time.strftime(self.settings['timeformat']), self.cieling_time.strftime(self.settings['timeformat'])
                        )

        if user_id is None and tenant_id is not None:
            query = query_base + "and %s = '%s'" % ('project_id', tenant_id)
        elif user_id is not None and tenant_id is None:
            query = query_base + "and %s = '%s'" % ('user_id', user_id)
        elif user_id is not None and tenant_id is not None:
            query = query_base + "and ( %s = '%s' and %s = '%s')" % ( 'project_id', tenant_id, 'user_id', user_id)
        else:
            sys.stderr.write("ERROR: How did you get here?\n")
            sys.exit(1)

        try:
            conn = self.db_connect(self.settings['novadb'])
            s = text(query)
            results = conn.execute(s)
        except SQLAlchemyError:
            sys.stderr.write("ERROR: Erroring querying the databases\n")
            sys.exit(1)

        #Break out the values we need 
        for row in results:
            try:
                updated_at = row[1].replace(tzinfo=timezone('UTC'))
            except AttributeError:
                updated_at = None
        
            try:
                deleted_at = row[2].replace(tzinfo=timezone('UTC'))
            except AttributeError:
                deleted_at = None
            
            deleted = int(row[3])
            user_id = row[6]
            project_id = row[7]
            instance_type_id = int(row[32])
            vcpus = int(row[18])

            try:
                launched_at = row[24].replace(tzinfo=timezone('UTC'))
            except AttributeError:
                launched_at = None


            try:
                scheduled_at = row[23].replace(tzinfo=timezone('UTC'))
            except AttributeError:
                scheduled_at = None

            try:
                terminated_at = row[25].replace(tzinfo=timezone('UTC'))
            except AttributeError:
                terminated_at = None
            uuid = row[34]            
            task_state = row[40]
      
            #Edge case for when VM started
            if launched_at is None:
                if scheduled_at is not None:
                    better_launched_at = scheduled_at
                else:
                    better_launched_at = created_at
            else:
                better_launched_at = launched_at

  
            #Find the term time for a vm 
            if deleted == 1 and terminated_at is not None:
                better_terminated_at = terminated_at
            elif deleted == 1 and deleted_at is not None:
                better_terminated_at = deleted_at
            elif deleted == 1 and updated_at is not None:
                better_terminated_at = updated_at
            elif deleted == 1 and deleted_at is None:
                #Something Bad happened ignore this VM
                better_terminated_at = better_launched_at
            elif deleted == 0 and deleted_at is not None:
                sys.stderr.write("ERROR: How did you get, here. Marked deleted but no deleted_at %s\n")
                sys.exit(1)
            elif deleted == 0:
                better_terminated_at = self.cieling_time
            else:
                sys.stderr.write("ERROR: You have found an unsupport VM state, investigate an extend code. uuid: %s, deleted: %s, terminated_at: %s\n" % (uuid, deleted, terminated_at))
                sys.exit(1)

            if better_terminated_at > self.cieling_time:
                safe_terminated_at = self.cieling_time
            else:
                safe_terminated_at = better_terminated_at

            if safe_terminated_at < self.start_time:
                continue
            if better_launched_at > self.cieling_time:
                continue

            #IF started before start_time adjust
            if better_launched_at <= self.start_time and safe_terminated_at >= self.start_time:
                safe_launched_at = self.start_time
            else:
                safe_launched_at = better_launched_at


            if self.start_time == self.end_time:
                #This is for the --now function.  I just want a pt in time of core used
                corehrs = vcpus
                corehrs_total += corehrs
            elif safe_launched_at >= self.start_time and safe_terminated_at <= self.cieling_time and safe_launched_at <= safe_terminated_at:
                #After all this only sum up the ones in range
                time_up = safe_terminated_at - safe_launched_at
                corehrs = (time_up.total_seconds()/3600)*vcpus
                corehrs_total += corehrs
            

        conn.close()
        return int(corehrs_total)

    def get_client(self, client_type, username=None, password=None, tenant=None,url=None):
        """ Get the client object for python*-client """
        if username is None:
            username=self.settings['OS_USERNAME']
        if password is None:
            password=self.settings['OS_PASSWORD']
        if tenant is None:
            tenant=self.settings['OS_TENANT_NAME']
        if url is None:
            url=self.settings['OS_AUTH_URL']

        try:
            if client_type is kc_client:
                kc = kc_client.Client(username=username,
                                password=password,
                                auth_url=url, 
                                tenant_name=tenant)
                return kc
            elif client_type is nc_client:
                #self, username, api_key, project_id, auth_url,
                #  insecure=False, timeout=None, proxy_tenant_id=None,
                #  proxy_token=None, region_name=None,
                #  endpoint_type='publicURL', extensions=None,
                #  service_type=None, service_name=None):
                nc = nc_client.Client(username=username,
                                api_key=password,
                                auth_url=url, 
                                project_id=tenant,
                                region_name='RegionOne',
                                
                    )
                return nc
        except AuthorizationFailure:
            sys.stderr.write("Invalid Nova Creds\n")


    def load_user_list(self,username=None, password=None, tenant=None, url=None):
        """Get list of tenants"""
        kc = self.get_client(client_type=kc_client)
        self.tenants = kc.tenants.list()
        self.users = kc.users.list()

    def load_flavor_list(self,username=None, password=None, tenant=None, url=None):
        """Get list of the flavors"""
        nc = self.get_client(client_type=nc_client)
        flavors = nc.flavors.list()

    
    def get_du(self, path=None, start_date=None, end_date=None):
        """AVG the gluster.$cloud table for a path corresponding to users homedir...hopefully"""
        g = PollGluster()
        du = g.get_average_du(
                start_date=start_date.strftime(
                    self.settings['timeformat']),
                    end_date=end_date.strftime(self.settings['timeformat']),
                    path=path)
        if du is None:
            return 0
        else:
            #Round to GB and return
            return int(du / 2**30)
                
        


    def get_stats(self, start_date=None, end_date=None):
        #Set the time range to pull reports for
        self.set_time_range(start_date = start_date, end_date = end_date)

        #Load List of Tenants and Users
        self.load_user_list()
    
        ##Find a specific tenant
        #my_tenant =[x for x in nova_user_reports.tenants if x.name=='shared_tenant_test'][0]
        #print my_tenant
        #print my_tenant.name

        #Loop through tenants
        for tenant in self.tenants:

            try:
                self.cloud_tenants[tenant] = TenantsStats(tenant.name)
            except KeyError:
                sys.stderr.write("ERROR: Duplicate Tenant\n")
                sys.exit(1)

            #Find users in a tenant
            ###FIXME do we save the tenant as its own user??
            tenant_users = tenant.list_users()
            tenant_corehrs = self.get_corehrs(tenant_id=tenant.id)
            tenant_du = self.get_du(
                path="%s/%s"%(self.settings['gprefix'],tenant.name), 
                start_date=self.start_time, end_date=self.cieling_time)
            self.cloud_tenants[tenant].set_tenant_stat(corehrs=tenant_corehrs, du=tenant_du)

            for user in tenant_users:
                corehrs = self.get_corehrs(user_id=user.id, tenant_id=tenant.id) 
                #Adjust paths for real tenants...
                du = self.get_du(
                    path="%s/%s"%(self.settings['gprefix'],user.name), 
                    start_date=self.start_time, end_date=self.cieling_time)
                if du is None:
                    du = self.get_du(
                        path="%s/%s/%s"%(self.settings['gprefix'], tenant.name, user.name), 
                        start_date=self.start_time, end_date=self.cieling_time)

                self.cloud_tenants[tenant].add_member(username=user.name, corehrs=corehrs, du=du)
  
    def gen_csv(self):
        self.csv = []
        self.csv.extend(["Tenant, User, Core Hours (H), Disk Usage (GB)"])
        for tenant in self.cloud_tenants:
            self.csv.extend(self.cloud_tenants[tenant].get_csv(tenant_reporting=self.tenant_reporting))
        
    def print_csv(self):
        #print "Tenant, User, Core Hours (H), Disk Usage (GB)"
        for line in self.csv:
            print "%s" %(line)

    def get_csv(self):
        return self.csv

    def email_csv(self,sendto=None, recvfrom=None, subject=None):
        """Send the csv to the list, sendto is a comma delimted string"""
        smtpserver = self.settings['smtphost']

        msg = MIMEMultipart()

        COMMASPACE = ', '
        if sendto is None:
            for recipient in self.settings['sendto'].split(","):
                msg.add_header('TO', recipient) 
        else:
            for recipient in sendto.split(","):
                msg.add_header('TO', recipient) 


        if recvfrom is None:
            msg['From'] =  self.settings['recvfrom']
        else:
            msg['From'] = recvfrom

        if subject is None:
            msg['Subject'] = "%s usage report for %s to %s" % ( self.settings['cloud'], self.start_time, self.end_time )
        else:
            msg['Subject'] = subject
    
        # now attach the file
        mformat, menc = mimetypes.guess_type("%s_%s-%s.csv" %(self.settings['cloud'], self.start_time, self.end_time))
        mmain, msub = mformat.split('/')
        fileMsg = MIMEBase(mmain,msub)
        attachment = "\n".join( nova_user_reports.get_csv() ) #.encode('UTF-8')
        fileMsg.set_payload( attachment  )
        encode_base64(fileMsg)
        fileMsg.add_header('Content-Disposition',"attachment;filename=%s_%s-%s.csv" %(self.settings['cloud'], self.start_time, self.end_time))
        msg.attach(fileMsg)

        #Now send it on its way
        s = smtplib.SMTP(smtpserver)
        s.sendmail(msg['From'] ,msg.get_all('TO'), msg.as_string())
        s.quit()

def weekbegend(year, week):
    """
    Calcul du premier et du dernier jour de la semaine ISO
    Used from example at http://stackoverflow.com/questions/396913/in-python-how-do-i-find-the-date-of-the-first-monday-of-a-given-week
    Week is from Monday to Sunday night

    """
    d = date(year, 1, 1)    
    delta_days = d.isoweekday() - 1
    delta_weeks = week
    if year == d.isocalendar()[0]:
        delta_weeks -= 1
    # delta for the beginning of the week
    delta = timedelta(days=-delta_days, weeks=delta_weeks)
    weekbeg = d + delta
    # delta2 for the end of the week
    delta2 = timedelta(days=6-delta_days, weeks=delta_weeks)
    weekend = d + delta2
    return weekbeg, weekend


if __name__ == "__main__":

    #some default flags
    noprint = False
    email = False
    tenant_reporting = False
    
    #Load in the CLI flags
    try:
        opts, args = getopt.getopt(sys.argv[1:], "s:e:c:", ["start=", "end=", 
            "cloud=","thismonth","lastmonth", "thisweek","lastweek","now",
            "noprint","email","tenants"])
    except getopt.GetoptError:
        sys.stderr.write("ERROR: Getopt\n")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-s", "--start",):
            start_date = arg
        elif opt in ("-end", "--end"):
            end_date = arg
        elif opt in ("-c", "--cloud"):
            pass
        elif opt in ("--thismonth"):
            now = datetime.now()
            start_date = now.strftime("%Y-%m-01 00:00:00")
            end_date = (now.replace(month=now.month+1, day=1) - timedelta(days=1)).strftime("%Y-%m-%d 23:59:59")
        elif opt in ("--lastmonth"):
            now = datetime.now()
            date = now.replace(day=1) - timedelta(days=1)
            start_date = date.strftime("%Y-%m-01 00:00:00")
            end_date = (date.replace(month=date.month+1, day=1) - timedelta(days=1)).strftime("%Y-%m-%d 23:59:59")
        elif opt in ("--thisweek"):
            now = datetime.now()
            year = int( now.strftime("%Y") )
            week = int( now.strftime("%U") )+1
            weekbeg, weekend = weekbegend( year, week)
            start_date = weekbeg.strftime("%Y-%m-%d 00:00:00")
            end_date = weekend.strftime("%Y-%m-%d 23:59:59")
        elif opt in ("--lastweek"):
            now = datetime.now()
            year = int( now.strftime("%Y") )
            week = int( now.strftime("%U") )
            weekbeg, weekend = weekbegend( year, week)
            start_date = weekbeg.strftime("%Y-%m-%d 00:00:00")
            end_date = weekend.strftime("%Y-%m-%d 23:59:59")
        elif opt in ("--now"):
            now = datetime.now()
            start_date = now.strftime("%Y-%m-%d %H:%M:%S")
            end_date = now.strftime("%Y-%m-%d %H:%M:%S")
        elif opt in ("--noprint"):
            noprint = True
        elif opt in ("--email"):
            email = True
        elif opt in ("--tenants"):
            #This prints the tenants along with the users
            tenant_reporting = True
        
        

    #initialize the clase with credentials
    nova_user_reports = NovaUserReporting(".settings")
    nova_user_reports.set_tenant_reporting(tenant_reporting)
    nova_user_reports.get_stats(start_date=start_date, end_date=end_date)
    nova_user_reports.gen_csv()



    if noprint is False:
        nova_user_reports.print_csv()

    if email is True:
        nova_user_reports.email_csv()


