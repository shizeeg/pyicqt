# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
import session
import legacy
from debug import LogEvent, INFO, WARN, ERROR
import lang
import jabw
import config
import globals

def authenticate_ldap(user, pwd):
	""" use ldap to authenticate user before """
	""" granting registration rights """
	import ldap
	LogEvent(INFO, msg="Performing authentication")
	try:
		l = ldap.open(config.authRegister_LDAP["server"])
		l.simple_bind_s(config.authRegister_LDAP["rootDN"], config.authRegister_LDAP["password"])
		LogEvent(INFO, msg="Bound to LDAP server")
		searchterm = config.authRegister_LDAP["uidAttr"] + "=" + user
		ldap_result_id = l.search(config.authRegister_LDAP["baseDN"], ldap.SCOPE_SUBTREE, searchterm, None)
		LogEvent(INFO, msg="Performed search")

		result_type, result_data = l.result(ldap_result_id, 0)
		LogEvent(INFO, msg="Got search results")

		if (result_data == []):
			return "false"
		else:
			if result_type == ldap.RES_SEARCH_ENTRY:
				LogEvent(INFO, msg="Getting acct data")
				acctdata = result_data[0]
				result_data = []
				acctdn = acctdata[0]
				acctdata = []

		LogEvent(INFO, msg=acctdn)
		if(acctdn == ""):
			#user does not exist
			return "false"
		else:
			#user exists, see if password is valid
			try:
				l1 = ldap.open(config.authRegister_LDAP["server"])
				l1.simple_bind_s(acctdn, pwd)
				#worked, valid info
				return "true"
			except:
				#problem, return false
				return "false"
	except:
		#problem, return false
		LogEvent(INFO, msg="Error performing authentication")
                return "false"



