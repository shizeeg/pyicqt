# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
import config
import lang
from debug import LogEvent, INFO, WARN, ERROR
import globals

class Statistics:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.adhoc.addCommand("stats", self.incomingIq, "command_Statistics")

		# self.stats is indexed by a unique ID, with value being the value for that statistic
		self.stats = {}
		self.stats["Uptime"] = 0
		self.stats["OnlineSessions"] = 0
		self.stats["IncomingMessages"] = 0
		self.stats["OutgoingMessages"] = 0
		self.stats["TotalSessions"] = 0
		self.stats["MaxConcurrentSessions"] = 0

		self.sessionstats = {}

	def sessionSetup(self, jid):
		self.sessionstats[jid] = { } 
		self.sessionstats[jid]['IncomingMessages'] = 0
		self.sessionstats[jid]['OutgoingMessages'] = 0
		self.sessionstats[jid]['Connections'] = 0

	def sessionUpdate(self, jid, setting, value):
		if not self.sessionstats.has_key(jid):
			self.sessionSetup(jid)
		self.sessionstats[jid][setting] += value

	def incomingIq(self, el):
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
		command.attributes["sessionid"] = self.pytrans.makeMessageID()
		command.attributes["xmlns"] = globals.COMMANDS
		command.attributes["status"] = "completed"

		x = command.addElement("x")
		x.attributes["xmlns"] = globals.XDATA
		x.attributes["type"] = "result"

		title = x.addElement("title")
		title.addContent(lang.get("command_Statistics", ulang))

		for key in self.stats:
			label = lang.get("statistics_%s" % key, ulang)
			description = lang.get("statistics_%s_Desc" % key, ulang)
			field = x.addElement("field")
			field.attributes["var"] = key
			field.attributes["label"] = label
			field.attributes["type"] = "text-single"
			field.addElement("value").addContent(str(self.stats[key]))
			field.addElement("desc").addContent(description)

		self.pytrans.send(iq)
