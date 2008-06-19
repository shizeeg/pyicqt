# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
from debug import LogEvent, INFO, WARN, ERROR
import config
import disco
import globals


def sendMessage(pytrans, to, fro, body, mtype=None, delay=None, xhtml=None, nickname=None):
	""" Sends a Jabber message """
	LogEvent(INFO)
	el = Element((None, "message"))
	el.attributes["to"] = to
	el.attributes["from"] = fro
	el.attributes["id"] = pytrans.makeMessageID()
	if mtype:
		el.attributes["type"] = mtype

	if delay:
		x = el.addElement("x")
		x.attributes["xmlns"] = globals.XDELAY
		x.attributes["from"] = fro
		x.attributes["stamp"] = delay

	if nickname:
		n = el.addElement("nick")
		n.attributes["xmlns"] = globals.NICK
		n.addContent(nickname)

	b = el.addElement("body")
	b.addContent(utils.xmlify(body))
	x = el.addElement("x")
	x.attributes["xmlns"] = globals.XEVENT
	composing = x.addElement("composing")
	xx = el.addElement("active")
	xx.attributes["xmlns"] = globals.CHATSTATES

	if xhtml and not config.disableXHTML:
		try:
			el.addChild(utils.parseText(xhtml))
		except:
			# Hrm, didn't add, we're not going to end the world
			# because of it.
			pass

	pytrans.send(el)
	sendArchive(pytrans, to, fro, body)

def sendPresence(pytrans, to, fro, show=None, status=None, priority=None, ptype=None, avatarHash=None, nickname=None, payload=[], url=None):
	if ptype in ["subscribe", "subscribed", "unsubscribe", "unsubscribed"]:
		to = internJID(to).userhost()
		fro = internJID(fro).userhost()

	el = Element((None, "presence"))
	el.attributes["to"] = to
	el.attributes["from"] = fro
	if ptype:
		el.attributes["type"] = ptype
	if show:
		s = el.addElement("show")
		s.addContent(utils.xmlify(show))
	if status:
		s = el.addElement("status")
		s.addContent(utils.xmlify(status))
	if priority:
		s = el.addElement("priority")
		s.addContent(priority)
	if url:
		s = el.addElement("x")
		s.attributes["xmlns"] = globals.XOOB
		s = el.addElement("url")
		s.addContent(url)

	if not ptype:
		if avatarHash and not config.disableAvatars and not config.disableVCardAvatars:
			x = el.addElement("x")
			x.attributes["xmlns"] = globals.VCARDUPDATE
			p = x.addElement("photo")
			p.addContent(avatarHash)

		if nickname:
			x = el.addElement("x")
			x.attributes["xmlns"] = globals.VCARDUPDATE
			n = x.addElement("nickname")
			n.addContent(nickname)

		if avatarHash and not config.disableAvatars and not config.disableIQAvatars:
			x = el.addElement("x")
			x.attributes["xmlns"] = globals.XAVATAR
			h = x.addElement("hash")
			h.addContent(avatarHash)

		if nickname and ptype == "subscribe":
			n = el.addElement("nick")
			n.attributes["xmlns"] = globals.NICK
			n.addContent(nickname)

	if payload:
		for p in payload:
			el.addChild(p)

	pytrans.send(el)

def sendErrorMessage(pytrans, to, fro, etype, condition, explanation, body=None, el=None):
	if el is None:
		el = Element((None, "message"))
	el.attributes["to"] = to
	el.attributes["from"] = fro
	el.attributes["type"] = "error"
	error = el.addElement("error")
	error.attributes["type"] = etype
	error.attributes["code"] = str(utils.errorCodeMap[condition])
	if condition:
		desc = error.addElement(condition)
		desc.attributes["xmlns"] = globals.XMPP_STANZAS
	text = error.addElement("text")
	text.attributes["xmlns"] = globals.XMPP_STANZAS
	text.addContent(explanation)

	if body and len(body) > 0:
		b = el.addElement("body")
		b.addContent(body)
	pytrans.send(el)