class RegisterManager:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		if not config.disableRegister:
			self.pytrans.disco.addFeature(globals.IQREGISTER, self.incomingRegisterIq, config.jid)
		LogEvent(INFO)
	
	def removeRegInfo(self, jabberID):
		LogEvent(INFO)
		try:
			# If the session is active then send offline presences
			session = self.pytrans.sessions[jabberID]
			session.removeMe()
		except KeyError:
			pass
		
		self.pytrans.xdb.removeRegistration(jabberID)
		LogEvent(INFO, msg="done")
	
	
	def incomingRegisterIq(self, incoming):
		# Check what type the Iq is..
		itype = incoming.getAttribute("type")
		LogEvent(INFO)
		if itype == "get":
			if config.authRegister:
				# Check to see if they're registered
				source = internJID(incoming.getAttribute("from")).userhost()
				result = self.pytrans.xdb.getRegistration(source)
				if result:
					self.sendRegistrationFields(incoming)
				else:
					# Must first submit local credentials
					self.sendLocalRegistrationFields(incoming)
                        else:
				# Send real registration form
				self.sendRegistrationFields(incoming)
		elif itype == "set":
			if config.authRegister:
				# Check to see if they're registered by local credentials
				source = internJID(incoming.getAttribute("from")).userhost()
				result = self.pytrans.xdb.getRegistration(source)
				username = ""
				password = ""
				if result:
					username, password = result
				if username == "local" and password == "local":
					# Update real credentials
					self.updateRegistration(incoming)
				else:
					# Must first validate local credentials
					self.validateLocalRegistration(incoming)
                        else:
				# Update real credentials
				self.updateRegistration(incoming)

	def sendLocalRegistrationFields(self, incoming):
		# Construct a reply with the fields they must fill out
		LogEvent(INFO)
		reply = Element((None, "iq"))
		reply.attributes["from"] = config.jid
		reply.attributes["to"] = incoming.getAttribute("from")
		reply.attributes["id"] = incoming.getAttribute("id")
		reply.attributes["type"] = "result"
		reply.attributes["authenticate"] = "true"
		query = reply.addElement("query")
		query.attributes["xmlns"] = globals.IQREGISTER
		instructions = query.addElement("instructions")
		ulang = utils.getLang(incoming)
		instructions.addContent(lang.get("authenticatetext", ulang))
		userEl = query.addElement("username")
		passEl = query.addElement("password")
                
		self.pytrans.send(reply)
        
	def validateLocalRegistration(self, incoming):
		# Grab the username and password
		LogEvent(INFO)
		source = internJID(incoming.getAttribute("from")).userhost()
		ulang = utils.getLang(incoming)
		username = None
		password = None
                
		for queryFind in incoming.elements():
			if queryFind.name == "query":
				for child in queryFind.elements():
					try:
						if child.name == "username":
							username = child.__str__().lower()
						elif child.name == "password":
							password = child.__str__()
					except AttributeError, TypeError:
						continue # Ignore any errors, we'll check everything below

		if username and password and len(username) > 0 and len(password) > 0:
			# Valid authentication data
			LogEvent(INFO, msg="Authenticating user")
			try:
				if config.authRegister == "LDAP":
					result = authenticate_ldap(username, password)
				else:
					result = "true"
				if result == "true":
					self.pytrans.xdb.setRegistration(source, "local", "local")
					LogEvent(INFO, msg="Updated XDB")
					self.successReply(incoming)
					LogEvent(INFO, msg="Authenticated user")
				else:
					self.xdbErrorReply(incoming)
					LogEvent(INFO, msg="Authentication failure")
			except:
				self.xdbErrorReply(incoming)
				raise
		else:
			self.badRequestReply(incoming)

	def sendRegistrationFields(self, incoming):
		# Construct a reply with the fields they must fill out
		LogEvent(INFO)
		reply = Element((None, "iq"))
		reply.attributes["from"] = config.jid
		reply.attributes["to"] = incoming.getAttribute("from")
		reply.attributes["id"] = incoming.getAttribute("id")
		reply.attributes["type"] = "result"
		query = reply.addElement("query")
		query.attributes["xmlns"] = globals.IQREGISTER
		instructions = query.addElement("instructions")
		ulang = utils.getLang(incoming)
		instructions.addContent(lang.get("registertext", ulang))
		userEl = query.addElement("username")
		passEl = query.addElement("password")
		
		# Check to see if they're registered
		source = internJID(incoming.getAttribute("from")).userhost()
		result = self.pytrans.xdb.getRegistration(source)
		if result:
			username, password = result
			if username != "local":
				userEl.addContent(username)
				query.addElement("registered")
		
		self.pytrans.send(reply)
	
	def updateRegistration(self, incoming):
		# Grab the username and password
		LogEvent(INFO)
		source = internJID(incoming.getAttribute("from")).userhost()
		ulang = utils.getLang(incoming)
		username = None
		password = None
		
		for queryFind in incoming.elements():
			if(queryFind.name == "query"):
				for child in queryFind.elements():
					try:
						if(child.name == "username"):
							username = child.__str__().lower()
						elif(child.name == "password"):
							password = child.__str__()
						elif(child.name == "remove"):
							# The user wants to unregister the transport! Gasp!
							LogEvent(INFO, msg="Unregistering")
							try:
								self.removeRegInfo(source)
								self.successReply(incoming)
							except:
								self.xdbErrorReply(incoming)
								return
							LogEvent(INFO, msg="Unregistered!")
							return
					except AttributeError, TypeError:
						continue # Ignore any errors, we'll check everything below
		
		if username and password and len(username) > 0 and len(password) > 0:
			# Valid registration data
			LogEvent(INFO, msg="Updating XDB")
			try:
				self.pytrans.xdb.setRegistration(source, username, password)
				LogEvent(INFO, msg="Updated XDB")
				self.successReply(incoming)
				LogEvent(INFO, msg="Sent a result Iq")
				to = internJID(incoming.getAttribute("from")).userhost()
				jabw.sendPresence(self.pytrans, to=to, fro=config.jid, ptype="subscribe")
				if config.registerMessage:
					jabw.sendMessage(self.pytrans, to=incoming.getAttribute("from"), fro=config.jid, body=config.registerMessage)
			except:
				self.xdbErrorReply(incoming)
				raise
		
		else:
			self.badRequestReply(incoming)
	
	def badRequestReply(self, incoming):
		LogEvent(INFO)
		# Send an error Iq
		reply = incoming
		reply.swapAttributeValues("to", "from")
		reply.attributes["type"] = "error"
		error = reply.addElement("error")
		error.attributes["type"] = "modify"
		interror = error.addElement("bad-request")
		interror["xmlns"] = globals.XMPP_STANZAS
		self.pytrans.send(reply)
	
	def xdbErrorReply(self, incoming):
		LogEvent(INFO)
		# send an error Iq
		reply = incoming
		reply.swapAttributeValues("to", "from")
		reply.attributes["type"] = "error"
		error = reply.addElement("error")
		error.attributes["type"] = "wait"
		interror = error.addElement("internal-server-error")
		interror["xmlns"] = globals.XMPP_STANZAS
		self.pytrans.send(reply)
	
	def successReply(self, incoming):
		reply = Element((None, "iq"))
		reply.attributes["type"] = "result"
		ID = incoming.getAttribute("id")
		if(ID): reply.attributes["id"] = ID
		reply.attributes["from"] = config.jid
		reply.attributes["to"] = incoming.getAttribute("from")
		self.pytrans.send(reply)

