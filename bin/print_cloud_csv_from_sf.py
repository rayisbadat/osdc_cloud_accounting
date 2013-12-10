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


    sfocc.login(username=settings['sfusername'], password=settings['sfpassword'])
    contacts = sfocc.get_contacts_from_campaign(campaign_name=settings['cloud'],  statuses=["Approved User", "Application Pending"])
    #contact_statuses = sfocc.get_campaign_members_status(campaign_name=settings['cloud'])
    #pprint.pprint(contact_statuses)
    sfocc.print_approved_users_csv(campaign_name=settings['cloud'], contacts=contacts)
