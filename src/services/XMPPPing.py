# Licensed for distribution under the GPL version 2, check COPYING for details

from twisted.words.xish.domish import Element
import config
from debug import LogEvent, INFO, WARN, ERROR
import globals

class XMPPPing:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.disco.addFeature(globals.IQPING, self.incomingIq, config.jid)
		self.pytrans.disco.addFeature(globals.IQPING, self.incomingIq, "USER")

	def incomingIq(self, el):
		eltype = el.getAttribute("type")
		if eltype != "get": return # Only answer "get" stanzas

		self.sendPong(el)

	def sendPong(self, el):
		LogEvent(INFO)
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = el.getAttribute("to")
		iq.attributes["to"] = el.getAttribute("from")
		if el.getAttribute("id"):
			iq.attributes["id"] = el.getAttribute("id")

		self.pytrans.send(iq)