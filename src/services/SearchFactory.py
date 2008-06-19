# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
import config
import lang
from debug import LogEvent, INFO, WARN, ERROR
import globals

class SearchFactory:
	def __init__(self, pytrans):
		self.pytrans = pytrans
		if 0: # Disable for now
			self.pytrans.disco.addFeature(globals.IQSEARCH, self.incomingIq, config.jid)

	def incomingIq(self, el):
		eltype = el.getAttribute("type")
		ID = el.getAttribute("id")
		to = el.getAttribute("from")
		if not hasattr(self.pytrans, "legacycon"):
			self.pytrans.iq.sendIqError(to=to, fro=config.jid, ID=ID, xmlns=globals.COMMANDS, etype="cancel", condition="service-unavailable")
		elif eltype == "get":
			self.sendSearchForm(el)
		elif eltype == "set":
			self.processSearch(el)

	def sendSearchForm(self, el):
		LogEvent(INFO)
		ulang = utils.getLang(el)
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = el.getAttribute("to")
		iq.attributes["to"] = el.getAttribute("from")
		if el.getAttribute("id"):
			iq.attributes["id"] = el.getAttribute("id")
		query = iq.addElement("query")
		query.attributes["xmlns"] = globals.IQSEARCH
		forminstr = query.addElement("instructions")
		forminstr.addContent(lang.get("searchnodataform", ulang))
		x = query.addElement("x")
		x.attributes["xmlns"] = globals.XDATA
		x.attributes["type"] = "form"
		title = x.addElement("title")
		title.addContent(lang.get("searchtitle", ulang))
		instructions = x.addElement("instructions")
		instructions.addContent(lang.get("searchinstructions", ulang))
		x.addChild(utils.makeDataFormElement("hidden", "FORM_TYPE", value="jabber:iq:search"))
		x.addChild(utils.makeDataFormElement("text-single", "email", "E-Mail Address"))
		x.addChild(utils.makeDataFormElement("text-single", "first", "First Name"))
		x.addChild(utils.makeDataFormElement("text-single", "middle", "Middle Name"))
		x.addChild(utils.makeDataFormElement("text-single", "last", "Last Name"))
		x.addChild(utils.makeDataFormElement("text-single", "maiden", "Maiden Name"))
		x.addChild(utils.makeDataFormElement("text-single", "nick", "Nickname"))
		x.addChild(utils.makeDataFormElement("text-single", "address", "Street Address"))
		x.addChild(utils.makeDataFormElement("text-single", "city", "City"))
		x.addChild(utils.makeDataFormElement("text-single", "state", "State"))
		x.addChild(utils.makeDataFormElement("text-single", "zip", "Zip Code"))
		x.addChild(utils.makeDataFormElement("text-single", "country", "Country"))
		x.addChild(utils.makeDataFormElement("text-single", "interest", "Interest"))

		self.pytrans.send(iq)

	def processSearch(self, el):
		LogEvent(INFO)
		ulang = utils.getLang(el)
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		to = el.getAttribute("to")
		iq.attributes["from"] = to
		fro = el.getAttribute("from")
		iq.attributes["to"] = fro
		ID = el.getAttribute("id")
		if ID:
			iq.attributes["id"] = ID
		query = iq.addElement("query")
		query.attributes["xmlns"] = globals.IQSEARCH
		x = query.addElement("x")
		x.attributes["xmlns"] = globals.XDATA
		x.attributes["type"] = "result"
		x.addChild(utils.makeDataFormElement("hidden", "FORM_TYPE", value="jabber:iq:search"))
		reported = x.addElement("reported")
		reported.addChild(utils.makeDataFormElement(None, "jid", "Jabber ID"))
		reported.addChild(utils.makeDataFormElement(None, "first", "First Name"))
		reported.addChild(utils.makeDataFormElement(None, "middle", "Middle Name"))
		reported.addChild(utils.makeDataFormElement(None, "last", "Last Name"))
		reported.addChild(utils.makeDataFormElement(None, "maiden", "Maiden Name"))
		reported.addChild(utils.makeDataFormElement(None, "nick", "Nickname"))
		reported.addChild(utils.makeDataFormElement(None, "email", "E-Mail Address"))
		reported.addChild(utils.makeDataFormElement(None, "address", "Street Address"))
		reported.addChild(utils.makeDataFormElement(None, "city", "City"))
		reported.addChild(utils.makeDataFormElement(None, "state", "State"))
		reported.addChild(utils.makeDataFormElement(None, "country", "Country"))
		reported.addChild(utils.makeDataFormElement(None, "zip", "Zip Code"))
		reported.addChild(utils.makeDataFormElement(None, "region", "Region"))

		dataform = None
		for query in el.elements():
			if query.name == "query":
				for child in query.elements():
					if child.name == "x":
						dataform = child
						break
				break

		if not hasattr(self.pytrans, "legacycon"):
			self.pytrans.iq.sendIqError(to=to, fro=config.jid, ID=ID, xmlns=globals.IQSEARCH, etype="cancel", condition="bad-request")

		if dataform:
			self.pytrans.legacycon.doSearch(dataform, iq).addCallback(self.gotSearchResponse)
		else:
			self.pytrans.iq.sendIqError(to=to, fro=config.jid, ID=ID, xmlns=globals.IQSEARCH, etype="retry", condition="bad-request")

	def gotSearchResponse(self, iq):
		LogEvent(INFO)
		self.pytrans.send(iq)
