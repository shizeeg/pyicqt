# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
import config
import lang
from debug import LogEvent, INFO, WARN, ERROR
import globals

class IqAvatarFactory:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		if not config.disableAvatars and not config.disableIQAvatars:
			self.pytrans.disco.addFeature(globals.IQAVATAR, self.incomingIq, "USER")
			self.pytrans.disco.addFeature(globals.STORAGEAVATAR, self.incomingIq, "USER")

	def incomingIq(self, el):
		itype = el.getAttribute("type")
		fro = el.getAttribute("from")
		froj = internJID(fro)
		to = el.getAttribute("to")
		ID = el.getAttribute("id")
		for query in el.elements():
			if(query.name == "query"):
				xmlns = query.uri
		if not xmlns:
			self.pytrans.iq.sendIqError(to=fro, fro=config.jid, ID=ID, xmlns=xmlns, etype="cancel", condition="bad-request")
			return
		if itype != "get" and itype != "error":
			self.pytrans.iq.sendIqError(to=fro, fro=config.jid, ID=ID, xmlns=xmlns, etype="cancel", condition="feature-not-implemented")
			return

		LogEvent(INFO, msg="Retrieving avatar")

		if not self.pytrans.sessions.has_key(froj.userhost()):
			self.pytrans.iq.sendIqError(to=fro, fro=config.jid, ID=ID, xmlns=xmlns, etype="auth", condition="not-authorized")
			return
		s = self.pytrans.sessions[froj.userhost()]
		if not s.ready:
			self.pytrans.iq.sendIqError(to=fro, fro=config.jid, ID=ID, xmlns=xmlns, etype="auth", condition="not-authorized")
			return

		c = s.contactList.findContact(to)
		if not c:
			self.pytrans.iq.sendIqError(to=fro, fro=config.jid, ID=ID, xmlns=xmlns, etype="cancel", condition="recipient-unavailable")
			return

		iq = Element((None, "iq"))
		iq.attributes["to"] = fro
		iq.attributes["from"] = to
		iq.attributes["id"] = ID
		iq.attributes["type"] = "result"
		query = iq.addElement("query")
		query.attributes["xmlns"] = xmlns
		if c.avatar:
			DATA = c.avatar.makeDataElement()
			query.addChild(DATA)

		self.pytrans.send(iq)
