# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import utils
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber.jid import internJID
from twisted.internet import reactor, task
import config
import lang
from debug import LogEvent, INFO, WARN, ERROR
import globals
import os

SPOOL_UMASK = 0077

class PublishSubscribe:
	def __init__(self, pytrans):
		LogEvent(INFO)
		self.pytrans = pytrans
		self.storage = PubSubStorage()

		# Add disco entries without handlers.  We're going to set up
		# our own general handler, we'll do that in a moment.
		self.pytrans.disco.addIdentity("pubsub", "pep", None, "USER")
		self.pytrans.disco.addFeature(globals.PUBSUB, None, "USER")
		self.pytrans.disco.addFeature(globals.PUBSUBPEP, None, "USER")
		self.pytrans.disco.addFeature(globals.PUBSUBACCESSPRES, None, "UJSER")

		# Now we need to tell disco that we're going to possibly
		# add items on behave of the user.
		self.pytrans.disco.addUserItemHandler(self.userDiscoItems)

		# Set up the pubsub prefix handler.
		self.pytrans.iq.addHandler(globals.PUBSUB, self.incomingIq, prefix=1)

	def incomingIq(self, el):
		itype = el.getAttribute("type")
		fro = el.getAttribute("from")
		froj = internJID(fro)
		to = el.getAttribute("to")
		toj = internJID(to)
		ID = el.getAttribute("id")

	def userDiscoItems(self, jid, query):
		nodes = self.storage.getNodeList(jid)
		for n in nodes:
			item = query.addElement("item")
			item.attributes["jid"] = jid
			item.attributes["node"] = n

	def localPublish(self, jid, node, itemid, el):
		self.storage.setItem(jid, node, itemid, el)



class PubSubStorage:
	""" Manages pubsub nodes on disk. Nodes are stored according to
	their jid and node.  The layout is config.spooldir / config.jid / pubsub / pubsub jid / node.
        That said, nodes can also have /'s in them, so we will utilize the
        file system to store these in a 'nice' layout. """


	def dir(self, jid, node):
		""" Returns the full path to the directory that a 
		particular key is in. Creates that directory if it doesn't already exist. """
		X = os.path.sep
		d = os.path.abspath(config.spooldir) + X + config.jid + X + "pubsub" + X + utils.mangle(jid) + X + self.nodeToPath(node) + X
		prev_umask = os.umask(SPOOL_UMASK)
		if not os.path.exists(d):
			os.makedirs(d)
		os.umask(prev_umask)
		return d

	def nodeToPath(self, node):
		X = os.path.sep
		path = node.replace('//', X+'_'+X).replace('/', X)
		return path

	def pathToNode(self, path):
		X = os.path.sep
		node = path.replace(X, '/').replace(X+'_'+X, '//')
		return node
	
	def setItem(self, jid, node, itemid, el):
		""" Writes an item to disk according to its jid, node, and
		itemid.  Returns nothing. """
		LogEvent(INFO)
		prev_umask = os.umask(SPOOL_UMASK)
		try:
			f = open(self.dir(jid, node) + itemid + ".xml", 'wb')
			f.write(el.toXml())
			f.close()
		except IOError, e:
			LogEvent(WARN, msg="IOError writing to node %r - %r" % (jid, node))
		os.umask(prev_umask)
	
	def getItem(self, jid, node, itemid):
		""" Loads the item from a node from disk and returns an element """
		try:
			filename = self.dir(jid, node) + itemid + ".xml"
			if os.path.isfile(filename):
				LogEvent(INFO, msg="Getting item %r - %r" % (node, itemid))
				document = utils.parseFile(filename)
				return document
			else:
				LogEvent(INFO, msg="Avatar not found %r" % (key))
		except IOError, e:
			LogEvent(INFO, msg="IOError reading item %r - %r" % (node, itemid))

	def getNodeList(self, jid):
		""" Retrieves a list of all of the pubsub/pep items for a
		particular jid.  Here we need to hunt through the file system
		and construct Node ids from what we find. """
		nodes = []
		X = os.path.sep
		pubsubbase = os.path.abspath(config.spooldir)+X+config.jid+X+"pubsub"+X+utils.mangle(jid)

		if not os.path.isdir(pubsubbase):
			return nodes

		def findfiles(dir=pubsubbase):
			for e in os.listdir(dir):
				if e == "." or e == "..": continue
				path=dir+X+e
				if os.path.isdir(path):
					findfiles(path)
				elif path.endswith(".xml"):
					dir = dir.replace(pubsubbase+X,"",1)
					if not nodes.count(dir):
						nodes.append(self.pathToNode(dir))

		findfiles()
		return nodes
