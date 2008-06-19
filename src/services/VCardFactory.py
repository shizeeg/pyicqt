# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
import legacy
import config
import lang
from debug import LogEvent, INFO, WARN, ERROR
import globals

class VCardFactory:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.disco.addFeature(globals.VCARD, self.incomingIq, "USER")
		self.pytrans.disco.addFeature(globals.VCARD, self.incomingIq, config.jid)
		self.pytrans.adhoc.addCommand("updatemyvcard", self.getMyVCard, "command_UpdateMyVCard")

	def incomingIq(self, el):
		itype = el.getAttribute("type")
		fro = el.getAttribute("from")
		froj = internJID(fro)
		to = el.getAttribute("to")
		ID = el.getAttribute("id")
		filter = None
		if itype != "get" and itype != "error":
			self.pytrans.iq.sendIqError(to=fro, fro=config.jid, ID=ID, xmlns="vcard-temp", etype="cancel", condition="feature-not-implemented")
			return

		LogEvent(INFO, msg="Sending vCard")

		for child in el.elements():
			if child.name == "vCard" and child.uri == globals.VCARD:
				for child2 in child.elements():
					if child2.name == "filter" and child2.uri == globals.VCARDFILTER:
						filter = child2
						break
				break

		toGateway = not (to.find('@') > 0)
		if not toGateway:
			if not self.pytrans.sessions.has_key(froj.userhost()):
				self.pytrans.iq.sendIqError(to=fro, fro=config.jid, ID=ID, xmlns="vcard-temp", etype="auth", condition="not-authorized")
				return
			s = self.pytrans.sessions[froj.userhost()]
			if not s.ready:
				self.pytrans.iq.sendIqError(to=fro, fro=config.jid, ID=ID, xmlns="vcard-temp", etype="auth", condition="not-authorized")
				return

			c = s.contactList.findContact(to)
			if not c:
				iq = Element((None, "iq"))
				iq.attributes["to"] = fro
				iq.attributes["from"] = to
				iq.attributes["id"] = ID
				iq.attributes["type"] = "result"
				vCard = iq.addElement("vCard")
				vCard.attributes["xmlns"] = globals.VCARD
				self.pytrans.legacycon.getvCardNotInList(vCard, to).addCallback(self.gotvCardResponse, iq, filter)
				return
				# Lets leave this up to the legacy pieces
				#self.pytrans.iq.sendIqError(to=fro, fro=config.jid, ID=ID, xmlns="vcard-temp", etype="cancel", condition="recipient-unavailable")


		iq = Element((None, "iq"))
		iq.attributes["to"] = fro
		iq.attributes["from"] = to
		iq.attributes["id"] = ID
		iq.attributes["type"] = "result"
		vCard = iq.addElement("vCard")
		vCard.attributes["xmlns"] = globals.VCARD
		if toGateway:
			FN = vCard.addElement("FN")
			FN.addContent(legacy.name)
			DESC = vCard.addElement("DESC")
			DESC.addContent(legacy.name)
			URL = vCard.addElement("URL")
			URL.addContent(legacy.url)

			if not config.disableAvatars and not config.disableVCardAvatars:
				from legacy import defaultAvatar
				PHOTO = defaultAvatar.makePhotoElement()
				vCard.addChild(PHOTO)

			self.pytrans.send(iq)
		else:
			c.fillvCard(vCard, to).addCallback(self.gotvCardResponse, iq, filter)

	def gotvCardResponse(self, vcard, iq, filter):
		LogEvent(INFO)
		if filter:
			for child in filter.elements():
				for vchild in vcard.elements():
					if vchild.name.lower() == child.name.lower():
						vcard.children.remove(vchild)
		self.pytrans.send(iq)

	def getMyVCard(self, el):
		to = el.getAttribute("from")
		fro = el.getAttribute("from")
		froj = internJID(fro)
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)

		if not self.pytrans.sessions.has_key(froj.userhost()):
			self.pytrans.iq.sendIqError(to=fro, fro=config.jid, ID=ID, xmlns="vcard-temp", etype="auth", condition="not-authorized")
			return
		s = self.pytrans.sessions[froj.userhost()]
		if not s.ready:
			self.pytrans.iq.sendIqError(to=fro, fro=config.jid, ID=ID, xmlns="vcard-temp", etype="auth", condition="not-authorized")
			return

		s.doVCardUpdate()

		iq = Element((None, "iq"))
		iq.attributes["to"] = to
		iq.attributes["from"] = config.jid
		if ID:
			iq.attributes["id"] = ID
		iq.attributes["type"] = "result"

		command = iq.addElement("command")
		command.attributes["sessionid"] = self.pytrans.makeMessageID()
		command.attributes["xmlns"] = globals.COMMANDS
		command.attributes["status"] = "completed"

		x = command.addElement("x")
		x.attributes["xmlns"] = globals.XDATA
		x.attributes["type"] = "result"

		title = x.addElement("title")
		title.addContent(lang.get("command_UpdateMyVCard", ulang))

		field = x.addElement("field")
		field.attributes["type"] = "fixed"
		field.addElement("value").addContent(lang.get("command_Done", ulang))

		self.pytrans.send(iq)
