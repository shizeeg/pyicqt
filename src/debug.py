# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

from twisted.python import log
import sys, time
import config


def observer(eventDict):
	try:
		observer2(eventDict)
	except Exception, e:
		printf("CRITICAL: Traceback in debug.observer2 - " + str(e))


def observer2(eventDict):
	edm = eventDict['message']
	if isinstance(edm, LogEvent):
		if edm.category == INFO and config.debugLevel < 3:
			return
		if (edm.category == WARN or edm.category == ERROR) and config.debugLevel < 2:
			return
		text = str(edm)
	elif edm:
		if config.debugLevel < 3: return
		text = ' '.join(map(str, edm))
	else:
		if eventDict['isError'] and eventDict.has_key('failure'):
			if config.debugLevel < 1: return
			text = eventDict['failure'].getTraceback()
		elif eventDict.has_key('format'):
			if config.debugLevel < 3: return
			text = eventDict['format'] % eventDict
		else:
			return
	
	# Now log it!
	timeStr = time.strftime("[%Y-%m-%d %H:%M:%S]", time.localtime(eventDict['time']))
	text = text.replace("\n", "\n\t")
	global debugFile
	debugFile.write("%s %s\n" % (timeStr, text))
	debugFile.flush()
	
def printf(text):
	sys.__stdout__.write(text + "\n")
	sys.__stdout__.flush()

debugFile = None
def reloadConfig():
	global debugFile
	if debugFile:
		debugFile.close()

	if config.debugLevel > 0:
		if len(config.debugFile) > 0:
			try:
				debugFile = open(config.debugFile, "a")
				log.msg("Reopened log file.")
			except IOError:
				log.discardLogs() # Give up
				debugFile = sys.__stdout__
				return
		else:
			debugFile = sys.__stdout__

		log.startLoggingWithObserver(observer)
	else:
		log.discardLogs()

class INFO : pass
class WARN : pass
class ERROR: pass

class LogEvent:
	def __init__(self, category=INFO, ident="", msg="", log=True, skipargs=False):
		self.category, self.ident, self.msg = category, ident, msg
		frame = sys._getframe(1)
		# Get the class name
		s = str(frame.f_locals.get("self", frame.f_code.co_filename))
		self.klass = s[s.find(".")+1:s.find(" ")]
		if self.klass == "p": self.klass = ""
		self.method = frame.f_code.co_name
		if self.method == "?": self.method = ""
		self.args = frame.f_locals
		self.skipargs = skipargs
		if log:
			self.log()
	
	def __str__(self):
		args = {}
		if not self.skipargs:
			for key in self.args.keys():
				if key == "self":
					#args["self"] = "instance"
					continue
				val = self.args[key]
				args[key] = val
				try:
					if len(val) > 128:
						args[key] = "Oversize arg"
				except:
					# If its not an object with length, assume that it can't be too big. Hope that's a good assumption.
					pass
		category = str(self.category).split(".")[1]
		return "%s :: %s :: %s :: %s :: %s :: %s" % (category, str(self.ident), str(self.klass), self.method, str(args), self.msg)
	
	def log(self):
		log.msg(self)
