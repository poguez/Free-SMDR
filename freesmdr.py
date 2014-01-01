#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
Free SMDR daemon
by Gabriele Tozzi <gabriele@tozzi.eu>, 2010-2011

This software starts a TCP server and listens for a SMDR stream. The received
data in then written in raw format to a log file and also to a MySQL database.

Here is the SQL to create the table:
 CREATE TABLE 'freesmdr' (
  'idfreesmdr' bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  'call_start' datetime DEFAULT NULL,
  'call_duration' time DEFAULT NULL,
  'ring_duration' time DEFAULT NULL,
  'caller' varchar(255) DEFAULT NULL,
  'direction' enum('I','O') DEFAULT NULL,
  'called_number' varchar(255) DEFAULT NULL,
  'dialled_number' varchar(255) DEFAULT NULL,
  'account' varchar(255) DEFAULT NULL,
  'is_internal' tinyint(1) DEFAULT NULL COMMENT '**BOOL**',
  'call_id' int(10) unsigned DEFAULT NULL,
  'continuation' tinyint(1) DEFAULT NULL COMMENT '**BOOL**',
  'paty1device' char(5) DEFAULT NULL,
  'party1name' varchar(255) DEFAULT NULL,
  'party2device' char(5) DEFAULT NULL,
  'party2name' varchar(255) DEFAULT NULL,
  'hold_time' time DEFAULT NULL,
  'park_time' time DEFAULT NULL,
  'authvalid' varchar(255) DEFAULT NULL,
  'authcode' varchar(255) DEFAULT NULL,
  'user_charged' varchar(255) DEFAULT NULL,
  'call_charge' varchar(255) DEFAULT NULL,
  'currency' varchar(255) DEFAULT NULL,
  'amount_change' varchar(255) DEFAULT NULL COMMENT 'Amount at last User Change',
  'call_units' varchar(255) DEFAULT NULL,
  'units_change' varchar(255) DEFAULT NULL COMMENT 'Units at last User Change',
  'cost_per_unit' varchar(255) DEFAULT NULL,
  'markup' varchar(255) DEFAULT NULL,
  PRIMARY KEY ('idfreesmdr'),
  KEY 'direction_idx' ('direction'),
  KEY 'caller_idx' ('caller')
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='Freesmdr log table';

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

'''

from SocketServer import TCPServer
from SocketServer import BaseRequestHandler
import sys, os
from optparse import OptionParser
import traceback
import re, math
#import MySQLdb
import psycopg2
import logging
import datetime
import time

# Info
NAME = 'Free SMDR'
VERSION = '0.9'

# Settings
HOST = '192.168.49.99'                     #Listen on this IP
PORT = 9000                   #Listen on this port
LOGFILE = '/var/log/freesmdr/freesmdr.log' #Where to log the received data
LOGINFO = '/var/log/freesmdr/freesmdr.info' #Debug output
#MYSQL_DB = {
#    'host': 'localhost',
#    'user': 'freesmdr',
#    'passwd': '',
#    'db': 'freesmdr',
#    'table': 'freesmdr',
#}

# Classes
class ParserError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class RecvHandler(BaseRequestHandler):

    def handle(self):
        """ Handles established connection

        self.request is the socket
        """

        global server_running
        #global MYSQL_DB
        global DB_TABLE
        DB_TABLE = 'freesmdr'
        log = logging.getLogger('req_handler')

        # Init parser
        #parser = re.compile('^(("(?:[^"]|"")*"|[^,]*)(,("(?:[^"]|"")*"|[^,]*))*)$')
        parser = re.compile(',')
        fieldlist = (
            ( "call_start", 'timestamp', '%Y/%m/%d %H:%M:%S' ),
            ( "call_duration", 'time', '%H:%M:%S' ),
            ( "ring_duration", 'timeint' ), # In seconds, max 9999
            ( "caller", 'str', 255 ),
            ( "direction", 'enum', ['I','O'] ), #Inbound, Outbound
            ( "called_number", 'str', 255 ),
            ( "dialled_number", 'str', 255 ),
            ( "account", 'str', 255 ),
            ( "is_internal", 'bool' ), #0 or 1
            ( "call_id", 'int' ), #Internal avaya call ID
            ( "continuation", 'bool' ), #Tells if there is a further record for this callID
            ( "party1device", 'str', 5 ), #(E|T|V)xxx E=Extension, T=Trunk, V=voicemail
            ( "party1name", 'str', 255 ),
            ( "party2device", 'str', 5 ), #Like above
            ( "party2name", 'str', 255 ),
            ( "hold_time", 'timeint' ), #Seconds
            ( "park_time", 'timeint' ), #Seconds
            ( "authcode", 'str', 255 ),
            ( "authvalid", 'str', 255 ), #Undocumented from here
            ( "user_charged", 'str', 255 ),
            ( "call_charge", 'str', 255 ),
            ( "currency", 'str', 255 ),
            ( "amount_change", 'str', 255 ),
            ( "call_units", 'str', 255 ),
            ( "units_change", 'str', 255 ),
            ( "cost_per_unit", 'str', 255 ),
            ( "markup", 'str', 255 ),
        );

        peerinfo = self.request.getpeername()
        log.info(u'Got connection from ' + unicode(peerinfo[0]) + ' (' + unicode(peerinfo[1]) + ')')

        #Init connection to database
        conn = psycopg2.connect("dbname=smdr user=postgres")
        #conn = MySQLdb.connect(
        #        host = MYSQL_DB['host'],
        #        user = MYSQL_DB['user'],
        #        passwd = MYSQL_DB['passwd'],
        #        db = MYSQL_DB['db'],
        #        )
        #conn.autocommit(True)

        #Receive data loop
        dbuffer = ""
        while server_running:
            data = self.request.recv(1024)
            if not data:
                break

            # Append data to LOGFILE
            lgf = open(LOGFILE, 'ab')
            lgf.write(data)
            lgf.close()

            # Process data
            line = data.strip(" \n\r\t")
            vals = parser.split(line)
            if len(vals) >= len(fieldlist):
                # Received a good line
                # Build a dictionary
                dictv = {}
                i = 0
                try:
                    for v in fieldlist:
                        if v[1] == 'timestamp':
                            dictv[v[0]] = datetime.datetime.strptime(vals[i], v[2])
                        elif v[1] == 'time':
                            dictv[v[0]] = datetime.datetime.strptime(vals[i], v[2]).time()
                        elif v[1] == 'timeint':
                            z = int(vals[i])
                            #h = int(math.floor( z / ( 60 ** 2 ) ))
                            #m = int(math.floor( ( z - ( h * 60 ** 2 ) ) / 60 ** 1 ))
                            #s = z - ( h * 60 ** 2 ) - ( m * 60 ** 1 )
                            dictv[v[0]] = datetime.timedelta(seconds=z)
                        elif v[1] == 'int':
                            dictv[v[0]] = int(vals[i])
                        elif v[1] == 'str':
                            if len(vals[i]) > v[2]:
                                raise ParserError(v[0] + ': String too long')
                            dictv[v[0]] = str(vals[i])
                        elif v[1] == 'bool':
                            if vals[i] != '0' and vals[i] != '1':
                                raise ParserError(v[0] + ': Unvalid boolean')
                            dictv[v[0]] = bool(vals[i])
                        elif v[1] == 'enum':
                            if not vals[i] in v[2]:
                                raise ParserError(v[0] + ': Value out of range')
                            dictv[v[0]] = str(vals[i])
                        else:
                            raise ParserError(v[0] + ': Unknown field type ' + v[1])
                        i += 1

                except Exception, e:
                    # Unable to parse line
                    log.error(u"Parse error on line (" + str(v[0]) +"  "+ str(vals[i]) + "): got exception " + unicode(e) + " (" + str(line) + ")")

                else:
                    # Line parsed correctly
                    log.debug(u"Correctly persed 1 line: " + unicode(dictv))

                    #Prepare dictv for query
                    #map(lambda v: MySQLdb.string_literal(v), dictv)
                    #dictv['table'] = MYSQL_DB['table']
                    map(lambda v: v, dictv)
                    dictv['table'] = DB_TABLE

                    # Put the data into the DB
                    cur = conn.cursor()
                    q = """
                        INSERT INTO %(table)s (call_start,call_duration,ring_duration, caller,direction,called_number,dialled_number,account,is_internal,call_id,continuation,party1device,party1name,party2device,party2name,hold_time,park_time,authvalid,authcode,user_charged,call_charge,currency,amount_change,call_units,units_change,cost_per_unit,markup) VALUES ('%(call_start)s','%(call_duration)s','%(ring_duration)s','%(caller)s','%(direction)s','%(called_number)s','%(dialled_number)s','%(account)s','%(is_internal)d','%(call_id)d','%(continuation)d','%(party1device)s','%(party1name)s','%(party2device)s','%(party2name)s','%(hold_time)s','%(park_time)s','%(authvalid)s','%(authcode)s','%(user_charged)s','%(call_charge)s','%(currency)s','%(amount_change)s','%(call_units)s','%(units_change)s','%(cost_per_unit)s','%(markup)s');
                    """ % dictv
                    log.debug(u"Query: " + unicode(q))
                    print cur.execute(q)
                    print conn.commit()
                    print cur.close()

                    #cursor = conn.cursor()
                    #q = """
                    #    INSERT INTO '%(table)s' SET
                    #        'call_start' = '%(call_start)s',
                    #        'call_duration' = '%(call_duration)s',
                    #        'ring_duration' = '%(ring_duration)s',
                    #        'caller' = '%(caller)s',
                    #        'direction' = '%(direction)s',
                    #        'called_number' = '%(called_number)s',
                    #        'dialled_number' = '%(dialled_number)s',
                    #        'account' = '%(account)s',
                    #        'is_internal' = %(is_internal)d,
                    #        'call_id' = %(call_id)d,
                    #        'continuation' = %(continuation)d,
                    #        'paty1device' = '%(party1device)s',
                    #        'party1name' = '%(party1name)s',
                    #        'party2device' = '%(party2device)s',
                    #        'party2name' = '%(party2name)s',
                    #        'hold_time' = '%(hold_time)s',
                    #        'park_time' = '%(park_time)s',
                    #        'authvalid' = '%(authvalid)s',
                    #        'authcode' = '%(authcode)s',
                    #        'user_charged' = '%(user_charged)s',
                    #        'call_charge' = '%(call_charge)s',
                    #        'currency' = '%(currency)s',
                    #        'amount_change' = '%(amount_change)s',
                    #        'call_units' = '%(call_units)s',
                    #        'units_change' = '%(units_change)s',
                    #        'cost_per_unit' = '%(cost_per_unit)s',
                    #        'markup' = '%(markup)s';
                    #""" % dictv
                    #log.debug(u"Query: " + unicode(q))
                    #cursor.execute(q)
                    #cursor.close()

            else:
                log.error(u"Parse error on line (len " + str(len(vals)) + " vs " + str(len(fieldlist)) + "): " + unicode(line))


        # Connection terminated
        log.info(unicode(peerinfo[0]) + ' (' + unicode(peerinfo[1]) + ') disconnected')

# Parse command line
usage = "%prog [options] <config_file>"
parser = OptionParser(usage=usage, version=NAME + ' ' + VERSION)
parser.add_option("-f", "--foreground", dest="foreground",
        help="Don't daemonize", action="store_true")

(options, args) = parser.parse_args()

# Fork & go to background
if not options.foreground:
    pid = os.fork()
else:
    pid = 0
if pid == 0:
    # 1st child
    if not options.foreground:
        os.setsid()
        pid = os.fork()
    if pid == 0:
        # 2nd child
        # Set up file logging
        logging.basicConfig(
                level = logging.DEBUG,
                format = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                datefmt = '%Y-%m-%d %H:%M:%S',
                filename = LOGINFO,
                filemode = 'a'
                )

        if options.foreground:
            # Set up console logging
            console = logging.StreamHandler()
            console.setLevel(logging.INFO)
            formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
            console.setFormatter(formatter)
            logging.getLogger('').addHandler(console)

        # Create logger
        log = logging.getLogger()

        # Start server
        server_running = True
        server = TCPServer((HOST, PORT), RecvHandler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            log.info("^C detected, exiting...")
        except Exception as e:
            log.critical("Got exception, crashing...")
            log.critical(unicode(e))
            log.critical(traceback.format_exc())
            raise e
        server.server_close()
        sys.exit(0)
    else:
        os._exit(0)
else:
    os._exit(0)
