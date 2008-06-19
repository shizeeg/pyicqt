# Copyright 2005-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.internet import reactor
from twisted.words.xish.domish import Element
import jabw
import config
from debug import LogEvent, INFO, WARN, ERROR
import lang
import sha
import legacy
import globals
import base64
if not config.disableAvatars:
	import Image
import StringIO


class Contact:
	""" Represents a Jabber contact """
	def __init__(self, jid, sub, contactList):
		self.jid = jid
		self.contactList = contactList
		self.groups = []
		self.sub = sub
		self.nickname = ""
		self.avatar = None
		self.show = ""
		self.status = ""
		self.url = ""
		self.ptype = "unavailable"
	
	def removeMe(self):
		""" Destroys this object. Does not remove the contact from the server's list. """
		self.contactList = None
		self.avatar = None
	
	def syncContactGrantedAuth(self):
		""" Since last using the transport the user has been granted authorisation by this contact.
		Call this to synchronise the user's Jabber list with their legacy list after logon. """
		if self.sub == "none":
			self.sub = "to"
		elif self.sub == "from":
			self.sub = "both"
		else:
			return
		self.updateRoster("subscribe")

	def syncContactRemovedAuth(self):
		""" Since last using the transport the user has been blocked by this contact.
		Call this to synchronise the user's Jabber list with their legacy list after logon. """
		if self.sub == "to":
			self.sub = "none"
		elif self.sub == "both":
			self.sub = "from"
		else:
			return
		self.updateRoster("unsubscribed")
	
	def syncUserGrantedAuth(self):
		""" Since last using the transport the user has granted authorisation to this contact.
		Call this to synchronise the user's Jabber list with their legacy list after logon. """
		if self.sub == "none":
			self.sub = "from"
		elif self.sub == "to":
			self.sub = "both"
		else:
			return
		self.updateRoster("subscribe")
	
	def syncUserRemovedAuth(self):
		""" Since last using the transport the user has removed this contact's authorisation.
		Call this to synchronise the user's Jabber list with their legacy list after logon. """
		if self.sub == "from":
			self.sub = "none"
		elif self.sub == "both":
			self.sub = "to"
		else:
			return
		self.updateRoster("unsubscribe")

	def syncGroups(self, groups, push=True):
		""" Set the groups that this contact is in on the legacy service.
		By default this pushes the groups out with a presence subscribed packet. """
		self.groups = groups
		if push: self.updateRoster("subscribed");
	
	def contactGrantsAuth(self):
		""" Live roster event """
		if self.sub == "none":
			self.sub = "to"
		elif self.sub == "from":
			self.sub = "both"
		self.sendSub("subscribed")
		self.sendPresence()
	
	def contactRemovesAuth(self):
		""" Live roster event """
		if self.sub == "to":
			self.sub = "none"
		elif self.sub == "both":
			self.sub = "from"
		self.sendSub("unsubscribed")
	
	def contactRequestsAuth(self):
		""" Live roster event """
		self.sendSub("subscribe")
	
	def contactDerequestsAuth(self):
		""" Live roster event """
		self.sendSub("unsubscribe")
	
	def jabberSubscriptionReceived(self, subtype):
		""" Updates the subscription state internally and pushes the update to the legacy server """
		if subtype == "subscribe":
			if self.sub == "to" or self.sub == "both":
				self.sendSub("subscribed")
			self.contactList.legacyList.addContact(self.jid)

		elif subtype == "subscribed":
			if self.sub == "none":
				self.sub = "from"
			if self.sub == "to":
				self.sub = "both"
			self.contactList.legacyList.authContact(self.jid)

		elif(subtype == "unsubscribe"):
			if self.sub == "none" and self.sub == "from":
				self.sendSub("unsubscribed")
			if self.sub == "both":
				self.sub = "from"
			if self.sub == "to":
				self.sub = "none"
			self.contactList.legacyList.removeContact(self.jid)

		elif(subtype == "unsubscribed"):
			if self.sub == "both":
				self.sub = "to"
			if self.sub == "from":
				self.sub = "none"
			self.contactList.legacyList.deauthContact(self.jid)

	def updateNickname(self, nickname, push=True):
		try:
			decodednickname = unicode(self.nickname, errors='replace')
		except:
			decodednickname = self.nickname
		if decodednickname != "nickname":
			self.nickname = nickname
			# will re-remove this if it's removed from JEP-0172.
			#self.sendNickname()
			if push: self.sendPresence()

			#n = Element((None, "nick"))
			#n.attributes["xmlns"] = globals.NICK
			#n.addContent(nickname)
			#self.contactList.session.pytrans.pubsub.localPublish(self.jid, globals.NICK, "current", n)
	
	def updatePresence(self, show, status, ptype, force=False, tojid=None, url=None):
		updateFlag = (self.show != show or self.status != status or self.ptype != ptype or force)
		self.show = show
		self.status = status
		self.ptype = ptype
		self.url = url
		if updateFlag:
			self.sendPresence(tojid)
	
	def updateAvatar(self, avatar=None, push=True):
		if config.disableAvatars: return
		if self.avatar == avatar: return
		self.avatar = avatar
		if push: self.sendPresence()

		#if self.avatar and not config.disableAvatars and not config.disablePEPAvatars:
			#avatarHash = self.avatar.getImageHash()
			#avatarData = self.avatar.getImageData()
			#inbuff = StringIO.StringIO(avatarData)
                        #img = Image.open(inbuff)

			#d = Element((None, "data"))
			#d.attributes["xmlns"] = globals.AVATARDATA
			#d.addContent(base64.encodestring(avatarData).replace("\n",""))
			#self.contactList.session.pytrans.pubsub.localPublish(self.jid, globals.AVATARDATA, avatarHash, d)

			#m = Element((None, "metadata"))
			#m.attributes["xmlns"] = globals.AVATARMETADATA
			#mi = m.addElement("info")
			#mi.attributes["id"] = avatarHash
			#mi.attributes["type"] = "image/png"
			#mi.attributes["bytes"] = str(len(avatarData))
			#mi.attributes["height"] = str(img.size[0])
			#mi.attributes["width"] = str(img.size[1])
			#self.contactList.session.pytrans.pubsub.localPublish(self.jid, globals.AVATARMETADATA, avatarHash, m)
	
	def sendSub(self, ptype):
		self.contactList.session.sendPresence(to=self.contactList.session.jabberID, fro=self.jid, ptype=ptype)

	def sendNickname(self, tojid=None):
		if not tojid:
			tojid=self.contactList.session.jabberID
		if self.nickname:
			el = Element((None, "message"))
			el.attributes["to"] = tojid
			el.attributes["from"] = self.jid
			nick = el.addElement("nick")
			nick.attributes["xmlns"] = globals.NICK
			nick.addContent(self.nickname)
			self.contactList.session.pytrans.send(el)
	
	def sendPresence(self, tojid=None):
		avatarHash = ""
		if self.avatar and not config.disableAvatars:
			avatarHash = self.avatar.getImageHash()
		caps = Element((None, "c"))
		caps.attributes["xmlns"] = globals.CAPS
		caps.attributes["node"] = legacy.url + "/protocol/caps"
		caps.attributes["ver"] = legacy.version
		if not tojid:
			tojid=self.contactList.session.jabberID
		self.contactList.session.sendPresence(to=tojid, fro=self.jid, ptype=self.ptype, show=self.show, status=self.status, avatarHash=avatarHash, nickname=self.nickname, payload=[caps], url=self.url)
	
	def updateRoster(self, ptype):
		self.contactList.session.sendRosterImport(jid=self.jid, ptype=ptype, sub=self.sub, groups=self.groups)

	def fillvCard(self, vCard, jid):
		if self.nickname:
			NICKNAME = vCard.addElement("NICKNAME")
			NICKNAME.addContent(self.nickname)
		if self.avatar and not config.disableAvatars and not config.disableVCardAvatars:
			PHOTO = self.avatar.makePhotoElement()
			vCard.addChild(PHOTO)
		user = jid.split('@')[0]
		return self.contactList.session.legacycon.jabberVCardRequest(vCard, user)


