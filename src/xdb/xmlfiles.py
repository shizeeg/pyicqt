# Copyright 2004-2005 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID, InvalidFormat
import shutil
import sys
import os
import os.path
from debug import LogEvent, INFO, WARN, ERROR
import config

X = os.path.sep
SPOOL_UMASK = 0077
XDBNS_PREFIX = "jabber:iq:"
XDBNS_REGISTER = XDBNS_PREFIX+"register"
XDBNS_PREFERENCES = XDBNS_PREFIX+"settings"

class XDB:
	"""
	Class for storage of data.
	"""
	def __init__(self, name):
		""" Creates an XDB object. """
		self.name = os.path.join(os.path.abspath(config.spooldir), name)
		if not os.path.exists(self.name):
			os.makedirs(self.name)
	
	def __getFile(self, file):
		file = utils.mangle(file)
		hash = file[0:2]
		document = utils.parseFile(self.name + X + hash + X + file + ".xml")
		return document
	
	def __writeFile(self, file, text):
		file = utils.mangle(file)
		prev_umask = os.umask(SPOOL_UMASK)
		hash = file[0:2]
		pre = self.name + X + hash + X
		if not os.path.exists(pre):
			os.makedirs(pre)
		f = open(pre + file + ".xml", "w")
		f.write(text)
		f.close()
		os.umask(prev_umask)
	
	def files(self):
		""" Returns a list containing the files in the current XDB database """
		files = []
		for dir in os.listdir(self.name):
			if len(dir) != 2: continue
			if os.path.isdir(self.name + X + dir):
				files.extend(os.listdir(self.name + X + dir))
		files = [utils.unmangle(x) for x in files]
		files = [x[:-4] for x in files]
		while files.count(''):
			files.remove('')

		return files
	
	def request(self, file, xdbns):
		""" Requests a specific xdb namespace from the XDB 'file' """
		try:
			document = self.__getFile(file)
			for child in document.elements():
				if child.getAttribute("xdbns") == xdbns:
					return child
		except:
			return None
	
	def set(self, file, xdbns, element):
		""" Sets a specific xdb namespace in the XDB 'file' to element """
		try:
			element.attributes["xdbns"] = xdbns
			document = None
			try:
				document = self.__getFile(file)
			except IOError:
				pass
			if not document:
				document = Element((None, "xdb"))
			
			# Remove the existing node (if any)
			for child in document.elements():
				if child.getAttribute("xdbns") == xdbns:
					document.children.remove(child)
			# Add the new one
			document.addChild(element)
			
			self.__writeFile(file, document.toXml())
		except:
			LogEvent(INFO, msg="XDB error writing entry %s to file %s" % (xdbns, file))
			raise
	
	def remove(self, file):
		""" Removes an XDB file """
		file = self.name + X + file[0:2] + X + file + ".xml"
		file = utils.mangle(file)
		try:
			os.remove(file)
		except:
			LogEvent(INFO, msg="XDB error removing file " + file)
			raise

	def formRegEntry(self, username, password):
		""" Returns a domish.Element representation of the data passed. This element will be written to the XDB spool file """
		reginfo = Element((None, "query"))
		reginfo.attributes["xmlns"] = XDBNS_REGISTER

		userEl = reginfo.addElement("username")
		userEl.addContent(username)

		if config.xdbDriver_xmlfiles.get("format","") == "encrypted":
			passEl = reginfo.addElement("encpassword")
			passEl.addContent(utils.encryptPassword(password))
		else:
			passEl = reginfo.addElement("password")
			passEl.addContent(password)

		return reginfo

	def getAttributes(self, base):
		""" This function should, given a spool domish.Element, pull the username, password,
		and out of it and return them """
		username = ""
		password = ""
		for child in base.elements():
			try:
				if child.name == "username":
					username = child.__str__()
				elif child.name == "encpassword":
					password = utils.decryptPassword(child.__str__())
				elif child.name == "encryptedpassword":
					password = utils.decryptPassword(child.__str__())
				elif child.name == "password":
					password = child.__str__()
			except AttributeError:
				continue

		return username, password

	def getRegistration(self, jabberID):
		""" Retrieve registration information from the XDB.
		Returns a username and password. """
		result = self.request(jabberID, XDBNS_REGISTER)
		if result == None:
			return None

		username, password = self.getAttributes(result)
		if username and password and len(username) > 0 and len(password) > 0:
			return (username,password)
		else:
			return None

	def getRegistrationList(self):
		""" Returns an array of all of the registered jids. """
		return self.files()

	def setRegistration(self, jabberID, username, password):
		""" Sets up or creates a registration in the XDB.
		username and password are for the legacy account. """
		if len(password) == 0:
			password = (self.getRegistration(jabberID))[1]

		reginfo = self.formRegEntry(username, password)
		self.set(jabberID, XDBNS_REGISTER, reginfo)

	def removeRegistration(self, jabberID):
		""" Removes a registration from the XDB. """
		self.remove(jabberID)

	def getSettingList(self, jabberID):
		""" Gets a list of all settings for a user from the XDB. """
		settings = {}

		result = self.request(jabberID, XDBNS_PREFERENCES)
		if result == None:
			return settings

		for child in result.elements():
			try:
				settings[child.name] = child.__str__()
			except AttributeError:
				continue

		return settings

	def getSetting(self, jabberID, variable):
		""" Gets a user setting from the XDB. """
		result = self.request(jabberID, XDBNS_PREFERENCES)
		if result == None:
			return None

		for child in result.elements():
			try:
				if child.name == variable:
					return child.__str__()
			except AttributeError:
				continue

		return None

	def setSetting(self, jabberID, variable, value):
		""" Sets a user setting in the XDB. """
		prefs = self.request(jabberID, XDBNS_PREFERENCES)
		if prefs == None:
			prefs = Element((None, "query"))
			prefs.attributes["xmlns"] = XDBNS_PREFERENCES

		# Remove the existing element
		for child in prefs.elements():
			if child.name == variable:
				prefs.children.remove(child)

		newpref = prefs.addElement(variable)
		newpref.addContent(value)

		self.set(jabberID, XDBNS_PREFERENCES, prefs)

	def getListEntry(self, type, jabberID, legacyID):
		""" Retrieves a legacy ID entry from a list in
		the XDB, based off the type and jabberID you provide.
		Returns a dict of attributes, empty of no attributes, and
		None if the entry does not exist. """
		xdbns = XDBNS_PREFIX+type
		result = self.request(jabberID, xdbns)
		if result == None:
			return None

		attributes = None
		for child in result.elements():
			try:
				if child.getAttribute("jid") == legacyID:
					attributes = {}
					for a in child.attributes:
						if a == "jid": continue
						attributes[a] = child.getAttribute(a)
			except AttributeError:
				continue

		return attributes

	def getListTypes(self, jabberID):
		""" Returns an array containing a list of all list types
		associated with a user. """
		types = []
		try:
			document = self.__getFile(jabberID)
			for child in document.elements():
				xdbns = child.getAttribute("xdbns")
				if xdbns != XDBNS_REGISTER and xdbns != XDBNS_PREFERENCES:
					listtype = xdbns[len(XDBNS_PREFIX):]
					types.append(listtype)
		except:
			pass
		return types

	def getList(self, type, jabberID):
		""" Returns an array containing an entire list of a
		jabberID's from the XDB, based off the type and jabberID
		you provide.  Array entries are in the format of
		(legacyID, attributes) where attributes is a dict. """
		xdbns = XDBNS_PREFIX+type
		result = self.request(jabberID, xdbns)
		if result == None:
			return None

		entities = []
		for child in result.elements():
			try:
				if child.hasAttribute("jid"):
					entity = []
					entity.append(child.getAttribute("jid"))
					attributes = {}
					for a in child.attributes:
						if a == "jid": continue
						attributes[a] = child.getAttribute(a)
					entity.append(attributes)
					entities.append(entity)
			except AttributeError:
				continue

		return entities

	def setListEntry(self, type, jabberID, legacyID, payload = {}):
		""" Updates or adds a legacy ID entry to a list in
		the XDB, based off the type and jabberID you provide. """
		xdbns = XDBNS_PREFIX+type
		list = self.request(jabberID, xdbns)
		if list == None:
			list = Element((None, "query"))
			list.attributes["xmlns"] = xdbns

		# Remove the existing element
		for child in list.elements():
			try:
				if child.getAttribute("jid") == legacyID:
					list.children.remove(child)
			except AttributeError:
				continue

		newentry = list.addElement("item")
		newentry["jid"] = legacyID
		for p in payload.keys():
			newentry[p] = payload[p]

		self.set(jabberID, xdbns, list)

	def removeListEntry(self, type, jabberID, legacyID):
		""" Removes a legacy ID entry from a list in
		the XDB, based off the type and jabberID you provide. """
		xdbns = XDBNS_PREFIX+type
		list = self.request(jabberID, xdbns)
		if list == None:
			list = Element((None, "query"))
			list.attributes["xmlns"] = xdbns

		# Remove the element
		for child in list.elements():
			try:
				if child.getAttribute("jid") == legacyID:
					list.children.remove(child)
			except AttributeError:
				continue

		self.set(jabberID, xdbns, list)


