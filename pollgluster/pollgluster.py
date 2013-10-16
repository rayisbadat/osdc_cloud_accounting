from subprocess import check_output, call

from sqlalchemy import create_engine, insert, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import Table, Column, Text, Float, MetaData, DateTime

import sys

import ConfigParser

#All this just to convert dates
from datetime import datetime, timedelta
from pytz import timezone
import pytz

from unitconversion import UnitConversion


class PollGluster:
    def __init__(self, vol_name="USER-HOME", config_file=".settings"):
        """Polls gluster for quotas and save into dict"""
        self.settings = {}

        #read in settings
        Config = ConfigParser.ConfigParser()
        Config.read(config_file)
        sections = ['general','pollgluster']
        for section in sections:
            options = Config.options(section)
            for option in options:
                try:
                    self.settings[option] = Config.get(section, option)
                except:
                    print "exception on [%s] %s!" % (section, option)

        self.gluster_cmd = ["/usr/sbin/gluster", "volume", "quota",
            vol_name, "list"]
        self.now_time = datetime.now(tz=pytz.timezone('UTC'))
        self.dus = {}
        self.metadata = MetaData()
        self.du_table = Table(self.settings['cloud'], self.metadata,
                Column('date', DateTime),
                Column('path', Text),
                Column('value', Float),
        )

    def get_gluster_output(self):
        try:
            raw_output = check_output(self.gluster_cmd)

        except:
            sys.stderr.write("ERROR:Gluster Call Failed\n")
            sys.exit(1)

        #Skip header and then save lines
        lines = raw_output.split("\n")
        for line in lines[2:]:
            entry = line.split()
            if entry:
                try:
                    self.dus[entry[0]] = entry[2]
                except IndexError:
                    sys.stderr.write("ERROR: IndexError on %s\n" % (entry))
                    pass

    def print_du(self):
        """Print the du for each path"""
        for key, value in self.dus.items():
            print "Path: %s Value: %s " % (key, value)

    def db_connect(self, db):
        try:
            dsn = "mysql://%s:%s@%s/%s" % (self.settings['db_user'],
                self.settings['pwd'], self.settings['server'], db)
            engine = create_engine(dsn)
            return engine.connect()

        except SQLAlchemyError, e:
            print "Error %d: %s" % (e.args[0], e.args[1])

    def write_to_db(self):
        """Push it out to a file"""

        conn = self.db_connect(self.settings['glusterdb'])
        insert = []
        unitconverter = UnitConversion()
        for path, value in self.dus.items():
            insert.append({'date': self.now_time,
                'path': path,
                'value': unitconverter.human2bytes(value)
            })
        conn.execute(self.du_table.insert(), insert)

    def get_average_du(self, start_date=None, end_date=None, path=None):
        """ Retrieve paths """
        if start_date is  None or end_date is None:
            sys.stderr.write(
                "ERROR: Start and End Dates no specified in get_average_du")
            sys.exit(1)

        self.set_time_range(start_date=start_date, end_date=end_date)

        my_query = "SELECT AVG(value) FROM %s where ( date >= '%s' and date <= '%s' ) and path like '%s'" % (
            self.settings['cloud'],
            self.start_time.strftime(self.settings['timeformat']),
            self.cieling_time.strftime(self.settings['timeformat']),
            path)

        try:
            conn = self.db_connect(self.settings['glusterdb'])
            s = text(my_query)
            result = conn.execute(s).fetchall()
            return result[0][0]

        except SQLAlchemyError:
            sys.stderr.write("Erroring querying the databases\n")
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


if __name__ == "__main__":
    g = PollGluster()
    g.get_gluster_output()
    g.write_to_db()
