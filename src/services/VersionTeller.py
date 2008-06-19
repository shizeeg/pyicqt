# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
import svninfo
import legacy
import config
from debug import LogEvent, INFO, WARN, ERROR
import sys
import globals
import twisted.copyright

class VersionTeller:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.disco.addFeature(globals.IQVERSION, self.incomingIq, config.jid)
		self.pytrans.disco.addFeature(globals.IQVERSION, self.incomingIq, "USER")
		try:
			self.version = "%s - SVN r%s" % (legacy.version, svninfo.getSVNVersion())
		except:
			self.version = legacy.version
		self.os = "Python " + sys.version.split(' ')[0] + "/" + sys.platform + ", Twisted " + twisted.copyright.version

	def incomingIq(self, el):
		eltype = el.getAttribute("type")
		if eltype != "get": return # Only answer "get" stanzas

		self.sendVersion(el)

	def sendVersion(self, el):
		LogEvent(INFO)
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = el.getAttribute("to")
		iq.attributes["to"] = el.getAttribute("from")
		if el.getAttribute("id"):
			iq.attributes["id"] = el.getAttribute("id")
		query = iq.addElement("query")
		query.attributes["xmlns"] = globals.IQVERSION
		name = query.addElement("name")
		name.addContent(legacy.name)
		version = query.addElement("version")
		version.addContent(self.version)
		os = query.addElement("os")
		os.addContent(self.os)

		self.pytrans.send(iq)
