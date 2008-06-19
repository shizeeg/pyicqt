#!/usr/bin/env python
#
# Spool Migration Script
#
# This script takes two arguments.  The first is either "dump" or "restore".
# The second argument will be a file that your xdb will be dumped to, in the
# case of a "dump", or restored from, in the case of a "restore".  The
# spool config used will be what is in config.xml in the root of the
# distribution.  This script is expected to be run from this directory.
#
# For example, if you are currently using the xmlfiles xdb backend, you
# would first have a config.xml file that is configured for that.  You would
# then type './migrate.py dump mydump'.  This will produce a long-ish file
# in XML format that contains all of the data from your spool.
#
# Next, lets say you wanted to switch to the MySQL xdb backend.  You would
# first make sure that you have it set up correctly as per the instructions.
# (you would have had to create the tables using db-setup.mysql in this
# directory)  Then you would set up your config.xml appropriately and
# run './migrate restore mydump'.  This will import the xdb roster into
# your new spool.
#
# WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING
# A restore -will- write over entries from your current spool.
# Please make sure to make a backup if you wish to do so.
# WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING
#
# This script accepts a subset of the command line flags that the transport
# itself accepts.  Please run it with '-h' to see the available options.
#

transportname	= "PyICQt"
dumpversion	= "1.0"

import sys
reload(sys)
sys.setdefaultencoding('utf-8')
del sys.setdefaultencoding
sys.path.append("../src")
import debug
import getopt
import config
import utils

def showhelp():
	print "./migrate.py [options] cmd file"
	print "options:"
	print "   -h                  print this help"
	print "   -c <file>           read configuration from this file"
	print "   -o <var>=<setting>  set config var to setting"
	print "   -d                  print debugging output"
	print "cmd:";
	print "   dump                dump spool to file"
	print "   restore             restore spool from file"
	sys.exit(0)

conffile = "config.xml"
options = {}
opts, args = getopt.getopt(sys.argv[1:], "c:do:h", ["config=", "debug", "option=", "help"])
for o, v in opts:
	if o in ("-c", "--config"):
		conffile = v
	elif o in ("-d", "--debug"):
		config.debugOn = True
	elif o in ("-o", "--option"):
		var, setting = v.split("=", 2)
		options[var] = setting
	elif o in ("-h", "--help"):
		showhelp()
reload(debug)

if len(args) != 2:
	showhelp()

import twistfix
twistfix.main()

import xmlconfig
xmlconfig.Import(conffile, options)
from twisted.words.xish.domish import Element

if args[0] == "dump":
	import xdb
	myxdb = xdb.XDB(config.jid)
	out = Element((None, "pydump"))
	out["transport"] = transportname
	out["version"] = dumpversion
	for jid in myxdb.getRegistrationList():
		print "Dumping "+jid+"..."
		userpass = myxdb.getRegistration(jid)
		if not userpass: continue
		user = out.addElement("user")
		user["jid"] = jid
		user["username"] = userpass[0]
		user["password"] = userpass[1]
		prefs = user.addElement("preferences")
		settinglist = myxdb.getSettingList(jid)
		if settinglist:
			for pref in settinglist:
				thispref = settinglist.addElement(pref)
				thispref.addContent(settinglist[pref])
		listtypes = myxdb.getListTypes(jid)
		if listtypes:
			for listtype in listtypes:
				list = user.addElement("list")
				list["type"] = listtype
				listentries = myxdb.getList(listtype, jid)
				if not listentries: continue
				for entry in listentries:
					listentry = list.addElement("entry")
					listentry["name"] = entry[0]
					attrs = entry[1]
					for attr in attrs:
						entryattr = listentry.addElement(attr)
						entryattr.addContent(attrs[attr])
	f = open(args[1], "w")
	f.write(out.toXml())
	f.close()
elif args[0] == "restore":
	import xdb
	myxdb = xdb.XDB(config.jid)
	input = utils.parseFile(args[1])
	if input.getAttribute("transport") != transportname:
		print "The dump file specified does not appear to be for this transport."
		sys.exit(0)
	for child in input.elements():
		jid = child.getAttribute("jid")
		print "Restoring "+jid+"..."
		doesexist = myxdb.getRegistration(jid)
		if doesexist:
			myxdb.removeRegistration(jid)
		username = child.getAttribute("username")
		password = child.getAttribute("password")
		myxdb.setRegistration(jid, username, password)
		for child2 in child.elements():
			if child2.name == "preferences":
				for pref in child2.elements():
					myxdb.setSetting(jid, pref, pref.__str__())
			elif child2.name == "list":
				type = child2.getAttribute("type")
				for entry in child2.elements():
					name = entry.getAttribute("name")
					attrs = {}
					for attr in entry.elements():
						attrs[attr.name] = attr.__str__()
					myxdb.setListEntry(type, jid, name, payload=attrs)
else:
	showhelp()
