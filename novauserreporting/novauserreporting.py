import os
import sys
import getopt
import ConfigParser
import pprint
import math

from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError

#keystone libs
from keystoneclient.v2_0 import client as kc_client
from keystoneclient.v2_0 import users, tenants
from keystoneclient.exceptions import AuthorizationFailure, Unauthorized

#Nova calls
### I am worried about the level of control this has
from novaclient.v1_1 import client as nc_client
from novaclient.v1_1 import flavors, images

#All this just to convert dates
from datetime import datetime, timedelta, date
from pytz import timezone
import pytz

#The gluster poller
from repquota import RepQuota
from repcephosdu import RepCephOSdu

# Here are the email package modules we'll need
import smtplib
from email.mime.text import MIMEText
from email.mime.message import MIMEMessage
from email.mime.base  import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.encoders import encode_base64
import mimetypes

from salesforceocc import SalesForceOCC

import numpy


class UserUsageStat:
    """This is an object to store a users info"""
    def __init__(self, username, tenant=None, corehrs=0, du=0,obj_du=0,blk_du=0):
        self.username = username
        self.tenant = tenant
        self.corehrs = corehrs
        self.du = du
        self.obj_du = obj_du 
        self.blk_du = blk_du


class NovaUserReporting:
    def __init__(self, config_file,debug=None, storage_type=None):
        """INit the function"""
        #Dict of settings
        self.settings = {}
        self.cloud_users = {}
        self.debug = None

        #Stores the csv
        self.csv = []

        #read in settings
        self.config_file = config_file
        Config = ConfigParser.ConfigParser()
        Config.read(self.config_file)
        sections = ['general','novauserreporting','salesforceocc']
        for section in sections:
            options = Config.options(section)
            for option in options:
                try:
                    self.settings[option] = Config.get(section, option)
                except:
                    sys.stderr.write("exception on [%s] %s!" % section, option)

        #Get the ENV overrides
        self.override_nova_creds_with_env('OS_USERNAME')
        self.override_nova_creds_with_env('OS_PASSWORD')
        self.override_nova_creds_with_env('OS_AUTH_URL')
        self.override_nova_creds_with_env('OS_TENANT_NAME')


    def override_nova_creds_with_env(self, keyname):
       #Get the nova auth stuff if not already
        try:
            self.settings[keyname]
        except KeyError:
            try:
                self.settings[keyname] = os.environ.get(keyname)
            except KeyError:
                sys.stderr.write("ERROR: KeyError on pulling ENV\n")
                sys.exit(1)

    def set_time_range(self, start_date=None, end_date=None):
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
                    datetime.strptime(start_date, self.settings['timeformat']
                    )
                )
            )
        except ValueError:
            sys.stderr.write("ERROR: Start time not in proper format '%s'\n"
                % (self.settings['timeformat']))
            sys.exit(1)

        try:
            self.end_time = localize_timezone.localize(
                datetime.strptime(end_date, self.settings['timeformat'])
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

    def db_connect(self, db):
        try:
            dsn = "mysql://%s:%s@%s/%s" % (self.settings['db_user'],
                self.settings['db_passwd'], self.settings['db_server'], db)
            engine = create_engine(dsn)
            return engine.connect()

        except SQLAlchemyError, e:
            sys.stderr.write("Error %s" % (e))
            sys.exit(1)

    def get_corehrs(self, user_id=None, tenant_id=None):
        """Fetch the core hrs for a uuid, can be by tenant or user"""
        corehrs_total = 0
        query_base = """SELECT
                        created_at,
                        updated_at,
                        deleted_at,
                        deleted,
                        id,
                        user_id,
                        project_id,
                        memory_mb,
                        vcpus,
                        scheduled_at,
                        launched_at,
                        terminated_at,
                        instance_type_id,
                        uuid,
                        task_state

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
			or
			( launched_at <= '%s' and terminated_at >= '%s' )
                    )
                    """ % (self.start_time.strftime(self.settings['timeformat']), self.cieling_time.strftime(self.settings['timeformat']),
                            self.start_time.strftime(self.settings['timeformat']), self.cieling_time.strftime(self.settings['timeformat']),
                            self.start_time.strftime(self.settings['timeformat']), self.cieling_time.strftime(self.settings['timeformat']),
                            self.start_time.strftime(self.settings['timeformat']), self.cieling_time.strftime(self.settings['timeformat']),
                            self.start_time.strftime(self.settings['timeformat']), self.cieling_time.strftime(self.settings['timeformat'])
                        )

        if user_id is None and tenant_id is not None:
            query = query_base + "and %s = '%s'" % ('project_id', tenant_id)
        elif user_id is not None and tenant_id is None:
            query = query_base + "and %s = '%s'" % ('user_id', user_id)
        elif user_id is not None and tenant_id is not None:
            query = query_base + "and ( %s = '%s' and %s = '%s')" % ('project_id', tenant_id, 'user_id', user_id)
        else:
            sys.stderr.write("ERROR: How did you get here?\n")
            sys.exit(1)

        try:
            conn = self.db_connect(self.settings['novadb'])
            s = text(query)
            results = conn.execute(s)
        except SQLAlchemyError as e:
            sys.stderr.write("ERROR-NUR: Erroring querying the databases: %s\n" % (e) )
            sys.exit(1)


        #Break out the values we need
        for row in results:

            try:
                created_at = row[0].replace(tzinfo=timezone('UTC'))
            except AttributeError:
                created_at = None

            try:
                updated_at = row[1].replace(tzinfo=timezone('UTC'))
            except AttributeError:
                updated_at = None

            try:
                deleted_at = row[2].replace(tzinfo=timezone('UTC'))
            except AttributeError:
                deleted_at = None

            deleted = int(row[3])
            user_id = row[5]
            project_id = row[6]
            vcpus = int(row[8])
            try:
                scheduled_at = row[9].replace(tzinfo=timezone('UTC'))
            except AttributeError:
                scheduled_at = None
            try:
                launched_at = row[10].replace(tzinfo=timezone('UTC'))
            except AttributeError:
                launched_at = None
            try:
                terminated_at = row[11].replace(tzinfo=timezone('UTC'))
            except AttributeError:
                terminated_at = None
            instance_type_id = int(row[12])
            uuid = row[13]
            task_state = row[14]

            #Edge case for when VM started
            if launched_at is None:
                if scheduled_at is not None:
                    better_launched_at = scheduled_at
                else:
                    better_launched_at = created_at
            else:
                better_launched_at = launched_at

            #Find the term time for a vm
            if deleted != 0 and terminated_at is not None:
                better_terminated_at = terminated_at
            elif deleted != 0 and deleted_at is not None:
                better_terminated_at = deleted_at
            elif deleted != 0 and updated_at is not None:
                better_terminated_at = updated_at
            elif deleted != 0 and deleted_at is None:
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
                corehrs = (time_up.total_seconds() / 3600) * vcpus
                corehrs_total += corehrs

        conn.close()
        return int(corehrs_total)


    def get_cinder_du_percentile(self, user_id=None, tenant_id=None, percentile=95):
        """Fetch the core hrs for a uuid, can be by tenant or user"""
        #An array of the storage, we will take a start and stop time period and iterate over
        dus = []

        #The time period that we care about
        start_time=self.start_time
        stop_time=self.cieling_time
        start_time_str=self.start_time.strftime(self.settings['timeformat'])
        stop_time_str=self.cieling_time.strftime(self.settings['timeformat'])

        try:
            conn = self.db_connect(self.settings['cinderdb'])

        except SQLAlchemyError as e:
            sys.stderr.write("ERROR-NUR: Erroring querying the databases: %s\n" % (e) )
            sys.exit(1)

        #Loop through time period and 
        while start_time < stop_time:
            temp_du = 0
            query_base = """ SELECT size
                        from cinder.volumes where status != 'error' and
                        ( 
                            ( launched_at >= '%s' and launched_at <= '%s' )
                            or
                            ( terminated_at >= '%s' and terminated_at <= '%s' )
                            or
                            ( deleted_at >= '%s' and deleted_at <= '%s' )
                            or
                            ( terminated_at is NULL and deleted_at is NULL and deleted = '0' and launched_at <= '%s')
                            or
                            ( launched_at <= '%s' and terminated_at >= '%s' )
                        ) """ % (
                                start_time_str, stop_time_str,
                                start_time_str, stop_time_str,
                                start_time_str, stop_time_str,
                                stop_time_str,
                                start_time_str, stop_time_str,
                            )



    
            if user_id is None and tenant_id is not None:
                query = query_base + "and %s = '%s'" % ('project_id', tenant_id)
            elif user_id is not None and tenant_id is None:
                query = query_base + "and %s = '%s'" % ('user_id', user_id)
            elif user_id is not None and tenant_id is not None:
                query = query_base + "and ( %s = '%s' and %s = '%s')" % ('project_id', tenant_id, 'user_id', user_id)
            else:
                sys.stderr.write("ERROR: How did you get here?\n")
                sys.exit(1)
    
            try:
                s = text(query)
                results = conn.execute(s)
            except SQLAlchemyError as e:
                sys.stderr.write("ERROR-NUR: Erroring querying the databases: %s\n" % (e) )
                sys.exit(1)
    
            #sum up the sizes for a given period
            for row in results:
                if row[0] :
                    temp_du += row[0]

            #append the dus to array for latter processing
            dus.append(temp_du)
            start_time += timedelta(seconds=int(self.settings['du_period']))

   
        conn.close()

        if dus:
            du = numpy.percentile(a=dus,q=float(percentile))
        else:
            du = 0

        #return du
        #Cinder operates in base10 GB, we need Base 2 GiB
        return int( math.ceil( du*(2**30)/(1000**3)) )


    def get_client(self, client_type, username=None, password=None, tenant=None, url=None):
        """ Get the client object for python*-client """
        if username is None:
            username = self.settings['OS_USERNAME']
        if password is None:
            password = self.settings['OS_PASSWORD']
        if tenant is None:
            tenant = self.settings['OS_TENANT_NAME']
        if url is None:
            url = self.settings['OS_AUTH_URL']

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

    def load_user_list(self, username=None, password=None, tenant=None, url=None):
        """Get list of tenants"""
        kc = self.get_client(client_type=kc_client)
        self.tenants = kc.tenants.list()
        self.users = kc.users.list()

    def load_flavor_list(self, username=None, password=None, tenant=None, url=None):
        """Get list of the flavors"""
        nc = self.get_client(client_type=nc_client)
        flavors = nc.flavors.list()

    def get_du(self, user_name=None, tenant_name=None, user_id=None, tenant_id=None, start_date=None, end_date=None,storage_type=None):
        """AVG the gluster.$cloud table for a path corresponding to users homedir...hopefully"""

        du = None

        if storage_type == "repquota":
            #Reports in KiboBytes
            unit_power = 20 # Divide result by Power of 2 to convert to GiB

            g = RepQuota(config_file=self.config_file)
            du = g.get_percentile_du(
                        start_date=start_date.strftime(self.settings['timeformat']),
                        end_date=end_date.strftime(self.settings['timeformat']),
                        path=user_name, 
                        percentile=self.settings['du_percentile']
                )

        elif storage_type == 'object':
            # Reports in Bytes
            unit_power = 30 # Divide result by Power of 2 to convert to GiB

            g = RepCephOSdu(debug=self.debug)
            du = g.get_percentile_du(
                        start_date=start_date.strftime(self.settings['timeformat']),
                        end_date=end_date.strftime(self.settings['timeformat']),
                        path=user_name, 
                        percentile=self.settings['du_percentile']
                )

        elif storage_type == 'block':
            # Reports in ????
            unit_power = 0 # Divide result by Power of 2 to convert to GB
            du = self.get_cinder_du_percentile(
                tenant_id=tenant_id, 
                user_id=user_id,
                percentile=self.settings['du_percentile'] )

        else:
            sys.stderr.write("ERROR: How did you get here: %s\n" % (storage_type)) 
            pass

        if du is None:
            return None
        else:
            #Round to GB and return
            return int(du / 2 ** unit_power)

    def load_stats(self, start_date=None, end_date=None):
        #Set the time range to pull reports for
        self.set_time_range(start_date=start_date, end_date=end_date)

        #Load List of Tenants and Users
        self.load_user_list()

        #Loop through tenants
        for tenant in self.tenants:
            if tenant.name in self.settings['ignore_tenants'].split(','):
                continue

            #Find users in a tenant
            tenant_users = tenant.list_users()
            for user in tenant_users:
                corehrs = self.get_corehrs(user_id=user.id, tenant_id=tenant.id)
                #Adjust paths for real tenants...
                du = 0
                obj_du = 0
                blk_du = 0
                for storage_type in self.settings['storage_types'].split(','):
                    temp_du = self.get_du(
                        user_name=str(user.name),
                        tenant_name=str(tenant.name),
                        user_id = str(user.id),
                        tenant_id = str(tenant.id),
                        start_date=self.start_time, 
                        end_date=self.cieling_time,
                        storage_type=storage_type
                    )
                    if storage_type == 'object':
                        obj_du = temp_du
                    elif storage_type == 'block':
                        blk_du = temp_du
                    else:
                        du += temp_du
                if self.debug:
                    sys.stderr.write( "Tenant: %s, USER: %s,core=%s,obj=%s,blk=%s,type=%s\n" %(tenant.name,user.name, corehrs,obj_du, blk_du, storage_type))
                self.cloud_users.setdefault(user.name, []).append( UserUsageStat(username=user.name, tenant=tenant.name, corehrs=corehrs, du=du, obj_du=obj_du, blk_du=blk_du) )


    def gen_csv(self):
        self.csv = []
        self.csv.extend(["User, Core Hours (H), Misc Disk Usage (GiB), Object Storage (GiB), Block Storage (GiB)"])
        for cloud_user, stats in self.cloud_users.items():
            #self.csv.extend(["%s,%s,%s" % (cloud_user, stats.corehrs, stats.du)])
            #This is stupid but until we have better handling on multi tenant users, its kludged to work

            du = stats[0].du
            obj_du = stats[0].obj_du
            blk_du = stats[0].blk_du
            corehrs = 0
            for per_tenant_corehrs in stats:
                corehrs += per_tenant_corehrs.corehrs
            self.csv.extend(["%s,%s,%s,%s,%s" % (cloud_user, corehrs, du,obj_du, blk_du)])


    def print_csv(self):
        #print "Tenant, User, Core Hours (H), Disk Usage (GiB)"
        for line in self.csv:
            print "%s" % (line)

    def get_csv(self):
        return self.csv

    def email_csv(self, sendto=None, recvfrom=None, subject=None):
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
            msg['From'] = self.settings['recvfrom']
        else:
            msg['From'] = recvfrom

        if subject is None:
            msg['Subject'] = "%s usage report for %s to %s" % (self.settings['cloud'], self.start_time, self.end_time)
        else:
            msg['Subject'] = subject

        # now attach the file
        mformat, menc = mimetypes.guess_type("%s_%s-%s.csv" % (self.settings['cloud'], self.start_time, self.end_time))
        mmain, msub = mformat.split('/')
        fileMsg = MIMEBase(mmain, msub)
        attachment = "\n".join(self.get_csv())  # .encode('UTF-8')
        fileMsg.set_payload(attachment)
        encode_base64(fileMsg)
        fileMsg.add_header('Content-Disposition', "attachment;filename=%s_%s-%s.csv" % (self.settings['cloud'], self.start_time, self.end_time))
        msg.attach(fileMsg)

        #Now send it on its way
        s = smtplib.SMTP(smtpserver)
        s.sendmail(msg['From'], msg.get_all('TO'), msg.as_string())
        s.quit()

    def push_to_sf(self):
        """ Take list of users on cloud, push as many as you can to SF """
        sf = SalesForceOCC()
        sf.login(username=self.settings['sfusername'], password=self.settings['sfpassword'], url=self.settings['sfurl'])
        sf.load_contacts_from_campaign(campaign_name=self.settings['campaign'])
        for cloud_username, stats in self.cloud_users.items():
            contact_id = None
            case_id = None


            #This is stupid but until we have better handling on multi tenant users, its kludged to work
            du = stats[0].du
            blk_du = stats[0].blk_du
            obj_du = stats[0].obj_du
            corehrs = 0
            for per_tenant_corehrs in stats:
                corehrs += per_tenant_corehrs.corehrs
            
            # Assume the username on cloud and SF match
            # If not we can try the slow way and query SF for a match
            try:
                contact_id = sf.contacts[cloud_username]['id']
            except KeyError:
                try:
                    contact_id = sf.get_contact_id_by_case_username(case=self.settings['case'], cloud_username=cloud_username)
                except KeyError:
                    contact_id = None

            # If we found a contact_id then we can proceed
            if contact_id is not None:
                # We prefer having a case, but can get away witout it
                try:
                    case_id = sf.get_case_id(case=self.settings['case'], contact_id=contact_id)
                except KeyError:
                    case_id = None
            
                if ( corehrs is None or corehrs == 0 ) and ( du is None or du == 0):
                    sys.stderr.write("INFO: User %s had no billable usage\n" %(cloud_username) )
                else:
                    # Write to SalesForce
                    try:
                        saver_result = sf.create_invoice_task(
                            campaign=self.settings['campaign'], 
                            contact_id=contact_id,
                            case_id=case_id, 
                            corehrs=corehrs, 
                            du=du,
                            blk_du=blk_du,
                            obj_du=obj_du,
                            start_date=self.start_time, 
                            end_date=self.end_time)
                        if case_id is None:
                            sys.stderr.write("WARN: Cannot find the case number for users %s. Task still created with id %s.\n" % (cloud_username, saver_result))
                    except KeyError:
                        # I do not know if its even possible to get here...
                        sys.stderr.write("ERROR: KeyError: Cannot find user '%s' in campaign in salesforce\n" % (cloud_username))
            else:
                sys.stderr.write("ERROR: Cannot find user '%s' in campaign in salesforce\n" % (cloud_username))
                


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
    delta2 = timedelta(days=6 - delta_days, weeks=delta_weeks)
    weekend = d + delta2
    return weekbeg, weekend
