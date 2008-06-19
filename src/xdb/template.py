# Copyright 2005-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details
#
# This is a template for any new XDB drivers that might be written.
#

class XDB:
	"""
	Class for storage of data.
	"""
	def __init__(self, name):
		""" Creates an XDB object. """
		# Do whatever setup type stuff you might need

	def getRegistration(self, jabberID):
		""" Retrieve registration information from the XDB.
		Returns a username and password. """
		return None

	def getRegistrationList(self):
		""" Returns an array of all of the registered jids. """
		return []

	def setRegistration(self, jabberID, username, password):
		""" Sets up or creates a registration in the XDB.
		username and password are for the legacy account. """
		pass

	def removeRegistration(self, jabberID):
		""" Removes a registration from the XDB. """
		pass

	def getSettingList(self, jabberID):
		""" Gets a list of all settings for a user from the XDB. """
		return {}

	def getSetting(self, jabberID, variable):
		""" Gets a user setting from the XDB. """
		return None

	def setSetting(self, jabberID, variable, value):
		""" Sets a user setting in the XDB. """
		pass

	def getListTypes(self, jabberID):
		""" Returns an array containing a list of all list types
		associated with a user. """
		return []

	def getListEntry(self, namespace, jabberID, legacyID):
		""" Retrieves a legacy ID entry from a list in
		the XDB, based off the namespace and jabberID you provide. """
		return None

	def getList(self, namespace, jabberID):
		""" Retrieves an array containing an entire list of a
		 jabberID's from the XDB, based off the namespace and jabberID
		you provide. """
		return None

	def setListEntry(self, namespace, jabberID, legacyID, payload = {}):
		""" Updates or adds a legacy ID entry to a list in
		the XDB, based off the namespace and jabberID you provide. """
		pass

	def removeListEntry(self, namespace, jabberID, legacyID):
		""" Removes a legacy ID entry from a list in
		the XDB, based off the namespace and jabberID you provide. """
		pass


def housekeep():
	""" Perform cleanup type tasks upon startup. """
	pass
