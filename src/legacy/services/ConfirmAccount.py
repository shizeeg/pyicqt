# Copyright 2005-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
from debug import LogEvent, INFO, WARN, ERROR
import config
import lang
import globals

class ConfirmAccount:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.adhoc.addCommand("confirmaccount", self.incomingIq, "command_ConfirmAccount")

	def incomingIq(self, el):
		to = el.getAttribute("from")
		toj = internJID(to)
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)

		sessionid = None

		for command in el.elements():
			sessionid = command.getAttribute("sessionid")
			if command.getAttribute("action") == "cancel":
				self.pytrans.adhoc.sendCancellation("confirmaccount", el, sessionid)
				return

		if not self.pytrans.sessions.has_key(toj.userhost()) or not hasattr(self.pytrans.sessions[toj.userhost()].legacycon, "bos"):
			self.pytrans.adhoc.sendError("confirmaccount", el, errormsg=lang.get("command_NoSession", ulang), sessionid=sessionid)
		else:
			self.pytrans.sessions[toj.userhost()].legacycon.bos.confirmAccount().addCallback(self.sendResponse, el, sessionid)

	def sendResponse(self, failure, el, sessionid=None):
		LogEvent(INFO)
		to = el.getAttribute("from")
		toj = internJID(to)
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)

		iq = Element((None, "iq"))
		iq.attributes["to"] = to
		iq.attributes["from"] = config.jid
		if ID:
			iq.attributes["id"] = ID
		iq.attributes["type"] = "result"

		command = iq.addElement("command")
		if sessionid:
			command.attributes["sessionid"] = sessionid
		else:
			command.attributes["sessionid"] = self.pytrans.makeMessageID()
		command.attributes["node"] = "confirmaccount"
		command.attributes["xmlns"] = globals.COMMANDS
		command.attributes["status"] = "completed"

		note = command.addElement("note")
		if failure:
			note.attributes["type"] = "error"
			note.addContent(lang.get("command_ConfirmAccount_Failed", ulang))
		else:
			note.attributes["type"] = "info"
			note.addContent(lang.get("command_ConfirmAccount_Complete", ulang))

		self.pytrans.send(iq)
