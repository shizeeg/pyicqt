# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
from twisted.internet.defer import Deferred
from twisted.internet import reactor
import sys
import config
import legacy
from debug import LogEvent, INFO, WARN, ERROR
import lang
import globals


class ServiceDiscovery:
	""" Handles Service Discovery (aka DISCO) support """
 	 
	def __init__ (self, pytrans):
		LogEvent(INFO)
		self.pytrans = pytrans
		self.identities = {}
		self.features = {}
		self.nodes = {}
		self.userInfoHandlers = []
		self.userItemHandlers = []
		
		self.addFeature(globals.DISCO, None, config.jid)
		self.addFeature(globals.DISCO, None, "USER")
		self.pytrans.iq.addHandler(globals.DISCO, self.incomingIq, prefix=1)

	def addIdentity(self, category, ctype, name, jid):
		""" Adds an identity to this JID's discovery profile. If jid == "USER" then ICQ users will get this identity. """
		#debug.log("ServerDiscovery: Adding identity \"%r\" \"%r\" \"%r\" \"%r\"" % (category, ctype, name, jid))
		LogEvent(INFO)
		if not self.identities.has_key(jid):
			self.identities[jid] = []
		self.identities[jid].append((category, ctype, name))
	
	def addFeature(self, var, handler, jid):
		""" Adds a feature to this JID's discovery profile. If jid == "USER" then ICQ users will get this feature. """
		#debug.log("ServerDiscovery: Adding feature support \"%r\" \"%r\" \"%r\"" % (var, handler, jid))
		LogEvent(INFO)
		if not self.features.has_key(jid):
			self.features[jid] = []
		self.features[jid].append(var)
		if handler:
			self.pytrans.iq.addHandler(var, handler)

	def addNode(self, node, handler, name, jid, rootnode):
		""" Adds a node to this JID's discovery profile. If jid == "USER" then ICQ users will get this node. """
		#debug.log("ServerDiscovery: Adding node item \"%r\" \"%r\" \"%r\" \"%r\" \"%r\"" % (node, handler, name, jid, rootnode))
		LogEvent(INFO)
		if not self.nodes.has_key(jid):
			self.nodes[jid] = {}
		self.nodes[jid][node] = (handler, name, rootnode)

	def addUserItemHandler(self, handler):
		""" Adds an extra handler to disco items requests directed at users """
		LogEvent(INFO)
		self.userItemHandlers.append(handler)

	def addUserInfoHandler(self, handler):
		""" Adds an extra handler to disco info requests directed at users """
		LogEvent(INFO)
		self.userInfoHandlers.append(handler)

	def incomingIq(self, el):
		""" Decides what to do with an IQ """
		fro = el.getAttribute("from")
		to = el.getAttribute("to")
		ID = el.getAttribute("id")
		iqType = el.getAttribute("type")
		ulang = utils.getLang(el)
		try: # StringPrep
			froj = internJID(fro)
			to = internJID(to).full()
		except Exception, e:
			LogEvent(INFO, msg="Dropping IQ because of stringprep error")

		LogEvent(INFO, msg="Looking for handler")

		for query in el.elements():
			xmlns = query.uri
			node = query.getAttribute("node")

			if xmlns.startswith(globals.DISCO) and node:
				if self.nodes.has_key(to) and self.nodes[to].has_key(node) and self.nodes[to][node][0] != None:
					self.nodes[to][node][0](el)
					return
				else:
					# If the node we're browsing wasn't found, fall through and display the root disco
					self.sendDiscoInfoResponse(to=fro, ID=ID, ulang=ulang, jid=to)
					return
			elif xmlns == globals.DISCO_INFO:
				self.sendDiscoInfoResponse(to=fro, ID=ID, ulang=ulang, jid=to)
				return
			elif xmlns == globals.DISCO_ITEMS:
				self.sendDiscoItemsResponse(to=fro, ID=ID, ulang=ulang, jid=to)
				return

			# Still hasn't been handled
			LogEvent(WARN, msg="Unknown Iq Request")
			self.pytrans.iq.sendIqError(to=fro, fro=to, ID=ID, xmlns=xmlns, etype="cancel", condition="feature-not-implemented")

	def sendDiscoInfoResponse(self, to, ID, ulang, jid):
		""" Send a service discovery disco#info stanza to the given 'to'. 'jid' is the JID that was queried. """
		LogEvent(INFO)
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = jid
		iq.attributes["to"] = to
		if ID:
			iq.attributes["id"] = ID
		query = iq.addElement("query")
		query.attributes["xmlns"] = globals.DISCO_INFO
		
		searchjid = jid
		if jid.find('@') > 0: searchjid = "USER"

		# Add any identities
		for (category, ctype, name) in self.identities.get(searchjid, []):
			LogEvent(INFO, msg="Found identity %r %r %r" % (category, ctype, name))
			identity = query.addElement("identity")
			identity.attributes["category"] = category
			identity.attributes["type"] = ctype
			if name:
				identity.attributes["name"] = name
		
		# Add any supported features
		for var in self.features.get(searchjid, []):
			LogEvent(INFO, msg="Found feature %r" % (var))
			feature = query.addElement("feature")
			feature.attributes["var"] = var

		if searchjid == "USER":
			# Add any user specific identities/features
			for hndl in self.userInfoHandlers:
				hndl(jid, query)

		self.pytrans.send(iq)

	def sendDiscoItemsResponse(self, to, ID, ulang, jid):
		""" Send a service discovery disco#items stanza to the given 'to'. 'jid' is the JID that was queried. """
		LogEvent(INFO)
		iq = Element((None, "iq"))
		iq.attributes["type"] = "result"
		iq.attributes["from"] = jid
		iq.attributes["to"] = to
		if ID:
			iq.attributes["id"] = ID
		query = iq.addElement("query")
		query.attributes["xmlns"] = globals.DISCO_ITEMS

		searchjid = jid
		if jid.find('@') > 0: searchjid = "USER"

		for node in self.nodes.get(searchjid, []):
			handler, name, rootnode = self.nodes[jid][node]
			if rootnode:
				LogEvent(INFO, msg="Found node %r" % (node))
				name = lang.get(name, ulang)
				item = query.addElement("item")
				item.attributes["jid"] = jid
				item.attributes["node"] = node
				item.attributes["name"] = name

		if searchjid == "USER":
			# Add any user specific items
			for hndl in self.userItemHandlers:
				hndl(jid, query)
		
		self.pytrans.send(iq)
