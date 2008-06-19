# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
import config
import lang
from debug import LogEvent, INFO, WARN, ERROR
import globals

class RosterRetrieval:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.adhoc.addCommand("retrieveroster", self.incomingIq, "command_RosterRetrieval")

	def incomingIq(self, el):
		to = el.getAttribute("from")
		fro = el.getAttribute("from")
		froj = internJID(fro)
		ID = el.getAttribute("id")
		if not hasattr(self.pytrans, "legacycon"):
			self.pytrans.iq.sendIqError(to=to, fro=config.jid, ID=ID, xmlns=globals.COMMANDS, etype="cancel", condition="service-unavailable")
		ulang = utils.getLang(el)

		if not self.pytrans.sessions.has_key(froj.userhost()):
			self.pytrans.iq.sendIqError(to=fro, fro=config.jid, ID=ID, xmlns=globals.COMMANDS, etype="cancel", condition="service-unavailable")
			return
		s = self.pytrans.sessions[froj.userhost()]
		if not s.ready:
			self.pytrans.iq.sendIqError(to=fro, fro=config.jid, ID=ID, xmlns=globals.COMMANDS, etype="cancel", condition="service-unavailable")
			return

		iq = Element((None, "iq"))
		iq.attributes["to"] = to
		iq.attributes["from"] = config.jid
		if ID:
			iq.attributes["id"] = ID
		iq.attributes["type"] = "result"

		command = iq.addElement("command")
		command.attributes["sessionid"] = self.pytrans.makeMessageID()
		command.attributes["node"] = "retrieveroster"
		command.attributes["xmlns"] = globals.COMMANDS
		command.attributes["status"] = "completed"

		x = command.addElement("x")
		x.attributes["xmlns"] = globals.XDATA
		x.attributes["type"] = "result"

		title = x.addElement("title")
		title.addContent(lang.get("command_RosterRetrieval", ulang))

		reported = x.addElement("reported")
		reported.addChild(utils.makeDataFormElement(None, "legacyid", "Legacy ID"))
		reported.addChild(utils.makeDataFormElement(None, "nick", "Nickname"))

		entities = s.pytrans.xdb.getList("roster", s.jabberID)
		if entities != None:
			for e in entities:
				name = e[0]
				attrs = e[1]

				item = x.addElement("item")

				field = item.addElement("field")
				field.attributes["var"] = "legacyid"
				field.addElement("value").addContent(name)

				field = item.addElement("field")
				field.attributes["var"] = "nick"
				field.addElement("value").addContent(attrs.get('nickname',''))

		self.pytrans.send(iq)
