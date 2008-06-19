# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import config
import utils
import legacy
import jabw
import contact
import avatar
import globals
from debug import LogEvent, INFO, WARN, ERROR
import lang
from twisted.words.protocols.jabber.jid import internJID



def makeSession(pytrans, jabberID, ulang, rosterID):
	""" Tries to create a session object for the corresponding JabberID. Retrieves information
	from XDB to create the session. If it fails, then the user is most likely not registered with
	the transport """
	LogEvent(INFO, jabberID)
	if pytrans.sessions.has_key(jabberID):
		LogEvent(INFO, jabberID, "Removing existing session")
		pytrans.sessions[jabberID].removeMe()
	result = pytrans.xdb.getRegistration(jabberID)
	if result:
		username, password = result
		return Session(pytrans, jabberID, username, password, ulang, rosterID)
	else:
		return None



class Session(jabw.JabberConnection):
	""" A class to represent each registered user's session with the legacy network. Exists as long as there
	is a Jabber resource for the user available """
	
	def __init__(self, pytrans, jabberID, username, password, ulang, rosterID):
		""" Initialises the session object and connects to the legacy network """
		jabw.JabberConnection.__init__(self, pytrans, jabberID)
		LogEvent(INFO, jabberID)
		
		self.pytrans = pytrans
		self.alive = True
		self.ready = False # Only ready when we're logged into the legacy service
		self.jabberID = jabberID # the JabberID of the Session's user
		self.username = username # the legacy network ID of the Session's user
		self.password = password
		self.description = None
		self.nickname = None
		self.nicknamePri = 0	# priority of nickname:
					# 0 = no nickname
					# 1 = vcard based nickname
					# 2 = pep based nickname
		self.avatar = None
		self.avatarPri = 0	# priority of avatar:
					# 0 = no avatar
					# 1 = default avatar
					# 2 = vcard based avatar
					# 3 = iq based avatar
					# 4 = pep based avatar
		self.lang = ulang

		if rosterID.resource == "registered":
			self.registeredmunge = True
		else:
			self.registeredmunge = False

		self.show = None
		self.status = None
		self.url = None
		
		self.resourceList = {}
		self.capabilities = []
		
		self.contactList = contact.ContactList(self)
		self.legacycon = legacy.LegacyConnection(self.username, self.password, self)
		self.pytrans.legacycon = self.legacycon
		self.contactList.legacyList = self.legacycon.legacyList

		if config.sessionGreeting:
			self.sendMessage(to=self.jabberID, fro=config.jid, body=config.sessionGreeting)
		# Set default avatar to start with, should do this better
		self.legacycon.updateAvatar()
		self.avatarPri = 1
		self.updateNickname(self.nickname)
		self.updateDescription(self.description)
		self.doVCardUpdate()
		if not config.disableIQAvatars:
			self.doIQAvatarUpdate()
		self.doDiscoRequest()
		LogEvent(INFO, self.jabberID, "Created!")

		self.pytrans.serviceplugins['Statistics'].stats["TotalSessions"] += 1
		self.pytrans.serviceplugins['Statistics'].stats["OnlineSessions"] += 1
		if len(self.pytrans.sessions)+1 > self.pytrans.serviceplugins['Statistics'].stats["MaxConcurrentSessions"]:
			self.pytrans.serviceplugins['Statistics'].stats["MaxConcurrentSessions"] = len(self.pytrans.sessions)+1
		self.pytrans.serviceplugins['Statistics'].sessionUpdate(self.jabberID, "Connections", 1)
	
	def removeMe(self):
		""" Safely removes the session object, including sending <presence type="unavailable"/> messages for each legacy related item on the user's contact list """
		# Send offline presence to Jabber ID
		# Delete all objects cleanly
		# Remove this Session object from the pytrans
		
		LogEvent(INFO, self.jabberID)
		
		# Mark as dead
		self.alive = False
		self.ready = False
		
		# Send offline presence to the user
		if self.pytrans:
			tmpjid = config.jid
			if self.registeredmunge:
				tmpjid = tmpjid + "/registered"
			self.sendPresence(to=self.jabberID, fro=tmpjid, ptype="unavailable")
			self.pytrans.serviceplugins['Statistics'].stats["OnlineSessions"] -= 1

		# Clean up stuff on the legacy service end (including sending offline presences for all contacts)
		if self.legacycon:
			self.legacycon.removeMe()
			self.legacycon = None

		if self.contactList:
			self.contactList.removeMe()
			self.contactList = None

		if self.pytrans:
			# Remove us from the session list
			del self.pytrans.sessions[self.jabberID]
			# Clean up the no longer needed reference
			self.pytrans = None
		
		LogEvent(INFO, self.jabberID, "Removed!")

	def hasCapability(self, capability):
		for c in self.capabilities:
			if c == capability:
				return True
		return False

	def doDiscoRequest(self):
		def userDiscoInfoReceived(el):
			if not self.alive: return
			LogEvent(INFO, self.jabberID)
			fro = el.getAttribute("from")
			for e in el.elements():
				if e.name == "query" and e.uri == globals.DISCO_INFO:
					for item in e.elements():
						if item.name == "feature":
							var = item.getAttribute("var")
							self.capabilities.append(var)
			LogEvent(INFO, self.jabberID, "Capabilities of %r:\n\t%s" % (fro, "\n\t".join(self.capabilities)))

		def serverDiscoInfoReceived(el):
			if not self.alive: return
			LogEvent(INFO, self.jabberID)
			fro = el.getAttribute("from")
			for e in el.elements():
				if e.name == "query" and e.uri == globals.DISCO_INFO:
					for item in e.elements():
						if item.name == "feature":
							var = item.getAttribute("var")
							self.capabilities.append(var)
			LogEvent(INFO, self.jabberID, "Capabilities of %r:\n\t%s" % (fro, "\n\t".join(self.capabilities)))

		def errback(args=None):
			LogEvent(INFO, self.jabberID, "Error fetching disco info")

		LogEvent(INFO, self.jabberID, "Fetching disco info from %r" % self.jabberID)
		d = self.sendDiscoRequest(to=self.jabberID, fro=config.jid)
		d.addCallback(userDiscoInfoReceived)
		d.addErrback(errback)

		sjid = internJID(self.jabberID).host
		LogEvent(INFO, self.jabberID, "Fetching disco info from %r" % sjid)
		d = self.sendDiscoRequest(to=sjid, fro=config.jid)
		d.addCallback(serverDiscoInfoReceived)
		d.addErrback(errback)

	def doVCardUpdate(self):
		def vCardReceived(el):
			if not self.alive: return
			LogEvent(INFO, self.jabberID)
			vCard = None
			for e in el.elements():
				if e.name == "vCard" and e.uri == globals.VCARD:
					vCard = e
					break
			if not vCard:
				return
			for e in vCard.elements():
				if e.name == "DESC":
					self.updateDescription(e.__str__())
				if e.name == "NICKNAME" and self.nicknamePri < 1:
					self.updateNickname(e.__str__())
					self.nicknamePri = 1
				if e.name == "PHOTO" and not config.disableAvatars and not config.disableVCardAvatars and self.avatarPri < 2:
					imageData = avatar.parsePhotoEl(e)
					if not imageData:
						errback(Exception("Invalid image data")) # Possibly it wasn't in a supported format?
					self.avatar = self.pytrans.avatarCache.setAvatar(imageData)
					self.legacycon.updateAvatar(self.avatar)
					self.avatarPri = 2

		def errback(args=None):
			LogEvent(INFO, self.jabberID, "Error fetching vcard (avatar)")

		LogEvent(INFO, self.jabberID, "Fetching vcard")
		d = self.sendVCardRequest(to=self.jabberID, fro=config.jid)
		d.addCallback(vCardReceived)
		d.addErrback(errback)

	def doIQAvatarUpdate(self):
		if config.disableAvatars or config.disableIQAvatars: return

		def errback(args=None):
			LogEvent(INFO, self.jabberID, "Error fetching IQ-based avatar")

		def storageAvatarReceived(el):
			if not self.alive: return
			LogEvent(INFO, self.jabberID)
			qtype = el.getAttribute("type")
			if qtype == "error": return
			query = None
			for e in el.elements():
				if e.name == "query" and e.uri == globals.STORAGEAVATAR:
					query = e
					break
			if not query:
				return
			for e in query.elements():
				if e.name == "data" and self.avatarPri < 3:
					imageData = avatar.parseIQPhotoEl(e)
					if not imageData:
						errback(Exception("Invalid image data")) # Possibly it wasn't in a supported format?
					self.avatar = self.pytrans.avatarCache.setAvatar(imageData)
					self.legacycon.updateAvatar(self.avatar)
					self.avatarPri = 3

		def iqAvatarReceived(el):
			if not self.alive: return
			LogEvent(INFO, self.jabberID)
			qtype = el.getAttribute("type")
			if qtype == "error":
				LogEvent(INFO, self.jabberID, "That didn't work, let's try an IQ-storage-based avatar")
				d = self.sendStorageAvatarRequest(to=self.jabberID, fro=config.jid)
				d.addCallback(storageAvatarReceived)
				d.addErrback(errback)
				
			query = None
			for e in el.elements():
				if e.name == "query" and e.uri == globals.IQAVATAR:
					query = e
					break
			if not query:
				return
			for e in query.elements():
				if e.name == "data" and self.avatarPri < 3:
					imageData = avatar.parseIQPhotoEl(e)
					if not imageData:
						errback(Exception("Invalid image data")) # Possibly it wasn't in a supported format?
					self.avatar = self.pytrans.avatarCache.setAvatar(imageData)
					self.legacycon.updateAvatar(self.avatar)
					self.avatarPri = 3

		LogEvent(INFO, self.jabberID, "Fetching IQ-based avatar")
		highestActive = self.highestResource()
		if not highestActive: return
		d = self.sendIQAvatarRequest(to=self.jabberID+"/"+highestActive, fro=config.jid)
		d.addCallback(iqAvatarReceived)
		d.addErrback(errback)

	def updateNickname(self, nickname):
		self.nickname = nickname
		if not self.nickname:
			j = internJID(self.jabberID)
			self.nickname = j.user
		self.setStatus(self.show, self.status, self.url)

	def updateDescription(self, description):
		self.description = description
		if not self.description:
			self.description = "I am a PyICQ-t user with no profile set."

	def setStatus(self, show, status, url=None):
		self.show = show
		self.status = status
		self.url = url
		self.legacycon.setStatus(self.nickname, show, status, url)
	
	def sendNotReadyError(self, source, resource, dest, body):
		self.sendErrorMessage(source + '/' + resource, dest, "wait", "not-allowed", lang.get("waitforlogin", self.lang), body)
	
	def nicknameReceived(self, source, dest, nickname):
		if dest.find('@') > 0: return # Ignore presence packets sent to users
        
		self.updateNickname(nickname)

	def avatarHashReceived(self, source, dest, avatarHash, avatarType="vcard"):
		if config.disableAvatars: return
		if dest.find('@') > 0: return # Ignore presence packets sent to users

		if avatarHash == " ": # Setting no avatar
			self.legacycon.updateAvatar() # Default
		elif not self.avatar or (self.avatar and self.avatar.getImageHash() != avatarHash):
			av = self.pytrans.avatarCache.getAvatar(avatarHash)
			if av:
				self.avatar = av # Stuff in the cache is always PNG
				self.legacycon.updateAvatar(self.avatar)
			else:
				if avatarType == "vcard" and not config.disableVCardAvatars:
					self.doVCardUpdate()
				elif avatarType == "iq" and not config.disableIQAvatars:
					self.doIQAvatarUpdate()

	def messageReceived(self, source, resource, dest, destr, mtype, body, noerror, xhtml, autoResponse=0):
		if dest == config.jid:
			if body.lower().startswith("end"):
				LogEvent(INFO, self.jabberID, "Received 'end' request")
				self.removeMe()
			return

		if not self.ready:
			self.sendNotReadyError(source, resource, dest, body)
			return
		
		LogEvent(INFO, self.jabberID, "Message")
		self.legacycon.sendMessage(dest, resource, body, noerror, xhtml, autoResponse=autoResponse)
	
	def typingNotificationReceived(self, dest, resource, composing):
		""" The user has sent typing notification to a contact on the legacy service """
		self.legacycon.userTypingNotification(dest, resource, composing)

	def chatStateReceived(self, dest, resource, state):
		""" The user has sent a chat state notification to a contact on the legacy service """
		self.legacycon.chatStateNotification(dest, resource, state)
	
	def presenceReceived(self, source, resource, to, tor, priority, ptype, show, status, url=None):
		# Checks resources and priorities so that the highest priority resource always appears as the
		# legacy services status. If there are no more resources then the session is deleted
		if ptype == 'probe':
			LogEvent(INFO, self.jabberID, "Responding to presence probe")
			if to == config.jid:
				self.legacycon.sendShowStatus(source)
			else:
				self.contactList.getContact(to).sendPresence(source)
		else:
			self.handleResourcePresence(source, resource, to, tor, priority, ptype, show, status, url)

		
	def handleResourcePresence(self, source, resource, to, tor, priority, ptype, show, status, url):
		if ptype and ptype != "unavailable": return # Ignore presence errors, probes, etc
		if to.find('@') > 0: return # Ignore presence packets sent to users

		existing = self.resourceList.has_key(resource)
		if ptype == "unavailable":
			if existing:
				LogEvent(INFO, self.jabberID, "Resource gone offline")
				self.resourceOffline(resource)
			else:
				return # I don't know the resource, and they're leaving, so it's all good
		else:
			if not existing:
				LogEvent(INFO, self.jabberID, "Resource came online")
				self.contactList.resendLists("%s/%s"%(source,resource))
			LogEvent(INFO, self.jabberID, "Setting status")
			self.resourceList[resource] = SessionResource(show, status, priority, url)

		highestActive = self.highestResource()

		if highestActive:
			# If we're the highest active resource, we should update the legacy service
			LogEvent(INFO, self.jabberID, "Updating status on legacy service")
			r = self.resourceList[highestActive]
			self.setStatus(r.show, r.status, r.url)
		else:
			LogEvent(INFO, self.jabberID, "Last resource died.  Calling removeMe in 0 seconds")
			#reactor.callLater(0, self.removeMe)
			self.removeMe()
			#FIXME Which of the above?

	def highestResource(self):
		""" Returns the highest priority resource """
		highestActive = None
		for checkR in self.resourceList.keys():
			if highestActive == None or self.resourceList[checkR].priority > self.resourceList[highestActive].priority: 
				highestActive = checkR

		#if highestActive:
		#	debug.log("Session %r - highest active resource is \"%r\" at %d" % (self.jabberID, highestActive, self.resourceList[highestActive].priority))

		return highestActive

	def resourceOffline(self, resource):
		del self.resourceList[resource]
		self.legacycon.resourceOffline(resource)

	def subscriptionReceived(self, to, subtype):
		""" Sends the subscription request to the legacy services handler """
		if to.find('@') > 0:
			LogEvent(INFO, self.jabberID, "Passing subscription to legacy service")
			self.contactList.jabberSubscriptionReceived(to, subtype)
		else:
			if subtype == "subscribe":
				self.sendPresence(to=self.jabberID, fro=config.jid, ptype="subscribed")
			elif subtype.startswith("unsubscribe"):
				# They want to unregister.
				jid = self.jabberID
				LogEvent(INFO, jid, "About to register")
				self.pytrans.registermanager.removeRegInfo(jid)
				LogEvent(INFO, jid, "Just unregistered")




class SessionResource:
	""" A convienence class to allow comparisons of Jabber resources """
	def __init__(self, show=None, status=None, priority=None, url=None):
		self.show = show
		self.status = status
		self.priority = 0
		self.url = url
		try:
			self.priority = int(priority)
		except TypeError: pass
		except ValueError: pass
