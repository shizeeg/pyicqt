# Copyright 2004-2006 James Bunton <james@delx.cjb.net> 
# Licensed for distribution under the GPL version 2, check COPYING for details


from twisted.python import log

import warnings, re, sys

from version import VersionNumber



def suppressWarnings():
	# Suppress the annoying warning we get with Twisted 1.3 words being deprecated
	warnings.filters.append(("ignore", None, UserWarning, re.compile("twisted.words"), 21))
	# Suppress the OpenSSL UserWarning
	warnings.filters.append(("ignore", re.compile("SSL connection shutdown possibly unreliable, please upgrade to ver 0.XX"), UserWarning, re.compile("twisted.internet.tcp"), 216))

def addParserFunctions():
	from twisted.words.xish import domish
	domish.parseText = parseText
	domish.parseFile = parseFile


def tryTwisted30():
	try:
		log.msg("Trying for Twisted > 2.0.0, Words >= 0.3, Words DOM")
		from twisted.words.xish.domish import SuxElementStream, Element, unescapeFromXml
		from twisted.words.protocols.jabber import jid, component
		log.msg("Using Twisted >= 2.0, Words >= 0.3, Words DOM")
		return True
	except ImportError:
		return False

def tryTwisted20():
	log.msg("Checking Twisted version...")
	import twisted.copyright
	v = VersionNumber(twisted.copyright.version)

	if v == VersionNumber("2.0.0"):
		log.msg("You are using Twisted 2.0.0. This version is too buggy. Please install a different version.")
		sys.exit(1)

	if v > VersionNumber("2.0.0"):
		from twisted.xish.domish import SuxElementStream, Element, unescapeFromXml
		from twisted.words.protocols.jabber import jid, component
		from twisted.web.http import HTTPClient
		import twisted.xish
		import twisted.xish.domish
		import twisted.words
		sys.modules["twisted.words.xish"] = twisted.xish
		sys.modules["twisted.words.xish.domish"] = twisted.xish.domish
		log.msg("Using Twisted >= 2.0, Words < 0.3, Twisted DOM")
		return True

	return False
	
def tryTwisted10():
	log.msg("Trying for Twisted 1.3, using internal patched DOM")
	import twistfix.words
	import twisted
	sys.modules["twisted.words"] = twistfix.words
	from twisted.words.protocols.jabber import jid
	jid.internJID = jid.intern
	from twisted.protocols import http
	sys.modules["twisted.web.http"] = http
	log.msg("Using Twisted < 2.0, Internal patched DOM")
	return True

def tryTwisted():
	try:
		if tryTwisted30(): return
		if tryTwisted20(): return
		if tryTwisted10(): return
	except:
		pass
	print "ImportError! You probably forgot to install Twisted Words or Web. Have a look at the docs. You may also be using an unsupported version of Twisted."
	sys.exit(1)

def main():
	suppressWarnings()
	tryTwisted()
	addParserFunctions()



#####################
# Easy text parsing #
#####################

def parseText(text, beExtremelyLenient=False, addDoc=True):
	return TextParser(beExtremelyLenient, addDoc).parseString(text)

def parseFile(filename, beExtremelyLenient=False, addDoc=True):
	return TextParser(beExtremelyLenient, addDoc).parseFile(filename)


class TextParser:
	def __init__(self, beExtremelyLenient=False, addDoc=False):
		self.root = None
		self.beExtremelyLenient = beExtremelyLenient
		self.addDoc = addDoc

	def parseFile(self, filename):
		return self.parseString(file(filename).read())

	def parseString(self, data):
		if self.addDoc:
			# Add a document parent tag. This makes parsing of single
			# elements work better. Without this they can't have a body
			data = "<document>%s</document>" % data

		from twisted.words.xish.domish import SuxElementStream
		es = SuxElementStream()
		es.beExtremelyLenient = self.beExtremelyLenient
		es.DocumentStartEvent = self.docStart
		es.DocumentEndEvent = self.docEnd
		es.ElementEvent = self.element
		es.parse(data)

		if self.addDoc:
			if len(self.root.children) < 1:
				return
			elif len(self.root.children) == 1:
				return self.root.children[0]
		return self.root

	def docStart(self, e):
		self.root = e

	def docEnd(self):
		pass

	def element(self, e):
		self.root.addChild(e)





if __name__ == "__main__":
	main()


