#!/usr/bin/env python
from novauserreporting import NovaUserReporting
import os
import sys
import getopt
import ConfigParser
import pprint
from datetime import datetime, timedelta, date


def weekbegend(year, week):
    """
    Calcul du premier et du dernier jour de la semaine ISO
    Used from example at http://stackoverflow.com/questions/
    396913/in-python-how-do-i-find-the-date-of-the-first-monday-of-a-given-week
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


if __name__ == "__main__":

    #some default flags
    noprint = False
    email = False
    tenant_reporting = False
    sf = False

    #Load in the CLI flags
    try:
        opts, args = getopt.getopt(sys.argv[1:], "", ["start=", "end=",
            "cloud=", "thismonth", "lastmonth", "thisweek", "lastweek", "now",
            "noprint", "email", "tenants", "sf"])
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
            end_date = (now.replace(month=now.month + 1, day=1) -
                timedelta(days=1)).strftime("%Y-%m-%d 23:59:59")
        elif opt in ("--lastmonth"):
            now = datetime.now()
            date = now.replace(day=1) - timedelta(days=1)
            start_date = date.strftime("%Y-%m-01 00:00:00")
            if date.month + 1 == 13:
                end_date = (date.replace(month=1, day=1, year=date.year+1) -
                    timedelta(days=1)).strftime("%Y-%m-%d 23:59:59")
            else:
                end_date = (date.replace(month=date.month + 1, day=1) -
                    timedelta(days=1)).strftime("%Y-%m-%d 23:59:59")
        elif opt in ("--thisweek"):
            now = datetime.now()
            year = int(now.strftime("%Y"))
            week = int(now.strftime("%U")) + 1
            weekbeg, weekend = weekbegend(year, week)
            start_date = weekbeg.strftime("%Y-%m-%d 00:00:00")
            end_date = weekend.strftime("%Y-%m-%d 23:59:59")
        elif opt in ("--lastweek"):
            now = datetime.now()
            year = int(now.strftime("%Y"))
            week = int(now.strftime("%U"))
            weekbeg, weekend = weekbegend(year, week)
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
        elif opt in ("--sf"):
            sf = True

    #initialize the clase with credentials
    nova_user_reports = NovaUserReporting("/etc/osdc_cloud_accounting/settings.py")
    nova_user_reports.load_stats(start_date=start_date, end_date=end_date)
    nova_user_reports.gen_csv()

    if noprint is False:
        nova_user_reports.print_csv()

    if email is True:
        nova_user_reports.email_csv()

    if sf is True:
        nova_user_reports.push_to_sf()
