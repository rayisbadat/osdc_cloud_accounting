#!/usr/bin/python

## This program makes some assumptions.  Mainly that if a key exists then the subuser should also exists # Fixme
## And that we should always update the s3creds.txt file after every run #NotSure

import getopt
import sys
import os
import pwd 
import subprocess
import json
import pprint


def create_ceph_s3_user(project, username,  user_type="subuser", access_type="readwrite", debug=None, run=None):
    """ Create the s3creds for a the project or subuser
        user_type=[subuser]|project
        access_type=[readwrite]|readonly
    """


    if user_type == "project":
	    cmd = [ 'radosgw-admin', 'user', 'create', 
	        "--uid=%s"%(project), 
	        "--display-name='%s'"%(project),
	        '--key-type=s3',
	        '--gen-access-key',
	        '--gen-secret',
	        ]
    elif user_type == "subuser":
	    cmd = [ 'radosgw-admin', 'subuser', 'create', 
	        "--uid=%s"%(project), 
	        "--subuser=%s"%(username),
	        "--access=%s"%(access_type),
	        '--key-type=s3',
	        '--gen-access-key',
	        '--gen-secret',
	        ]
    elif user_type == "info":
	    cmd = [ 'radosgw-admin', 'user', 'info', 
	        "--uid=%s"%(project)
            ]

    else:
        sys.stderr.write("No valid option given for user_type=%s in %s\n"%(user_type,__name__) )
        sys.exit(2)

    if debug:
        pprint.pprint(cmd)

    if run:
        try:
            cmd_output=subprocess.check_call(cmd, stdout=open(os.devnull, 'wb') ) 

        except subprocess.CalledProcessError, e:
            sys.stderr.write("ERROR: create_ceph_s3_user creating for user: %s\n" % (index) )
            sys.stderr.write("%s\n" % e.output)
            return False


def get_ceph_s3_key(project, username, user_type="subuser", debug=None,run=None):
    
    """ Get the s3creds for a the project or subuser
        If it doesnt exist return None
        user_type=[subuser]|project
        access_type=[readwrite]|readonly
    """

    cmd = [ 'radosgw-admin', 'user', 'info', "--uid=%s"%(project) ]
    index="%s:%s"%(project, username)
    keys={}

    if debug:
        pprint.pprint(cmd)
        print "Index: %s" % ( index )

    if run:
        try:
            cmd_output=subprocess.check_output(cmd)
    
        except subprocess.CalledProcessError, e:
            return None
   
        if user_type == "project":
            if debug:
                sys.stderr.write("INFO: Found project, %s ,in ceph already.\n"%(index))
            return True
 
        if user_type == "subuser":
            json_output=json.loads(cmd_output)
            
        
            for key in json_output["keys"]:
                if debug:
                    print "%s=%s,%s"%(key['user'],key['access_key'],key['secret_key'])

                keys[key['user']]={}
                keys[key['user']]["access_key"]=key['access_key']
                keys[key['user']]["secret_key"]=key['secret_key']
        
            if debug:
                sys.stderr.write("INFO: Found following keys in ceph.\n")
                pprint.pprint( keys )

        try:
            if keys[index]:
                if debug:
                    sys.stderr.write("INFO: Found project:subuser to have s3 user, %s ,in ceph.\n"%(index))
                return keys[index]
            else:
                return None
        except KeyError as e:
            if debug:
                sys.stderr.write("ERROR: No s3 key found in ceph for subuser: %s\n"%(index))
            return None
    
    else:
        return None

def write_s3_creds_to_file( project, username, user_keys, debug=None, run=None):
    """ Write the s3 creds out to file """

    homedir=os.path.expanduser("~%s"%(username))
    creds_file_path="%s/s3cred.txt"%( homedir )
    creds_file = open( creds_file_path, "a" )
    if run:
        creds_file.write( "\n[[ %s:%s ]]\n" %( project, username ) )
        creds_file.write( "access_key=%s\n"%(user_keys['access_key']) )
        creds_file.write( "secret_key=%s\n"%(user_keys['secret_key']) )
    creds_file.close()

    os.chown( creds_file_path, pwd.getpwnam(username).pw_uid, -1 )



if __name__ == "__main__":


    #Load in the CLI flags
    run = True
    debug = False
    create_new = True

    try:
        opts, args = getopt.getopt(sys.argv[1:], "", ["debug", "norun", ])
    except getopt.GetoptError:
        sys.stderr.write("ERROR: Getopt\n")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("--debug"):
            debug = True
        elif opt in ("--norun"):
            run = False

    pprint.pprint( args )
    #2+1
    if len(args) < 2:
        sys.stderr.write("Usage: %s project username \n"%(sys.argv[0]))
        sys.exit(1)

    project=args[0]
    username=args[1]



if not get_ceph_s3_key(project, username, user_type="project",  debug=debug,run=run):
    create_ceph_s3_user(project, username, user_type="project", debug=debug,run=run) 

user_keys=get_ceph_s3_key(project, username, user_type="subuser", debug=debug,run=run) 

if not user_keys:
    create_ceph_s3_user(project, username, user_type="subuser", debug=debug,run=run) 
    user_keys=get_ceph_s3_key(project, username, user_type="subuser", debug=debug,run=run) 

write_s3_creds_to_file(project,username, user_keys=user_keys,debug=debug,run=run)



