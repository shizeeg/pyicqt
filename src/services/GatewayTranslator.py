# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
import legacy
import config
import lang
from debug import LogEvent, INFO, WARN, ERROR
import globals

class GatewayTranslator:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		self.pytrans.disco.addFeature(globals.IQGATEWAY, self.incomingIq, config.jid)
	
	def incomingIq(self, el):
		fro = el.getAttribute("from")
		ID = el.getAttribute("id")
		itype = el.getAttribute("type")
		if itype == "get":
			self.sendPrompt(fro, ID, utils.getLang(el))
		elif itype == "set":
			self.sendTranslation(fro, ID, el)
	
	def sendPrompt(self, to, ID, ulang):
		LogEvent(INFO)
		
		iq = Element((None, "iq"))
		
		iq.attributes["type"] = "result"
		iq.attributes["from"] = config.jid
		iq.attributes["to"] = to
		iq.attributes["id"] = ID
		query = iq.addElement("query")
		query.attributes["xmlns"] = globals.IQGATEWAY
		desc = query.addElement("desc")
		desc.addContent(lang.get("gatewaytranslator", ulang))
		prompt = query.addElement("prompt")
		
		self.pytrans.send(iq)
	
	def sendTranslation(self, to, ID, el):
		LogEvent(INFO)
		
		# Find the user's legacy account
		legacyaccount = None
		for query in el.elements():
			if query.name == "query":
				for child in query.elements():
					if child.name == "prompt":
						legacyaccount = str(child)
						break
				break
		
		
		if legacyaccount and len(legacyaccount) > 0:
			LogEvent(INFO, msg="Sending translated account")
			iq = Element((None, "iq"))
			iq.attributes["type"] = "result"
			iq.attributes["from"] = config.jid
			iq.attributes["to"] = to
			iq.attributes["id"] = ID
			query = iq.addElement("query")
			query.attributes["xmlns"] = globals.IQGATEWAY
			prompt = query.addElement("prompt")
			prompt.addContent(legacy.translateAccount(legacyaccount))
			jid = query.addElement("jid")
			jid.addContent(legacy.translateAccount(legacyaccount))
			
			self.pytrans.send(iq)
		
		else:
			self.pytrans.iq.sendIqError(to, ID, globals.IQGATEWAY)
			self.pytrans.iq.sendIqError(to=to, fro=config.jid, ID=ID, xmlns="jabber:iq:gateway", etype="retry", condition="bad-request")
