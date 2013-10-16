import sys
import ConfigParser
import socket
import re

#Db stuff
from sqlalchemy import create_engine, insert, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import Table, Column, Text, Float, MetaData, DateTime

#All this just to convert dates
from datetime import datetime, timedelta
from pytz import timezone
import pytz

class RepQuota:
    def __init__(self, config_file=".settings"):
        """Polls gluster for quotas and save into dict"""
        self.settings = {}
        self.repquota_regex='(\S+)\s+--\s+(\d+)'
        self.servers = []
        self.dus = {}

        #read in settings
        Config = ConfigParser.ConfigParser()
        Config.read(config_file)
        sections = ['general','repquota']
        for section in sections:
            options = Config.options(section)
            for option in options:
                try:
                    self.settings[option] = Config.get(section, option)
                except:
                    sys.stderr.write("ERROR: exception on [%s] %s!" % (section, option))

        self.now_time = datetime.now(tz=pytz.timezone('UTC'))

        self.metadata = MetaData()
        self.du_table = Table(self.settings['cloud'], self.metadata,
                Column('date', DateTime),
                Column('path', Text),
                Column('value', Float),
        )

        if self.settings['repquota_servers']:
            for server in self.settings['repquota_servers'].split(','):
                self.add_server(server=server)


    def add_server(self, server=None):
        """ Add server to the list """
        self.servers.append(server)


    def get_repquota_from_server(self, server=None, port=None):
        """ Hit xinet.d on specified server and port and reclaim the repquota """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((server, port))
        s.send("")
        all_data = s.recv(1024)
        while 1:
            data = s.recv(1024)
            if not data: 
                break
            else:
                all_data += data
        s.close()
        return all_data


    def load_quotas(self, quota_type="user"):
        """ Loop through server list and get repquotas """
        if quota_type == "user":
            port = int(self.settings['user_repquota_port'])
        elif quota_type == "group":
            port = int(self.settings['group_repquota_port'])
        else:
            sys.stderr.write("ERROR: Valid quota types are 'user' or 'group'\n")
            raise Exception

        repquotas = []
        for server in self.servers:
            try:
                repquotas.append(
                    self.get_repquota_from_server(server=server, port=port))
            except Exception as e:
                sys.stderr.write("ERROR: server %s:%s errored getting quota\n%s\n" %(server, port, e))

        for repquota in repquotas:
            for line in repquota.split("\n"):
                results = re.search(self.repquota_regex,line)
                if results:
                    try:
                        self.dus[results.group(1)] += int(results.group(2))
                    except KeyError:
                        self.dus[results.group(1)] = int(results.group(2))
                        


    def print_du(self):
        """Print the du for each path"""
        for key, value in self.dus.items():
            print "User/Group: %s Value: %s " % (key, value)

    def db_connect(self, db):
        try:
            dsn = "mysql://%s:%s@%s/%s" % (self.settings['uid'],
                self.settings['pwd'], self.settings['server'], db)
            engine = create_engine(dsn)
            return engine.connect()

        except SQLAlchemyError, e:
            print "Error %d: %s" % (e.args[0], e.args[1])

    def write_to_db(self):
        """Push it out to a file"""

        conn = self.db_connect(self.settings['quotadb'])
        insert = []
        for path, value in self.dus.items():
            insert.append({'date': self.now_time,
                'path': path,
                'value': int(value)
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
    g = RepQuota()
    g.load_quotas()
    g.print_du()
