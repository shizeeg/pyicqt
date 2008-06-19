# Copyright 2005-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
from debug import LogEvent, INFO, WARN, ERROR
import config
import lang
import globals

class EmailLookup:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.adhoc.addCommand("emaillookup", self.incomingIq, "command_EmailLookup")

	def incomingIq(self, el):
		to = el.getAttribute("from")
		toj = internJID(to)
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)

		sessionid = None
		email = None

		for command in el.elements():
			sessionid = command.getAttribute("sessionid")
			if command.getAttribute("action") == "cancel":
				self.pytrans.adhoc.sendCancellation("emaillookup", el, sessionid)
				return
			for child in command.elements():
				if child.name == "x" and child.getAttribute("type") == "submit":
					for field in child.elements():
						if field.name == "field" and field.getAttribute("var") == "email":
							for value in field.elements():
								if value.name == "value":
									email = value.__str__()

		if not self.pytrans.sessions.has_key(toj.userhost()) or not hasattr(self.pytrans.sessions[toj.userhost()].legacycon, "bos"):
			self.pytrans.adhoc.sendError("emaillookup", el, errormsg=lang.get("command_NoSession", ulang), sessionid=sessionid)
		elif email:
			self.lookupEmail(el, email, sessionid=sessionid)
		else:
			self.sendForm(el)

	def sendForm(self, el, sessionid=None, errormsg=None):
		to = el.getAttribute("from")
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
		command.attributes["node"] = "emaillookup"
		command.attributes["xmlns"] = globals.COMMANDS
		command.attributes["status"] = "executing"

		if errormsg:
			note = command.addElement("note")
			note.attributes["type"] = "error"
			note.addContent(errormsg)

		actions = command.addElement("actions")
		actions.attributes["execute"] = "complete"
		actions.addElement("complete")

		x = command.addElement("x")
		x.attributes["xmlns"] = "jabber:x:data"
		x.attributes["type"] = "form"

		title = x.addElement("title")
		title.addContent(lang.get("command_EmailLookup", ulang))

		instructions = x.addElement("instructions")
		instructions.addContent(lang.get("command_EmailLookup_Instructions", ulang))

		email = x.addElement("field")
		email.attributes["type"] = "text-single"
		email.attributes["var"] = "email"
		email.attributes["label"] = lang.get("command_EmailLookup_Email", ulang)

		self.pytrans.send(iq)

	def lookupEmail(self, el, email, sessionid=None):
		to = el.getAttribute("from")
		toj = internJID(to)

		self.pytrans.sessions[toj.userhost()].legacycon.bos.lookupEmail(email).addCallback(self.emailLookupResults, el, sessionid)

	def emailLookupResults(self, results, el, sessionid):
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
		command.attributes["node"] = "emaillookup"
		command.attributes["xmlns"] = globals.COMMANDS
		command.attributes["status"] = "completed"

		note = command.addElement("note")
		note.attributes["type"] = "info"
		note.addContent(lang.get("command_EmailLookup_Results", ulang))

		x = command.addElement("x")
		x.attributes["xmlns"] = "jabber:x:data"
		x.attributes["type"] = "form"

		title = x.addElement("title")
		title.addContent(lang.get("command_EmailLookup", ulang))

		for r in results:
			email = x.addElement("field")
			email.attributes["type"] = "fixed"
			email.addElement("value").addContent(r)

		self.pytrans.send(iq)
