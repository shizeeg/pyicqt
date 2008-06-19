# Copyright 2005-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details
#
# MySQL database storage.  See db-setup.mysql in the tools directory in
# the root of the distribution, as well as configuration options in your
# transport config file.  (see config_example.xml)
#

import config
import os
import MySQLdb

class XDB:
	"""
	Class for storage of data.
	"""
	def __init__(self, name):
		""" Creates an XDB object. """
		self.db=MySQLdb.connect(
			host=config.xdbDriver_mysql["server"],
			user=config.xdbDriver_mysql["username"],
			passwd=config.xdbDriver_mysql["password"],
			charset="utf8",
			db=config.xdbDriver_mysql["database"]
		)
		if not self.db:
			print "Unable to connect to MySQL database."
			os.exit(1)

	def db_ping(self):
		""" 
		Wrapper function for MySQLdb.ping() to reconnect on lost connection
		""" 
		try:
			self.db.ping()
		except:
			self.db=MySQLdb.connect(
				host=config.xdbDriver_mysql["server"],
				user=config.xdbDriver_mysql["username"],
				passwd=config.xdbDriver_mysql["password"],
				charset="utf8",
				db=config.xdbDriver_mysql["database"]
			)
			self.db.ping()

	def getRegistration(self, jabberID):
		""" Retrieve registration information from the XDB.
		Returns a username and password. """
		self.db_ping()		
		c=self.db.cursor()
		c.execute("SELECT username,password,UNHEX(encryptedpassword) FROM register WHERE owner = '%s'" % jabberID)
		ret = c.fetchone()
		if ret:
			(username,password,encpass) = ret
			if encpass:
				return (username,encpass)
			else:
				return (username,password)
		else:
			return None

	def getRegistrationList(self):
		""" Returns an array of all of the registered jids. """
		self.db_ping()
		c=self.db.cursor()
		c.execute("SELECT owner FROM register")
		results = []
		ret = c.fetchone()
		while ret:
			(jid) = ret[0]
			results.append(jid)
			ret = c.fetchone()
		return results

	def setRegistration(self, jabberID, username, password):
		""" Sets up or creates a registration in the XDB.
		username and password are for the legacy account. """
		self.db_ping()
		c=self.db.cursor()
		c.execute("DELETE FROM register WHERE owner = '%s'" % jabberID)
                if config.xdbDriver_mysql.get("format","") == "encrypted":
			c.execute("INSERT INTO register(owner,username,encryptedpassword) VALUES('%s','%s',HEX('%s'))" % (jabberID, username, password))
		else:
			c.execute("INSERT INTO register(owner,username,password) VALUES('%s','%s','%s')" % (jabberID, username, password))

	def removeRegistration(self, jabberID):
		""" Removes a registration from the XDB. """
		self.db_ping()
		c=self.db.cursor()
		c.execute("DELETE FROM register WHERE owner = '%s'" % jabberID)
		c.execute("DELETE FROM settings WHERE owner = '%s'" % jabberID)
		c.execute("DELETE FROM lists WHERE owner = '%s'" % jabberID)
		c.execute("DELETE FROM list_attributes WHERE owner = '%s'" % jabberID)

	def getSettingList(self, jabberID):
		""" Gets a list of all settings for a user from the XDB. """
		self.db_ping()
		c=self.db.cursor()
		c.execute("SELECT variable,value FROM settings WHERE owner = '%s'" % (jabberID))
		results = []
		ret = c.fetchone()
		while ret:
			(variable) = ret[0]
			(value) = ret[1]
			results[variable] = value
			ret = c.fetchone()
		return results

	def getSetting(self, jabberID, variable):
		""" Gets a user setting from the XDB. """
		self.db_ping()
		c=self.db.cursor()
		c.execute("SELECT value FROM settings WHERE owner = '%s' AND variable = '%s'" % (jabberID, variable))
		ret = c.fetchone()
		if ret:
			(value) = ret[0]
			return value
		else:
			return None

	def setSetting(self, jabberID, variable, value):
		""" Sets a user setting in the XDB. """
		self.db_ping()
		c=self.db.cursor()
		c.execute("DELETE FROM settings WHERE owner = '%s' AND variable = '%s'" % (jabberID, variable))
		c.execute("INSERT INTO settings(owner,variable,value) VALUES('%s','%s','%s')" % (jabberID, variable, value))

	def getListEntry(self, type, jabberID, legacyID):
		""" Retrieves a legacy ID entry from a list in
		the XDB, based off the type and jabberID you provide. """
		self.db_ping()
		attributes = {}
		c=self.db.cursor()
		c.execute("SELECT attribute,value FROM list_attributes WHERE owner = '%s' AND type = '%s' AND jid = '%s'" % (jabberID, type, legacyID))
		ret = c.fetchone()
		while ret:
			(attribute,value) = ret[0:1]
			attributes[attribute] = value
			ret = c.fetchone()
		return attributes

	def getListTypes(self, jabberID):
		""" Returns an array containing a list of all list types
		associated with a user. """
		self.db_ping()
		types = []
		c=self.db.cursor()
		c.execute("SELECT type FROM lists WHERE owner = '%s'" % (jabberID))
		ret = c.fetchone()
		while ret:
			(type) = ret[0]
			types.append(type)
			ret = c.fetchone()
                return types

	def getList(self, type, jabberID):
		""" Retrieves an array containing an entire list of a
		 jabberID's from the XDB, based off the type and jabberID
		you provide. """
		self.db_ping()
		entities = []
		c=self.db.cursor()
		c.execute("SELECT jid FROM lists WHERE owner = '%s' AND type = '%s'" % (jabberID, type))
		ret = c.fetchone()
		while ret:
			(jid) = ret[0]
			entity = []
			entity.append(jid)
			attributes = {}
			self.db_ping()
			ic = self.db.cursor()
			ic.execute("SELECT attribute,value FROM list_attributes WHERE owner = '%s' AND type = '%s' AND jid = '%s'" % (jabberID, type, jid))
			iret = ic.fetchone()
			while iret:
				(attribute,value) = iret[0:2]
				attributes[attribute] = value
				iret = ic.fetchone()
			entity.append(attributes)
			ret = c.fetchone()
		return entities

	def setListEntry(self, type, jabberID, legacyID, payload = {}):
		""" Updates or adds a legacy ID entry to a list in
		the XDB, based off the type and jabberID you provide. """
		self.db_ping()
		c=self.db.cursor()
		c.execute("DELETE FROM lists WHERE owner = '%s' AND type = '%s' AND jid = '%s'" % (jabberID, type, legacyID))
		c.execute("DELETE FROM list_attributes WHERE owner = '%s' AND type = '%s' AND jid = '%s'" % (jabberID, type, legacyID))
		c.execute("INSERT INTO lists(owner,type,jid) VALUES('%s','%s','%s')" % (jabberID, type, legacyID))
		for p in payload.keys():
			c.execute("INSERT INTO list_attributes(owner,type,jid,attribute,value) VALUES('%s','%s','%s','%s','%s')" % (jabberID, type, legacyID, p, payload[p].replace("'", "\\'")))

	def removeListEntry(self, type, jabberID, legacyID):
		""" Removes a legacy ID entry from a list in
		the XDB, based off the type and jabberID you provide. """
		self.db_ping()
		c=self.db.cursor()
		c.execute("DELETE FROM lists WHERE owner = '%s' AND type = '%s' AND jid = '%s'" % (jabberID, type, legacyID))
		c.execute("DELETE FROM list_attributes WHERE owner = '%s' AND type = '%s' AND jid = '%s'" % (jabberID, type, legacyID))


def housekeep():
	""" Perform cleanup type tasks upon startup. """
	pass
