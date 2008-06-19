# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
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
		document = utils.parseFile(self.name + X + file + ".xml")
		return document
	
	def __writeFile(self, file, text):
		file = utils.mangle(file)
		prev_umask = os.umask(SPOOL_UMASK)
		pre = self.name + X
		if not os.path.exists(pre):
			os.makedirs(pre)
		f = open(pre + file + ".xml", "w")
		f.write(text)
		f.close()
		os.umask(prev_umask)
	
	def files(self):
		""" Returns a list containing the files in the current XDB database """
		files = []
		files.extend(os.listdir(self.name))
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
		file = self.name + X + file + ".xml"
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
		return {}

	def getSetting(self, jabberID, variable):
		""" Gets a user setting from the XDB. """
		return None

	def setSetting(self, jabberID, variable, value):
		""" Sets a user setting in the XDB. """
		pass

	def getListEntry(self, type, jabberID, legacyID):
		""" Retrieves a legacy ID entry from a list in
		the XDB, based off the type and jabberID you provide.
		Returns a dict of attributes, empty of no attributes, and
		None if the entry does not exist. """
		if type != "roster": return None
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
		return ["roster"]

	def getList(self, type, jabberID):
		""" Returns an array containing an entire list of a
		jabberID's from the XDB, based off the type and jabberID
		you provide.  Array entries are in the format of
		(legacyID, attributes) where attributes is a dict. """
		if type != "roster": return None
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
		if type != "roster": return
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
		if type != "roster": return
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
	pass