class ContactList:
	""" Represents the Jabber contact list """
	def __init__(self, session):
		LogEvent(INFO, session.jabberID)
		self.session = session
		self.contacts = {}
	
	def removeMe(self):
		""" Cleanly removes the object """
		LogEvent(INFO, self.session.jabberID)
		for jid in self.contacts:
			self.contacts[jid].updatePresence("", "", "unavailable")
			self.contacts[jid].removeMe()
		self.contacts = {}
		self.session = None
		self.legacyList = None
	
	def resendLists(self, tojid=None):
		for jid in self.contacts:
			if self.contacts[jid].status != "unavailable":
				self.contacts[jid].sendPresence(tojid)
		LogEvent(INFO, self.session.jabberID)
	
	def createContact(self, jid, sub):
		""" Creates a contact object. Use this to initialise the contact list
		Returns a Contact object which you can call sync* methods on to synchronise
		the user's legacy contact list with their Jabber list """
		LogEvent(INFO, self.session.jabberID)
		c = Contact(jid, sub, self)
		self.contacts[jid] = c
		return c
	
	def getContact(self, jid):
		""" Finds the contact. If one doesn't exist then a new one is created, with sub set to "none" """
		if not self.contacts.has_key(jid):
			self.contacts[jid] = Contact(jid, "none", self)
		return self.contacts[jid]
	
	def findContact(self, jid):
		if self.contacts.has_key(jid):
			return self.contacts[jid]
		return None
	
	def jabberSubscriptionReceived(self, jid, subtype):
		self.getContact(jid).jabberSubscriptionReceived(subtype)
	