def housekeep():
	try:
		noteList = ["doSpoolPrepCheck", "doHashDirUpgrade"]
		notes = utils.NotesToMyself(noteList)
		for note in noteList:
			if notes.check(note):
				exec("%s()" % note)
				notes.append(note)
		notes.save()
	except:
		print "An error occurred during one of the automatic data update routines.  Please report this bug."
		raise


def doSpoolPrepCheck():
	pre = os.path.abspath(config.spooldir) + X + config.jid + X

	print "Checking spool files and stringprepping any if necessary...",

	for file in os.listdir(pre):
		if os.path.isfile(pre + file) and file.find(".xml"):
			file = utils.unmangle(file).decode("utf-8", "replace")
			try:
				filej = internJID(file).full()
			except InvalidFormat, UnicodeDecodeError:
				print "Unable to stringprep "+file+".  Putting into BAD directory."
				file = utils.mangle(file)
				if not os.path.isdir(pre + "BAD"):
					os.makedirs(pre + "BAD")
				shutil.move(pre + file, pre + "BAD" + X + file)
				continue
			if file != filej:
				file = utils.mangle(file)
				filej = utils.mangle(filej)
				if os.path.exists(filej):
					print "Need to move "+file+" to "+filej+" but the latter exists!\nAborting!"
					sys.exit(1)
				else:
					shutil.move(pre + file, pre + filej)
	print "done"


def doHashDirUpgrade():
	print "Upgrading your XDB structure to use hashed directories for speed...",

	# Do avatars...
	pre = os.path.join(os.path.abspath(config.spooldir), config.jid) + X + "avatars" + X
	if os.path.exists(pre):
		for file in os.listdir(pre):
			if os.path.isfile(pre + file):
				pre2 = pre + file[0:3] + X
				if not os.path.exists(pre2):
					os.makedirs(pre2)
				shutil.move(pre + file, pre2 + file)
	
	# Do spool files...
	pre = os.path.join(os.path.abspath(config.spooldir), config.jid) + X
	if os.path.exists(pre):
		for file in os.listdir(pre):
			if os.path.isfile(pre + file) and file.find(".xml"):
				hash = file[0:2]
				pre2 = pre + hash + X
				if not os.path.exists(pre2):
					os.makedirs(pre2)

				if os.path.exists(pre2 + file):
					print "Need to move", file, "to", pre2 + file, "but the latter exists!\nAborting!"
					os.exit(1)
				else:
					shutil.move(pre + file, pre2 + file)

	print "done"
