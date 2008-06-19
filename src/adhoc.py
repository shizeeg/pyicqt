# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
import config
import lang
from debug import LogEvent, INFO, WARN, ERROR
import globals

class AdHocCommands:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.disco.addFeature(globals.COMMANDS, self.incomingIq, config.jid)
		self.pytrans.disco.addNode(globals.COMMANDS, self.sendCommandList, "command_CommandList", config.jid, True)

		self.commands = {} # Dict of handlers indexed by node
		self.commandNames = {} # Dict of names indexed by node

	def addCommand(self, command, handler, name):
		self.commands[command] = handler
		self.commandNames[command] = name
		self.pytrans.disco.addNode(command, self.incomingIq, name, config.jid, False)

	def incomingIq(self, el):
		itype = el.getAttribute("type")
		fro = el.getAttribute("from")
		froj = internJID(fro)
		to = el.getAttribute("to")
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)

		LogEvent(INFO, msg="Looking for handler")

		node = None
		for child in el.elements():
			xmlns = child.uri
			node = child.getAttribute("node")

			handled = False
			if child.name == "query" and xmlns == globals.DISCO_INFO:
				if node and self.commands.has_key(node) and itype == "get":
					self.sendCommandInfoResponse(to=fro, ID=ID, node=node, ulang=ulang)
					handled = True
			elif child.name == "query" and xmlns == globals.DISCO_ITEMS:
				if node and self.commands.has_key(node) and itype == "get":
					self.sendCommandItemsResponse(to=fro, ID=ID, node=node, ulang=ulang)
					handled = True
			elif child.name == "command" and xmlns == globals.COMMANDS:
				if node and self.commands.has_key(node) and (itype == "set" or itype == "error"):
					self.commands[node](el)
					handled = True
			if not handled:
				LogEvent(WARN, msg="Unknown Ad-Hoc command received")
				self.pytrans.iq.sendIqError(to=fro, fro=config.jid, ID=ID, xmlns=xmlns, etype="cancel", condition="feature-not-implemented")


	def sendCommandList(self, el):
		to = el.getAttribute("from")
		ID = el.getAttribute("id")
		ulang = utils.getLang(el)

		iq = Element((None, "iq"))
		iq.attributes["to"] = to
		iq.attributes["from"] = config.jid
		if ID:
			iq.attributes["id"] = ID
		iq.attributes["type"] = "result"

		query = iq.addElement("query")
		query.attributes["xmlns"] = globals.DISCO_ITEMS
		query.attributes["node"] = globals.COMMANDS

		for command in self.commands:
			item = query.addElement("item")
			item.attributes["jid"] = config.jid
			item.attributes["node"] = command
			item.attributes["name"] = lang.get(self.commandNames[command], ulang)

		self.pytrans.send(iq)

	def sendCommandInfoResponse(self, to, ID, node, ulang):
		LogEvent(INFO, msg="Replying to disco#info")
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = config.jid
		iq.attributes["to"] = to
		if ID: iq.attributes["id"] = ID
		query = iq.addElement("query")
		query.attributes["xmlns"] = globals.DISCO_INFO

		# Add identity
		identity = query.addElement("identity")
		identity.attributes["name"] = lang.get(self.commandNames[node], ulang)
		identity.attributes["category"] = "automation"
		identity.attributes["type"] = "command-node"

		# Add supported feature
		feature = query.addElement("feature")
		feature.attributes["var"] = globals.COMMANDS

		# Add supported feature
		feature = query.addElement("feature")
		feature.attributes["var"] = globals.XDATA

		self.pytrans.send(iq)

	def sendCommandItemsResponse(self, to, ID, node, ulang):
		LogEvent(INFO, msg="Replying to disco#items")
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = config.jid
		iq.attributes["to"] = to
		if ID: iq.attributes["id"] = ID
		query = iq.addElement("query")
		query.attributes["xmlns"] = globals.DISCO_ITEMS

		self.pytrans.send(iq)

	def sendCancellation(self, node, el, sessionid=None):
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
		command.attributes["node"] = node
		command.attributes["xmlns"] = globals.COMMANDS
		command.attributes["status"] = "canceled"

		self.pytrans.send(iq)

	def sendError(self, node, el, errormsg, sessionid=None):
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
		command.attributes["node"] = node
		command.attributes["xmlns"] = globals.COMMANDS
		command.attributes["status"] = "completed"

		note = command.addElement("note")
		note.attributes["type"] = "error"
		note.addContent(errormsg)

		self.pytrans.send(iq)
