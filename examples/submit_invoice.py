import sfconfig
import datetime

from salesforceocc import SalesForceOCC
if __name__ == "__main__":
    sf = SalesForceOCC()
    sf.login(username=sfconfig.USERNAME, password=sfconfig.PASSWORD, testing=True)
    sf.load_contacts_from_campaign(campaign=sfconfig.CLOUD)
    case_id = sf.get_case_id(campaign=sfconfig.CLOUD,contact_id=sf.contacts['rpowell1']['id'])
    saver_result = sf.create_invoice_task(campaign=sfconfig.CLOUD, contact_id=sf.contacts['rpowell1']['id'], case_id=case_id, corehrs="999", du="1234", start_date=datetime.datetime(2013,1,1) , end_date=datetime.datetime(2013,1,31))
    print saver_result