def sendArchive(pytrans, to, fro, body):
	""" Archive Jabber message if archive element set in config.xml """
	""" send iq xml packet to server specified in archive element """
	""" Configured for DataSink """
	""" THIS IS NOT COMPLIANT WITH JEP-0136 """
	if config.messageArchiveJID:
		LogEvent(INFO) 
		iq = Element((None, "iq"))
		iq.attributes["type"] = "set"
		iq.attributes["from"] = to
		iq.attributes["to"] = config.messageArchiveJID
		myarchive = iq.addElement("archive")
		mymessage = myarchive.addElement("message")
		mymessage.attributes["to"] = to
		mymessage.attributes["from"] = fro
		mybody = mymessage.addElement("body")
		mybody.addContent(utils.xmlify(body))
		pytrans.iq.sendIq(iq)




class JabberConnection:
	""" A class to handle a Jabber "Connection", ie, the Jabber side of the gateway.
	If you want to send a Jabber event, this is the place, and this is where incoming
	Jabber events for a session come to. """
	
	def __init__(self, pytrans, jabberID):
		self.pytrans = pytrans
		self.jabberID = jabberID
		self.last_el = dict()
		self.typingUser = False # Whether this user can accept typing notifications.
		self.chatStateUser = False # Whether this user can accept chat state notifications.
		self.messageIDs = dict() # The ID of the last message the user sent to a particular contact. Indexed by contact JID
		LogEvent(INFO, self.jabberID)
	
	def removeMe(self):
		""" Cleanly deletes the object """
		LogEvent(INFO, self.jabberID)
	
	def checkFrom(self, el):
		""" Checks to see that this packet was intended for this object """
		fro = el.getAttribute("from")
		froj = internJID(fro)
		
		return (froj.userhost() == self.jabberID) # Compare with the Jabber ID that we're looking at
	
	def sendMessage(self, to, fro, body, mtype=None, delay=None, xhtml=None, nickname=None):
		""" Sends a Jabber message 
		For this message to have a <x xmlns="jabber:x:delay"/>
		you must pass a correctly formatted timestamp (See JEP0091)
		"""
		LogEvent(INFO, self.jabberID)
		if xhtml and not self.hasCapability(globals.XHTML):
			# User doesn't support XHTML, so kill it.
			xhtml = None
		sendMessage(self.pytrans, to, fro, body, mtype, delay, xhtml, nickname)

	def sendArchive(self, to, fro, body):
		""" Sends an Archive message (see JEP-0136) """
		LogEvent(INFO, self.jabberID)
		sendArchive(self.pytrans, to, fro, body)

	def sendTypingNotification(self, to, fro, typing):
		""" Sends the user the contact's current typing notification status """
		if self.typingUser:
			LogEvent(INFO, self.jabberID)
			el = Element((None, "message"))
			el.attributes["to"] = to
			el.attributes["from"] = fro
			x = el.addElement("x")
			x.attributes["xmlns"] = globals.XEVENT
			if typing:
				composing = x.addElement("composing") 
			id = x.addElement("id")
			if self.messageIDs.has_key(fro) and self.messageIDs[fro]:
				id.addContent(self.messageIDs[fro])
			self.pytrans.send(el)

	def sendChatStateNotification(self, to, fro, state):
		""" Sends the user the contact's chat state status """
		if self.chatStateUser:
			LogEvent(INFO, self.jabberID)
			el = Element((None, "message"))
			el.attributes["to"] = to
			el.attributes["from"] = fro
			x = el.addElement(state)
			x.attributes["xmlns"] = globals.CHATSTATES
			self.pytrans.send(el)

	def sendVCardRequest(self, to, fro):
		""" Requests the the vCard of 'to'
		Returns a Deferred which fires when the vCard has been received.
		First argument an Element object of the vCard
		"""
		el = Element((None, "iq"))
		el.attributes["to"] = to
		el.attributes["from"] = fro
		el.attributes["type"] = "get"
		el.attributes["id"] = self.pytrans.makeMessageID()
		vCard = el.addElement("vCard")
		vCard.attributes["xmlns"] = globals.VCARD
		return self.pytrans.iq.sendIq(el)

	def sendIQAvatarRequest(self, to, fro):
		""" Requests the the IQ-based avatar of 'to'
		Returns a Deferred which fires when the IQ result has been received.
		"""
		LogEvent(INFO, self.jabberID)
		el = Element((None, "iq"))
		el.attributes["to"] = to
		el.attributes["from"] = fro
		el.attributes["type"] = "get"
		el.attributes["id"] = self.pytrans.makeMessageID()
		query = el.addElement("query")
		query.attributes["xmlns"] = globals.IQAVATAR
		return self.pytrans.iq.sendIq(el)

	def sendStorageAvatarRequest(self, to, fro):
		""" Requests the the IQ-storage-based avatar of 'to'
		Returns a Deferred which fires when the IQ result has been received.
		"""
		LogEvent(INFO, self.jabberID)
		el = Element((None, "iq"))
		el.attributes["to"] = to
		el.attributes["from"] = fro
		el.attributes["type"] = "get"
		el.attributes["id"] = self.pytrans.makeMessageID()
		query = el.addElement("query")
		query.attributes["xmlns"] = globals.STORAGEAVATAR
		return self.pytrans.iq.sendIq(el)

	def sendErrorMessage(self, to, fro, etype, explanation, condition=None, body=None):
		if self.last_el.has_key(to) and self.last_el[to].attributes.has_key("from"):
			LogEvent(INFO, self.jabberID, "Using pre-existing element")
			sendErrorMessage(self.pytrans, to=to, fro=self.last_el[to].attributes["to"], etype=etype, condition=condition, explanation=explanation, body=body, el=self.last_el[to])
			del self.last_el[to]
		else:
			LogEvent(INFO, self.jabberID, "**NOT** Using pre-existing element")
			sendErrorMessage(self.pytrans, to=to, fro=fro, etype=etype, condition=condition, explanation=explanation, body=body)
	
	def sendPresence(self, to, fro, show=None, status=None, priority=None, ptype=None, avatarHash=None, nickname=None, payload=[], url=None):
		""" Sends a Jabber presence packet """
		LogEvent(INFO, self.jabberID)
		sendPresence(self.pytrans, to, fro, show, status, priority, ptype, avatarHash, nickname, payload, url=url)
	
	def sendRosterImport(self, jid, ptype, sub, name="", groups=[]):
		""" Sends a special presence packet. This will work with all clients, but clients that support roster-import will give a better user experience
		IMPORTANT - Only ever use this for contacts that have already been authorised on the legacy service """
		el = Element((None, "presence"))
		el.attributes["to"] = self.jabberID
		el.attributes["from"] = jid
		el.attributes["type"] = ptype
		r = el.addElement("x")
		r.attributes["xmlns"] = globals.SUBSYNC
		item = r.addElement("item")
		item.attributes["subscription"] = sub
		n = el.addElement("nick")
		n.attributes["xmlns"] = globals.NICK
		n.addContent(unicode(name))
		for group in groups:
			g = item.addElement("group")
			g.addContent(group)
		
		self.pytrans.send(el)

	def sendDiscoRequest(self, to, fro):
		""" Requests the capabilities of the client """
		LogEvent(INFO, self.jabberID)

		iq = Element((None, "iq"))
		iq.attributes["type"] = "get"
		iq.attributes["from"] = fro
		iq.attributes["to"] = to
		query = iq.addElement("query")
		query.attributes["xmlns"] = globals.DISCO_INFO

		return self.pytrans.iq.sendIq(iq)

	def onMessage(self, el):
		""" Handles incoming message packets """
		if not self.checkFrom(el): return
		LogEvent(INFO, self.jabberID)
		fro = el.getAttribute("from")
		to = el.getAttribute("to")
		try:
			froj = internJID(fro)
			toj = internJID(to)
		except Exception, e:
			LogEvent(WARN, self.jabberID)
			return

		self.last_el[froj.userhost()] = el
		mID = el.getAttribute("id")
		mtype = el.getAttribute("type")
		body = ""
		autoResponse = 0
		xhtml = None
		error = None
		messageEvent = False
		noerror = False
		composing = None
		chatStateEvent = None
		chatStates = None
		for child in el.elements():
			if child.name == "body":
				body = child.__str__()
			elif child.name == "error":
				error = child.__str__()
			elif child.name == "html":
				xhtml = child.toXml()
			elif child.name == "noerror" and child.uri == globals.SAPO_NOERROR:
				noerror = True
			elif child.name == "x":
				if child.uri == globals.XEVENT:
					messageEvent = True
					composing = False
					for deepchild in child.elements():
						if deepchild.name == "composing":
							composing = True
							break
			elif child.name == "composing" or child.name == "active" or child.name == "paused" or child.name == "inactive" or child.name == "gone":
				if child.uri==globals.CHATSTATES:
					chatStates = True
					chatStateEvent = child.name
		
		if error:
			body = error
			xhtml = None
			autoResponse = 1
			LogEvent(WARN, self.jabberID, "Got error jabber packet")

		# Check message event stuff
		if body and chatStates:
			self.chatStateUser = True
		elif body and messageEvent:
			self.typingUser = True
		elif body and not messageEvent and not chatStates:
			self.typingUser = False
			self.chatStateUser = False
		elif not body and chatStateEvent:
			LogEvent(INFO, self.jabberID, "Chat state notification %r" % chatStateEvent)
			self.chatStateReceived(toj.userhost(), toj.resource, chatStateEvent)
		elif not body and messageEvent:
			LogEvent(INFO, self.jabberID, "Typing notification %r" % composing)
			self.typingNotificationReceived(toj.userhost(), toj.resource, composing)

		if body:
			# Save the message ID for later
			self.messageIDs[to] = mID
			LogEvent(INFO, self.jabberID, "Message packet")
			self.messageReceived(froj.userhost(), froj.resource, toj.userhost(), toj.resource, mtype, body, noerror, xhtml, autoResponse=autoResponse)
	
	def onPresence(self, el):
		""" Handles incoming presence packets """
		if not self.checkFrom(el): return
		LogEvent(INFO, self.jabberID)
		fro = el.getAttribute("from")
		froj = internJID(fro)
		to = el.getAttribute("to")
		toj = internJID(to)
		
		# Grab the contents of the <presence/> packet
		ptype = el.getAttribute("type")
		if ptype and (ptype.startswith("subscribe") or ptype.startswith("unsubscribe")):
			LogEvent(INFO, self.jabberID, "Parsed subscription presence packet")
			self.subscriptionReceived(toj.userhost(), ptype)
		else:
			status = None
			show = None
			priority = None
			avatarHash = ""
			nickname = ""
			url = None
			avatarType = ""
			for child in el.elements():
				if child.name == "status":
					status = child.__str__()
				elif child.name == "show":
					show = child.__str__()
				elif child.name == "priority":
					priority = child.__str__()
				elif child.uri == globals.TUNE:
					for child2 in child.elements():
						if child2.uri == globals.XOOB:
							for child3 in child2.elements():
								if child3.name == "url":
									url=child3.__str__()
				elif child.uri == globals.XOOB:
					for child2 in child.elements():
						if child2.name == "url":
							url=child2.__str__()
				elif child.uri == globals.VCARDUPDATE and not config.disableAvatars:
					avatarHash = " "
					for child2 in child.elements():
						if child2.name == "photo":
							avatarHash = child2.__str__()
						if child2.name == "nickname":
							nickname = child2.__str__()
							avatarType = "vcard"
				elif child.uri == globals.XAVATAR and not config.disableAvatars:
					avatarHash = " "
					for child2 in child.elements():
						if child2.name == "hash":
							avatarHash = child2.__str__()
							avatarType = "iq"

			if not ptype:
				# ptype == None
				if avatarHash and not config.disableAvatars:
					self.avatarHashReceived(froj.userhost(), toj.userhost(), avatarHash, avatarType)
				if nickname:
					self.nicknameReceived(froj.userhost(), toj.userhost(), nickname)

			LogEvent(INFO, self.jabberID, "Parsed presence packet")
			self.presenceReceived(froj.userhost(), froj.resource, toj.userhost(), toj.resource, priority, ptype, show, status)
	
	
	
	def messageReceived(self, source, resource, dest, destr, mtype, body, noerror, xhtml, autoResponse=0):
		""" Override this method to be notified when a message is received """
		pass
	
	def presenceReceived(self, source, resource, to, tor, priority, ptype, show, status, url=None):
		""" Override this method to be notified when presence is received """
		pass
	
	def subscriptionReceived(self, source, subtype):
		""" Override this method to be notified when a subscription packet is received """
		pass

	def nicknameReceived(self, source, dest, nickname):
		""" Override this method to be notified when a nickname has been received """
		pass

	def avatarHashReceived(self, source, dest, avatarHash):
		""" Override this method to be notified when an avatar hash is received """
		pass
