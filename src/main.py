# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

import os, os.path, time, sys, codecs, getopt, shutil
reload(sys)
sys.setdefaultencoding("utf-8")
sys.stdout = codecs.lookup('utf-8')[-1](sys.stdout)

# Find the best reactor
reactorchoices = ["epollreactor", "kqreactor", "cfreactor", "pollreactor", "selectreactor", "posixbase", "default"]
for choice in reactorchoices:
	try:
		exec("from twisted.internet import %s as bestreactor" % choice)
		if choice in ["selectreactor","default"]:
			print selectWarning
		break
	except:
		pass
try:
	bestreactor.install()
except:
	print "Unable to find a reactor.\nExiting..."
	sys.exit(1)

import twistfix
twistfix.main()

if __name__ == "__main__":
	print "The transport can no longer be started from main.py.  Please use"
	print "PyICQt.py from the root of the distribution instead."
	sys.exit(0)

import utils
from debug import LogEvent, INFO, WARN, ERROR
import debug

import config
import xmlconfig
conffile = "config.xml"
profilelog = None
options = {}
daemonizeme = False
opts, args = getopt.getopt(sys.argv[1:], "bc:o:dDgtl:p:h", ["background", "config=", "option=", "debug", "Debug", "garbage", "traceback", "log=", "profile=", "help"])
for o, v in opts:
	if o in ("-c", "--config"):
		conffile = v
	elif o in ("-p", "--profile"):
		profilelog = v
	elif o in ("-b", "--background"):
                daemonizeme = True
	elif o in ("-d", "--debug"):
		config.debugLevel = 2
	elif o in ("-D", "--Debug"):
		config.debugLevel = 3
	elif o in ("-g", "--garbage"):
		import gc
		gc.set_debug(gc.DEBUG_LEAK|gc.DEBUG_STATS)
	elif o in ("-t", "--traceback"):
		config.debugLevel = 1
	elif o in ("-l", "--log"):
		config.debugFile = v
	elif o in ("-o", "--option"):
		var, setting = v.split("=", 2)
		options[var] = setting
	elif o in ("-h", "--help"):
		print "./PyICQt [options]"
		print "   -h                  print this help"
		print "   -b                  daemonize/background transport"
		print "   -c <file>           read configuration from this file"
		print "   -d                  print debugging output (very little)"
		print "   -D                  print extended debugging output"
		print "   -g                  print garbage collection output"
		print "   -t                  print debugging only on traceback"
		print "   -l <file>           write debugging output to file"
		print "   -o <var>=<setting>  set config var to setting"
		sys.exit(0)
debug.reloadConfig()

xmlconfig.Import(conffile, options)

def reloadConfig(a, b):
	# Reload default config and then process conf file
	reload(config)
	xmlconfig.Import(conffile, None)
	debug.reloadConfig()

# Set SIGHUP to reload the config file
if os.name == "posix":
	import signal
	signal.signal(signal.SIGHUP, reloadConfig)
	# Load scripts for PID and daemonizing
	try:
		from twisted.scripts import _twistd_unix as twistd
	except:
		from twisted.scripts import twistd

selectWarning = "Unable to install any good reactors (kqueue, cf, epoll, poll).\nWe fell back to using select. You may have scalability problems.\nThis reactor will not support more than 1024 connections +at a time.  You may silence this message by choosing 'select' or 'default' as your reactor in the transport config."
if config.reactor and len(config.reactor) > 0:
	# They picked their own reactor. Lets install it.
	del sys.modules["twisted.internet.reactor"]
	reactorconv = {
		"epoll":"epollreactor",
		"poll":"pollreactor",
		"kqueue":"kqreactor",
		"cf":"cfreactor",
		"select":"selectreactor"
	}
	if reactorconv.has_key(config.reactor):
		reactorname = reactorconv[config.reactor]
	else:
		reactorname = config.reactor
	try:
		exec("from twisted.internet import %s as setreactor" % reactorname)
		setreactor.install()
		LogEvent(INFO, msg="Enabled reactor %s" % reactorname, skipargs=True)
	except:
		print "Unknown reactor: ", config.reactor, ". Using default, select(), reactor."
		from twisted.internet import default as bestreactor
		print selectWarning


from twisted.internet import reactor, task
from twisted.internet.defer import Deferred
from twisted.words.xish.domish import Element
from twisted.words.protocols.jabber import component
from twisted.words.protocols.jabber.jid import internJID


import xdb
import avatar
import session
import svninfo
import jabw
import iq
import disco
import adhoc
#import pubsub
import register
import legacy
import lang
import globals



