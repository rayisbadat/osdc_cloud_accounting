#!/usr/bin/env python
from salesforceocc import SalesForceOCC
import ConfigParser
import pwd
import sys
import subprocess
import getopt
import pprint
import csv

if __name__ == "__main__":

    #Load in the CLI flags
    run = True
    printcsv = False
    nih_file = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], "", ["print", "norun", "nihfile="])
    except getopt.GetoptError:
        sys.stderr.write("ERROR: Getopt\n")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("--print"):
            printcsv = True
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

    #Load up a nih style csv of approved users.
    #user_name is the actual human name
    #login is the name we care about.
    #phsid is also important eventually
    if nih_file:
        try:
            with open(nih_file, 'r') as handle:
                reader = csv.DictReader(handle, ['user_name', 'login', 'authority', 'role', 'email', 'phone',' status', 'phsid', 'permission_set', 'created', 'updated', 'expires', 'downloader_for'])
                for row in reader:
                    nih_approved_users[row['login']] = row['phsid']
        except NameError:
            pass
        except IOError as e:
            sys.exit('file %s not found: %s' % (nih_file, e))
        except csv.Error as e:
            sys.exit('file %s, line %d: %s' % (filename, reader.line_num, e))
    

    #Loop through list of members and run the bash scripts that will create the account
    #FIXME: Most of this stuff could be moved into the python, just simpler not to
    for username,fields in members_list.items():
        #Nih style changes....i am doing this wrong
        if nih_file:
            if fields['eRA_Commons_username']  in nih_approved_users:
                username = fields['eRA_Commons_username']
            else:
                continue
            
        try:
            user_exists = pwd.getpwnam(username)
        except:
            if username:
                if fields['Authentication_Method'] == 'OpenID':
                    method = 'openid'
                else:
                    method = 'shibboleth'
                
                #If we have an identifier use that, otherwise fallback to email
                #This if proves that i Suck
                if fields['login_identifier'] == 'None' or fields['login_identifier'] == None or not fields['login_identifier']:
                    login_identifier = fields['Email']
                else:
                    login_identifier = fields['login_identifier']

                
                #I am bad at the None checking and convert it to a string at one point
                #convert none to default
                if fields['core_quota'] == 'None' or fields['core_quota'] == None:
                    fields['core_quota'] = settings['general']['core_quota']
                if fields['storage_quota'] == 'None' or fields['storage_quota'] == None:
                    fields['storage_quota'] = settings['general']['storage_quota']

                #Assemble command
                print "Creating new user:  %s" % username
                cmd = [
                    '/usr/local/sbin/create-user.sh',
                    fields['Name'],
                    fields['username'],
                    login_identifier,
                    method,
                    settings['tukey']['cloud'],
                    fields['core_quota'],
                    fields['storage_quota'] + 'TB',
                ]
                try:
                    if printcsv:
                        pprint.pprint(cmd)
                        pprint.pprint(fields)
                    if run:
                        pass
                        result = subprocess.check_call( cmd )
                except subprocess.CalledProcessError, e:
                    sys.stderr.write("Error creating  new user:  %s\n" % username )
                    sys.stderr.write("%s\n" % e.output)
                

