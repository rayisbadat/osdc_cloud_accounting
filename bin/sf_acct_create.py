#!/usr/bin/env python
from salesforceocc import SalesForceOCC
import ConfigParser
import pprint

if __name__ == "__main__":
    sfocc = SalesForceOCC()
    #read in settings
    Config = ConfigParser.ConfigParser()
    Config.read(".settings")
    sections = ['general','salesforceocc']
    settings = {}
    for section in sections:
        options = Config.options(section)
        for option in options:
            try:
                settings[option] = Config.get(section, option)
            except:
                sys.stderr.write("exception on [%s] %s!" % section, option)

    #Load up a list of the users in SF that are approved for this cloud
    sfocc.login(username=settings['sfusername'], password=settings['sfpassword'])
    contacts = sfocc.get_contacts_from_campaign(campaign_name=settings['cloud'],  statuses=["Approved User", "Application Pending"])
    sfocc.print_approved_users_csv(campaign_name=settings['cloud'], contacts=contacts)
    members_list = sfocc.get_approved_users(campaign_name=settings['cloud'], contacts=contacts)

    #Loop through list of members and run the bash scripts that will create the account
    #FIXME: Most of this stuff could be moved into the python, just simpler not to
    for username,fields in members_list.items():
        pprint.pprint(username)
        pprint.pprint(fields)
    