class PyTransport(component.Service):
	routewrap = 0
	def __init__(self):
		LogEvent(INFO)
		try:
			LogEvent(INFO, msg="SVN r" + svninfo.getSVNVersion())
		except:
			pass

		### Database prep-work
		# Open our spool
		self.xdb = xdb.XDB(config.jid)
		# We need to enable our avatar cache
		if not config.disableAvatars: self.avatarCache = avatar.AvatarCache()

		### Lets load some key/base functionality handlers
		# Service discovery support
		self.iq = iq.IqHandler(self)
		# Service discovery support
		self.disco = disco.ServiceDiscovery(self)
		# Ad-hoc commands support
		self.adhoc = adhoc.AdHocCommands(self)
		# Pubsub/PEP support
		#self.pubsub = pubsub.PublishSubscribe(self)
		# Registration support
		self.registermanager = register.RegisterManager(self)

		# Lets add some known built-in features to discovery
		self.disco.addIdentity("gateway", legacy.id, legacy.name, config.jid)
		self.disco.addFeature(globals.XHTML, None, "USER")

		# Lets load the base and legacy service plugins
		self.serviceplugins = {}
		self.loadPlugins("src/services")
		self.loadPlugins("src/legacy/services")

		# Misc tracking variables
		self.startTime = int(time.time())
		self.xmlstream = None
		self.sessions = {}
		# Message IDs
		self.messageID = 0
		
		# Routine cleanup/updates/etc
		self.loopTask = task.LoopingCall(self.loopFunc)
		self.loopTask.start(60.0)


	def loadPlugins(self, dir):
		imppath = dir.replace("src/", "").replace("/", ".")
		files = os.listdir(dir);
		for i in range(len(files)):
			if files[i] == "__init__.py": continue
			if files[i].endswith(".py"):
				classname = files[i].replace(".py","")
				if self.serviceplugins.has_key(classname):
					print "Unable to load service plugin %s: Duplicate plugin???" % classname
					continue
				try:
					exec("from %s import %s" % (imppath, classname))
					exec("self.serviceplugins['%s'] = %s.%s(self)" % (classname, classname, classname))
				except Exception, e:
					print "Unable to load service plugin %s: %s" % (classname, e)
					raise


	def removeMe(self):
		LogEvent(INFO)
		for session in self.sessions.copy():
			self.sessions[session].removeMe()

	def makeMessageID(self):
		self.messageID += 1
		return str(self.messageID)
	
	def loopFunc(self):
		numsessions = len(self.sessions)

		self.serviceplugins['Statistics'].stats["Uptime"] = int(time.time()) - self.startTime
		if numsessions > 0:
			oldDict = self.sessions.copy()
			self.sessions = {}
			for key in oldDict:
				session = oldDict[key]
				if not session.alive:
					LogEvent(WARN, msg="Ghost session found")
					# Don't add it to the new dictionary. Effectively removing it
				else:
					self.sessions[key] = session
	
	def componentConnected(self, xmlstream):
		LogEvent(INFO)
		self.xmlstream = xmlstream
		self.xmlstream.addObserver("/iq", self.iq.onIq)
		self.xmlstream.addObserver("/presence", self.onPresence)
		self.xmlstream.addObserver("/message", self.onMessage)
		self.xmlstream.addObserver("/bind", self.onBind)
		self.xmlstream.addObserver("/route", self.onRouteMessage)
		self.xmlstream.addObserver("/error[@xmlns='http://etherx.jabber.org/streams']", self.streamError)
		if config.useXCP and config.compjid:
			pres = Element((None, "presence"))
			pres.attributes["to"] = "presence@-internal"
			pres.attributes["from"] = config.compjid
			x = pres.addElement("x")
			x.attributes["xmlns"] = globals.COMPPRESENCE
			x.attributes["xmlns:config"] = globals.CONFIG
			x.attributes["config:version"] = "1"
			x.attributes["protocol-version"] = "1.0"
			x.attributes["config-ns"] = legacy.url + "/component"
			self.send(pres)
		if config.useComponentBinding:
			LogEvent(INFO, msg="Component binding to %r" % config.jid)
			bind = Element((None,"bind"))
			bind.attributes["name"] = config.jid
			self.send(bind)
		if config.useRouteWrap:
			self.routewrap = 1

		self.sendInvitations()

	def send(self, obj):
		if self.routewrap == 1 and type(obj) == Element:
			to = obj.getAttribute("to")
			route = Element((None,"route"))
			route.attributes["from"] = config.jid
			route.attributes["to"] = internJID(to).host
			route.addChild(obj)
			obj.attributes["xmlns"] = "jabber:client"
			component.Service.send(self,route.toXml())
		else:
			if type(obj) == Element:
				obj = obj.toXml()
			component.Service.send(self,obj)
	
	def componentDisconnected(self):
		LogEvent(INFO)
		self.xmlstream = None
		self.routewrap = 0

	def onRouteMessage(self, el):
		LogEvent(INFO)
		for child in el.elements():
			if child.name == "message": 
				self.onMessage(child)
			elif child.name == "presence":
				# Ignore any presence broadcasts about other XCP components
				if child.getAttribute("to") and child.getAttribute("to").find("@-internal") > 0: return
				self.onPresence(child)
			elif child.name == "iq":
				self.iq.onIq(child)
			elif child.name == "bind": 
				self.onBind(child)

	def onBind(self, el):
		LogEvent(INFO)

	def streamError(self, errelem):
		LogEvent(INFO)
		self.xmlstream.streamError(errelem)

	def streamEnd(self, errelem):
		LogEvent(INFO)
	
	def onMessage(self, el):
		fro = el.getAttribute("from")
		to = el.getAttribute("to")
		mtype = el.getAttribute("type")
		try:
			froj = internJID(fro)
		except Exception, e:
			LogEvent(WARN, msg="Failed stringprep")
			return
		if self.sessions.has_key(froj.userhost()):
			self.sessions[froj.userhost()].onMessage(el)
		elif mtype != "error":
			ulang = utils.getLang(el)
			body = None
			for child in el.elements():
				if child.name == "body":
					body = child.__str__()
			LogEvent(INFO, msg="Sending error response to a message outside of seession")
			jabw.sendErrorMessage(self, fro, to, "auth", "not-authorized", lang.get("notloggedin", ulang), body)
	
	def onPresence(self, el):
		fro = el.getAttribute("from")
		to = el.getAttribute("to")
		# Ignore any presence broadcasts about other JD2 components
		if to == None: return
		try:
			froj = internJID(fro)
			toj = internJID(to)
		except Exception, e:
			LogEvent(WARN, msg="Failed stringprep")
			return

		if self.sessions.has_key(froj.userhost()):
			self.sessions[froj.userhost()].onPresence(el)
		else:
			ulang = utils.getLang(el)
			ptype = el.getAttribute("type")
			if to.find('@') < 0:
				# If the presence packet is to the transport (not a user) and there isn't already a session
				if not ptype: # Don't create a session unless they're sending available presence
					LogEvent(INFO, msg="Attempting to create a new session")
					s = session.makeSession(self, froj.userhost(), ulang, toj)
					if s:
						self.sessions[froj.userhost()] = s
						LogEvent(INFO, msg="New session created")
						# Send the first presence
						s.onPresence(el)
					else:
						LogEvent(INFO, msg="Failed to create session")
						jabw.sendMessage(self, to=froj.userhost(), fro=config.jid, body=lang.get("notregistered", ulang))
				
				elif ptype != "error":
					LogEvent(INFO, msg="Sending unavailable presence to non-logged in user")
					pres = Element((None, "presence"))
					pres.attributes["from"] = to
					pres.attributes["to"] = fro
					pres.attributes["type"] = "unavailable"
					self.send(pres)
					return
			
			elif ptype and (ptype.startswith("subscribe") or ptype.startswith("unsubscribe")):
				# They haven't logged in, and are trying to change subscription to a user
				# Lets log them in and then do it
				LogEvent(INFO, msg="New session created")
				s = session.makeSession(self, froj.userhost(), ulang, toj)
				if s:
					self.sessions[froj.userhost()] = s
					LogEvent(INFO, msg="New session created")
					# Tell the session there's a new resource
					s.handleResourcePresence(froj.userhost(), froj.resource, toj.userhost(), toj.resource, 0, None, None, None, None)
					# Send this subscription
					s.onPresence(el)

	def sendInvitations(self):              
		if config.enableAutoInvite:
			for jid in self.xdb.getRegistrationList():
				LogEvent(INFO, msg="Inviting %r" % jid)
				jabw.sendPresence(self, jid, config.jid, ptype="probe")
				jabw.sendPresence(self, jid, "%s/registered" % (config.jid), ptype="probe")



