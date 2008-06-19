# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
import config
from debug import LogEvent, INFO, WARN, ERROR
import globals
import time

class EntityTime:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.disco.addFeature(globals.IQTIME, self.incomingIq, config.jid)
		self.pytrans.disco.addFeature(globals.IQTIME, self.incomingIq, "USER")

	def incomingIq(self, el):
		eltype = el.getAttribute("type")
		if eltype != "get": return # Only answer "get" stanzas

		self.sendTime(el)

	def sendTime(self, el):
		LogEvent(INFO)
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = el.getAttribute("to")
		iq.attributes["to"] = el.getAttribute("from")
		if el.getAttribute("id"):
			iq.attributes["id"] = el.getAttribute("id")
		query = iq.addElement("query")
		query.attributes["xmlns"] = globals.IQTIME
		utc = query.addElement("utc")
		utc.addContent(str(time.strftime("%Y%m%dT%H:%M:%S")))
		tz = query.addElement("tz")
		tz.addContent(str(time.tzname[1]))
		display = query.addElement("display")
		display.addContent(str(time.ctime()))

		self.pytrans.send(iq)
