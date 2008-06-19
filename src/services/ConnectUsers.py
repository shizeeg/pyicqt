# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
import jabw
import config
import lang
from debug import LogEvent, INFO, WARN, ERROR
import globals

class ConnectUsers:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.adhoc.addCommand("connectusers", self.incomingIq, "command_ConnectUsers")
        
	def sendProbes(self):
		for jid in self.pytrans.xdb.getRegistrationList():
			jabw.sendPresence(self.pytrans, jid, config.jid, ptype="probe")

	def incomingIq(self, el):
		to = el.getAttribute("from")
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)

		if config.admins.count(internJID(to).userhost()) == 0:
			self.pytrans.iq.sendIqError(to=to, fro=config.jid, ID=ID, xmlns=globals.COMMANDS, etype="cancel", condition="not-authorized")
			return

		self.sendProbes()

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
		title.addContent(lang.get("command_ConnectUsers", ulang))

		field = x.addElement("field")
		field.attributes["type"] = "fixed"
		field.addElement("value").addContent(lang.get("command_Done", ulang))

		self.pytrans.send(iq)
