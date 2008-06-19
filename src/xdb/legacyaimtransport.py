# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
import os
import os.path
import config
from debug import LogEvent, INFO, WARN, ERROR

X = os.path.sep
SPOOL_UMASK = 0177
XDBNS_PREFIX = "aimtrans:"
XDBNS_REGISTER = XDBNS_PREFIX+"data"

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
		f = open(self.name + X + file + ".xml", "w")
		f.write(text)
		f.close()
		os.umask(prev_umask)
	
	
	def request(self, file, xdbns):
		""" Requests a specific xdb namespace from the XDB 'file' """
		try:
			document = self.__getFile(file)
			for child in document.elements():
				if child.getAttribute("xdbns") == xdbns:
					return child
		except:
			return None

	def files(self):
		""" Returns a list containing the files in the current XDB database """         
		files=os.listdir(self.name);
		for i in range(len(files)):
			files[i]=utils.unmangle(files[i])
			files[i]=files[i][:len(files[i])-4]
		return files

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
		reginfo = Element((None, "aimtrans"))

		logoninfo = reginfo.addElement("logon")
		logoninfo.attributes["id"] = username
		logoninfo.attributes["pass"] = password

		return reginfo

		reginfo = Element((None, "query"))
		reginfo.attributes["xmlns"] = XDBNS_REGISTER

		userEl = reginfo.addElement("username")
		userEl.addContent(username)

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
				if child.name == "logon":
					username = child.getAttribute("id")
					password = child.getAttribute("pass")
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
				if child.name == "buddies":
					for child2 in child.elements():
						if child2.getAttribute("name") == legacyID:
							attributes = {}
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
				if child.name == "buddies":
					for child2 in child.elements():
						if child2.hasAttribute("name"):
							entity = []
							entity.append(child2.getAttribute("name"))
							attributes = {}
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
			list = Element((None, "aimtrans"))
			list.attributes["xmlns"] = xdbns

		buddies = None
		for child in list.elements():
			try:
				if child.name == "buddies":
					buddies = child
					break
			except AttributeError:
				continue

		if buddies == None:
			buddies = list.addElement("buddies")

		# Remove the existing element
		for child in buddies.elements():
			try:
				if child.getAttribute("name") == legacyID:
					buddies.children.remove(child)
			except AttributeError:
				continue

		newentry = buddies.addElement("item")
		newentry["name"] = legacyID
		self.set(jabberID, xdbns, list)

	def removeListEntry(self, type, jabberID, legacyID):
		""" Removes a legacy ID entry from a list in
		the XDB, based off the type and jabberID you provide. """
		if type != "roster": return
		xdbns = XDBNS_PREFIX+type
		list = self.request(jabberID, xdbns)
		if list == None:
			list = Element((None, "aimtrans"))
			list.attributes["xmlns"] = xdbns

		buddies = None
		for child in list.elements():
			try:
				if child.name == "buddies":
					buddies = child
					break
			except AttributeError:
				continue

		if buddies == None:
			buddies = list.addElement("buddies")

		# Remove the existing element
		for child in buddies.elements():
			try:
				if child.getAttribute("name") == legacyID:
					buddies.children.remove(child)
			except AttributeError:
				continue

		self.set(jabberID, xdbns, list)


def housekeep():
	pass
