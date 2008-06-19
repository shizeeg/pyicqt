# Copyright 2005-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from debug import LogEvent, INFO, WARN, ERROR
import config
import sys
if type(True) != bool: from bool import bool

def invalidError(text):
	print text
	print "Exiting..."
	sys.exit(1)

def importFile(conffile):
	#if conffile[0] != "/":
	#	conffile = "../"+conffile

	try:
		document = utils.parseFile(conffile)
	except Exception, e:
		invalidError("Error parsing configuration file: " + str(e))

	for child in document.elements():
		tag = child.name
		cdata = child.__str__()
		children = [x for x in child.elements()]
		if not hasattr(config, tag):
			print "Ignoring unrecognized configuration option %r" % tag
		elif type(getattr(config, tag)) == dict:
			# For options like <settings><username>blar</username><password>foo</password></settings>
			try:
				if not cdata.isspace():
					invalidError("Tag %r in your configuration file should be a dictionary (ie, must have subtags)." % (tag))
				myDict = getattr(config, tag)
				for child in children:
					n = child.name
					s = child.__str__()
					myDict[n] = s
					LogEvent(INFO, msg="Adding %r=%r to config dictionary %r" % (n, s, tag), skipargs=True)
			except AttributeError:
				print "Ignoring configuration option %r" % tag
		elif type(getattr(config, tag)) == list:
			# For options like <admins><jid>user1@host.com</jid><jid>user2@host.com</jid></admins>
			try:
				if not cdata.isspace():
					invalidError("Tag %r in your configuration file should be a list (ie, must have subtags)." % (tag))
				myList = getattr(config, tag)
				for child in children:
					s = child.__str__()
					LogEvent(INFO, msg="Adding %r to config list %r" % (s, tag), skipargs=True)
					myList.append(s)
			except AttributeError:
				print "Ignoring configuration option %r" % tag
		elif type(getattr(config, tag)) == str:
			# For config options like <ip>127.0.0.1</ip>
			try:
				if not cdata:
					invalidError("Tag %r in your configuration file should be a string (ie, must have cdata)." % (tag))
				LogEvent(INFO, msg="Setting config option %r = %r" % (tag, cdata), skipargs=True)
				setattr(config, tag, cdata)
			except AttributeError:
				print "Ignoring configuration option %r" % tag
		elif type(getattr(config, tag)) == int:
			# For config options like <port>5347</port>
			try:
				if not cdata:
					invalidError("Tag %r in your configuration file should be an integer (ie, must have numeric cdata)." % (tag))
				LogEvent(INFO, msg="Setting config option %r = %r" % (tag, cdata), skipargs=True)
				try:
					setattr(config, tag, int(cdata))
				except:
					# Isn't an integer apparantly.
					invalidError("Tag %r in your configuration file should be an integer (ie, must have numeric cdata)." % (tag))
			except AttributeError:
				print "Ignoring configuration option %r" % tag
		elif type(getattr(config, tag)) == bool:
			# For config options like <crossChat/>
			try:
				if cdata:
					invalidError("Tag %r in your configuration file should be a boolean (ie, no cdata)." % (tag))
				LogEvent(INFO, msg="Enabling config option %r" % (tag), skipargs=True)
				setattr(config, tag, True)
			except AttributeError:
				print "Ignoring configuration option %r" % tag
		elif isinstance(getattr(config, tag), config.DeprecatedVariable):
			# For deprecated options, we will display a warning
			getattr(config, tag)()
		else:
			print "Ignoring unrecognized configuration option %r [unrecognized type %s]" % (tag, type(getattr(config, tag)))

def importOptions(options):
	for o in options:
		LogEvent(INFO, msg="Setting config option %r = %r" % (o, options[o]), skipargs=True)
		setattr(config, o, options[o])

def Import(file = None, options = None):
	LogEvent(INFO, msg="Created configuration entity", skipargs=True)
	if file != None:
		importFile(file)
	if options != None:
		importOptions(options)