class App:
	def __init__(self):
		# Check for any other instances
		if config.pid and os.name != "posix":
			config.pid = ""
		if config.pid:
			twistd.checkPID(config.pid)

		# Do any auto-update stuff
		xdb.housekeep()

		# Daemonise the process and write the PID file
		if daemonizeme and os.name == "posix":
			twistd.daemonize()
		if config.pid:
			self.writePID()

		jid = config.jid
		if config.useXCP and config.compjid: jid = config.compjid

		if config.saslUsername:
			import sasl
			self.c = sasl.buildServiceManager(jid, config.saslUsername, config.secret, "tcp:%s:%s" % (config.mainServer, config.port))
		else:
			self.c = component.buildServiceManager(jid, config.secret, "tcp:%s:%s" % (config.mainServer, config.port))
		self.transportSvc = PyTransport()
		self.transportSvc.setServiceParent(self.c)
		self.c.startService()

		reactor.addSystemEventTrigger('before', 'shutdown', self.shuttingDown)

	def alreadyRunning(self):
		print "There is already a transport instance running with this configuration."
		print "Exiting..."
		sys.exit(1)

	def writePID(self):
		# Create a PID file
		pid = str(os.getpid())
		pf = open(config.pid, "w")
		pf.write("%s\n" % pid)
		pf.close()

	def shuttingDown(self):
		self.transportSvc.removeMe()
		def cb(ignored=None):
			if config.pid:
				twistd.removePID(config.pid)
		d = Deferred()
		d.addCallback(cb)
		reactor.callLater(3.0, d.callback, None)
		return d



def main():
	app = App()
	if config.webport:
		try:
			from nevow import appserver
			import web
			site = appserver.NevowSite(web.WebInterface(pytrans=app.transportSvc))
			reactor.listenTCP(config.webport, site)
			LogEvent(INFO, msg="Web interface activated")
		except:
			LogEvent(WARN, msg="Unable to start web interface.  Either Nevow is not installed or you need a more recent version of Twisted.  (>= 2.0.0.0)")
	reactor.run()
