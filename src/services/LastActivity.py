# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
import config
from debug import LogEvent, INFO, WARN, ERROR
import globals

class LastActivity:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.disco.addFeature(globals.IQLAST, self.incomingIq, config.jid)
		self.pytrans.disco.addFeature(globals.IQLAST, self.incomingIq, "USER")

	def incomingIq(self, el):
		eltype = el.getAttribute("type")
		if eltype != "get": return # Only answer "get" stanzas

		self.sendLastActivity(el)

	def sendLastActivity(self, el):
		LogEvent(INFO)
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = el.getAttribute("to")
		iq.attributes["to"] = el.getAttribute("from")
		if el.getAttribute("id"):
			iq.attributes["id"] = el.getAttribute("id")
		query = iq.addElement("query")
		query.attributes["xmlns"] = globals.IQLAST
		query.attributes["seconds"] = "0"

		self.pytrans.send(iq)
