#!/usr/bin/env python
import beatbox
import sys
import pprint


class SalesForceOCC:
    def __init__(self):
        """INit the function"""
        self.svc = beatbox.Client()
        self.partnerNS = beatbox._tPartnerNS
        self.objectNS = beatbox._tSObjectNS
        self.soapNS = beatbox._tSoapNS
        self.contacts = {}
        self.contact_ids = []

    def create_invoice_task(self, campaign, contact_id, case_id, corehrs, du, start_date, end_date):
        """ Create the task/invoice in salesforce """

        """
            WhatId, Case Id
            RecordTypeId, Unknown
            Whoid, Contact Id
            Subject, "$CLOUD Invoice $MONTH.$YEAR"
            Status, "Completed"
        """
        t = {
                'type': 'Task',
                'WhatId': case_id,
                'WhoId': contact_id,
                'Subject': "%s Invoice %s" % (campaign, start_date.strftime('%m.%Y')),
                'ActivityDate': start_date,
                'Status': 'Completed',
                'Priority': 'Normal',
                'Core_Hour_Use__c': corehrs,
                'Storage_Use__c': du,
                'Usage_Start_Date__c': start_date,
                'Usage_End_Date__c': end_date,
        }

        ur = self.svc.upsert('Id', t)
        if str(ur[self.partnerNS.success]) == "true":
            return str(ur[self.partnerNS.id])
        else:
            return None

    def get_case_id(self, campaign, contact_id):
        """ Given a ContactId and a Campaign find the case"""
        query = """SELECT CaseNumber, Id 
                FROM Case 
                WHERE ContactId ='%s' and ResourceName__c='%s'
                """ % (contact_id, campaign)

        cases = self.svc.query(query)

        for case in cases:
            try:
                return str(case[self.objectNS.Id])
            except KeyError:
                pass

    def get_contact_id_by_case_username(self, campaign, cloud_username):
        """Pull the username assosiated with the cloud/campaign. 
            Used as last resort to find the edge case where system
            and salesforce do not match"""

        query = """SELECT ContactId 
                FROM Case 
                WHERE 
                ResourceName__c='%s' 
                and 
                Server_Username_Associated_with_Invoice__c='%s'
                """ % (campaign, cloud_username)

        users = self.svc.query(query)
        for user in users:
            try:
                return str(user[self.objectNS.ContactId])
            except KeyError:
                pass



    def load_contactids_from_campaign(self, campaign_name, statuses=["Approved User"]):
        """ Load the MemberIds of the people in campaign """
        self.contact_ids = self.get_contactids_from_campaign(campaign_name=campaign_name, statuses=statuses)
        
    def get_contactids_from_campaign(self, campaign_name, statuses=["Approved User"]):
        """ Get the MemberIds of the people in campaign """
        contact_ids = []

        campaign_id = self.get_campaignid(campaign_name=campaign_name)

        #Get the list of campaign Members CampaignMember.ContactId=Contact.Id
      
        for status in statuses:
            query_contacts = """SELECT ContactId, Status 
                FROM CampaignMember 
                WHERE campaignId ='%s' and status = '%s'
                """ % (campaign_id, status)
            contacts = self.svc.query(query_contacts)
    
            #Get the account mappings
            for contact in contacts:
                try:
                    contact_ids.append(str(contact[self.objectNS.ContactId]))
                except KeyError:
                    pass
    
        return contact_ids


    def get_campaignid(self, campaign_name=None):
        """ Get the CampaignID from SF """
        query_campaigns = """SELECT Id, Name
            FROM Campaign
            WHERE Name='%s'
            """ % (campaign_name)

        campaigns = self.svc.query(query_campaigns)
        campaign_id = str(campaigns[self.partnerNS.records:][0][self.objectNS.Id])
        return campaign_id
        

    def load_contacts_from_campaign(self, campaign_name, statuses=["Approved User"]):
        """ Create a listing of what we need for each user in a campaign """
        self.contacts = self.get_contacts_from_campaign(campaign_name=campaign_name, statuses=statuses)


    def get_contacts_from_campaign(self, campaign_name, statuses=["Approved User"]):
        """ Create a listing of what we need for each user in a campaign """
        #Get the ContactIds for the people in this campaign. We map cloud to campaign
        contact_ids = self.get_contactids_from_campaign(campaign_name, statuses=statuses)

        #We need to know what the correct objectNS for the correct campaign is
        userNS = self.return_userNS(campaign_name)

        #Get the accounts
        accounts = self.get_accounts()

        #Fields to pull
        fields = "Id, FirstName, AccountId, \
            LastName,Department,Principal_Investigator__c,Project_Name_Description__c, \
            PDC_eRA_Commons__c, OSDC_Username__c, Bionimbus_WEB_Username__c, Email, Name, OCC_Y_Server_Username__c, Phone, Authentication_Method__c"
        contacts = self.svc.retrieve(fields, "Contact", contact_ids)
        contacts_dict = {}
        contact_statuses = self.get_campaign_members_status(campaign_name=campaign_name)
        contact_quotas_core = self.get_campaign_members_quotas(campaign_name=campaign_name,quota='core')
        contact_quotas_storage = self.get_campaign_members_quotas(campaign_name=campaign_name,quota='storage')

        #Loop through and dict the results for latter processing
        for contact in contacts:
            try:
                contacts_dict[str(contact[userNS])] = {
                    'FirstName': str(contact[self.objectNS.FirstName]),
                    'Account': str(accounts[str(contact[self.objectNS.AccountId])]),
                    'LastName': str(contact[self.objectNS.LastName]),
                    'Department': str(contact[self.objectNS.Department]),
                    'PI': str(contact[self.objectNS.Principal_Investigator__c]),
                    'Project': str(contact[self.objectNS.Project_Name_Description__c]),
                    'username': str(contact[userNS]),
                    'Name': str(contact[self.objectNS.Name]),
                    'Email': str(contact[self.objectNS.Email]),
                    'Phone': str(contact[self.objectNS.Phone]),
                    'id':  str(contact[self.objectNS.Id]),
                    'core_quota': str(contact_quotas_core[str(contact[self.objectNS.Id])]),
                    'storage_quota': str(contact_quotas_storage[str(contact[self.objectNS.Id])]),
                    'status': contact_statuses[str(contact[self.objectNS.Id])],
                    'Authentication_Method': str(contact[self.objectNS.Authentication_Method__c])
                }
            except KeyError as e:
                sys.stderr.write("ERROR: KeyError trying to pull user info from campagin list.  Do we only have 1 user in campagin ?\n")

        return contacts_dict


    def get_campaign_members_status(self, campaign_name=None, campaign_id=None):
        """ Get the Campaign member status for all users in Campaign """

        contact_statuses = {}

        if campaign_id is None and campaign_name is not None:
            campaign_id = self.get_campaignid(campaign_name=campaign_name)
        
        query_campaign_member_status = """SELECT CampaignId, ContactId, Status
            FROM CampaignMember
            WHERE CampaignId = '%s'
            """ % (campaign_id)

        campaign_member_statuses = self.svc.query(query_campaign_member_status)
        for campaign_member_status in campaign_member_statuses:
            try:
                contact_id = str(campaign_member_status[self.objectNS.ContactId])
                contact_status = str(campaign_member_status[self.objectNS.Status])
                contact_statuses[contact_id] = contact_status
            except KeyError:
                pass

        return contact_statuses

    def get_campaign_members_quotas(self, campaign_name=None, campaign_id=None, quota='core'):
        """ Get the Campaign member quotas for all users in Campaign """

        contacts_quota = {}

        if campaign_id is None and campaign_name is not None:
            campaign_id = self.get_campaignid(campaign_name=campaign_name)

        if quota == 'core':
            query_campaign_members_quota = """SELECT ContactId, Core_Quota__c
                FROM CampaignMember
                WHERE CampaignId = '%s'
                """ % (campaign_id)
            quota_indexer = self.objectNS.Core_Quota__c
        elif quota == 'storage':
            query_campaign_members_quota = """SELECT ContactId, Storage_Quota__c
                FROM CampaignMember
                WHERE CampaignId = '%s'
                """ % (campaign_id)
            quota_indexer = self.objectNS.Storage_Quota__c
        else:
            raise KeyError("No core or storage quota provided")

        campaign_members_quota = self.svc.query(query_campaign_members_quota)

        for campaign_member_quota in campaign_members_quota:
            try:
                contact_id = str(campaign_member_quota[self.objectNS.ContactId])
                contact_quota = str(campaign_member_quota[quota_indexer])
                if contact_quota:
                    contacts_quota[contact_id] = int(float(contact_quota))
                else:
                    contacts_quota[contact_id] = None
            except KeyError:
                pass

        return contacts_quota
        
    def login(self, username="", password="", url="https://login.salesforce.com/services/Soap/u/28.0"):
        """Login to sales force to use their SOQL nonsense"""
        #I dont want to use .net and their shitty code explorer
        #Pull the table schema with Force.com Explorer(Beta)
        self.svc.serverUrl = url
        self.svc.login(username, password)

    def return_userNS(self, campaign_name):
        """ We need to use these xxxNS as indexes into results, this returns the correct one based on cloud name """
        if campaign_name == 'OCC Y User/Applicant Tracking':
            return self.objectNS.OCC_Y_Server_Username__c
        elif campaign_name == 'PDC':
            return self.objectNS.PDC_eRA_Commons__c
        elif campaign_name == 'Bionimbus (WEB ONLY) User/Applicant Tracking':
            return self.objectNS.Bionimbus_WEB_Username__c
        else:
            return self.objectNS.OSDC_Username__c

    def get_accounts(self):
        #Get the account mappings
        accounts_query = self.svc.query( "SELECT Id, Name FROM Account" )
        accounts_dict={}
        for value in accounts_query:
            try:
                value_id = str(value[self.objectNS.Id])
                value_name = str(value[self.objectNS.Name])
                accounts_dict[value_id]=value_name
            except KeyError:
                pass
        return accounts_dict



    def get_approved_users(self, campaign_name, contacts=None):
        """ Prints a csv of approved users in the format we use for new/disabled account processing"""
        if type(contacts) == None and self.contacts == None:
            sys.stderr.write("ERROR: KeyError trying to pull user info from campagin list.  Do we only have 1 user in campagin ?\n")
            sys.exit(1)
        elif type(contacts) == None:
            contacts=self.contacts

        return contacts



    def print_approved_users_csv(self, campaign_name, contacts=None):
        """ Prints a csv of approved users in the format we use for new/disabled account processing"""
        contacts = self.get_approved_users(campaign_name=campaign_name,contacts=contacts)
        for username, contact in contacts.items():
            try:
                print '"{}","{}","{}","{}","{}","{}","{}","{}","{}","{}","{}","{}","{}"'.format( \
                    contact['status'],
                    contact['FirstName'],
                    contact['LastName'],
                    contact['Account'],
                    contact['Department'],
                    contact['PI'],
                    contact['Project'],
                    contact['username'],
                    contact['Email'],
                    contact['Phone'],
                    campaign_name,
                    contact['core_quota'],
                    contact['storage_quota'],
                )
            except KeyError as e:
                sys.stderr.write("ERROR: KeyError trying to pull user info from campagin list.  Do we only have 1 user in campagin ?\n")



