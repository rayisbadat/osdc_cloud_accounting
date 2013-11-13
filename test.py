from salesforceocc import SalesForceOCC
import os
import sys
import pprint
import ConfigParser


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
    #contact_ids = sfocc.get_contactids_from_campaign(campaign_name=settings['cloud'], statuses=["Approved User", "Application Pending"])
    contacts = sfocc.get_contacts_from_campaign(campaign_name=settings['cloud'],  statuses=["Approved User", "Application Pending"])
    sfocc.print_approved_users_csv(campaign_name=settings['cloud'], contacts=contacts)
