# Copyright 2004-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details

from debug import LogEvent, INFO, WARN, ERROR
import re
import string
import config
import os
import os.path
import sys
import globals
from twisted.web import microdom
from twisted.words.xish.domish import Element, SuxElementStream

X = os.path.sep

_controlCharPat = re.compile(
	r"[\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f"
	r"\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f]")

set_char = [
	(0x000001, 0x00D7FF),
	(0x00E000, 0x00FFFD),
	(0x010000, 0x10FFFF)
]

set_restrictedchar = [
	(0x01, 0x08),
	(0x0B, 0x0C),
	(0x0E, 0x1F),
	(0x7F, 0x84),
	(0x86, 0x9F)
]

def is_in(set_list, c):
	for i in set_list:
		from_char, to_char = i
		if ord(c) >= from_char and ord(c) <= to_char:
			return True
	return False

_excluded = range(0,9)+range(11,13)+range(14,32)+range(0xD800,0xE000)+range(0xFFFE,0x10000)

excluded = {}
for c in _excluded: excluded[c] = None

def xmlify(s):
	if s.__class__ == str:
		try:
			us = unicode(s)
		except UnicodeDecodeError:
			us = unicode(s, 'iso-8859-1')
		return us.translate(excluded)
	elif s.__class__ == unicode:
		return s.translate(excluded)
	else:
		return ""

def xhtml_to_aimhtml(s):
	try:
		LogEvent(INFO, msg="Got %r" % s)

		# Convert the spans to fonts!
		s = re.sub("<(/?)span",r"<\1font",s)

		# SIMHTML doesn't support spans
		s = re.sub("</?span[^>]*>","",s)

		# AIMHTML might croke on these
		s = re.sub("<br/>","<br>",s)

		LogEvent(INFO, msg="Made %r" % s)
		return s
	except:
		LogEvent(INFO, msg="Failed")
		return None

def lower_element(match):
	s=match.group()
	return string.lower(s)

def font_to_span(match):
	s = re.sub("<font ([^>]*)>",r"\1",match.group())
	style=""

	m=re.search("style=['\"]([^'\">]*)['\"]",s);
	if m: style = style + "%s; "%(m.group(1))
 
	m=re.search("color=['\"]?([^'\" ]*)",s);
	if m: style = style + "color: %s; "%(m.group(1))

	m=re.search("face=['\"]([^'\">]*)['\"]",s);
	if m: style = style + "font-family: %s; "%(m.group(1))

	m=re.search("ptsize=['\"]?([0-9]*)",s)
	if m:
		style = style + "font-size: %dpt; "%(int(m.group(1)))
	else:
		m=re.search("absz=['\"]?([0-9]*)",s)
		if m:
			style = style + "font-size: %dpt; "%(int(m.group(1))*12/16+1)
		else:
			m=re.search("size=['\"]?([0-9]*)",s)
			if m:
				style = style + "font-size: %dpt; "%(int(m.group(1))*2+6)

	return "<span style='%s'>"%style

def prepxhtml(s):
	# We need to convert the horrible mess that is AIM's
	# type of html into well-formed xhtml. Yikes!
	try:
		s=s.encode("utf-8","replace")

		LogEvent(INFO, msg="Got %r" % s)

		s = re.sub(">+",">",s)
		s = re.sub("<+","<",s)

		# Fix dangling ampersands
		s = re.sub("&([^; =&<>\"'\n]*[ =&<>\"'\n])",r"&amp;\1",s)

		all_regex = re.compile('</?[^>]*>'); 
		try: s=all_regex.sub(lower_element, s);
		except: LogEvent(INFO, msg="Unable to do lowercase stuff")

		font_regex = re.compile('<font [^>]*>',re.X);
		try: s=font_regex.sub(font_to_span, s);
		except: LogEvent(INFO, msg="Unable to do font-to-span stuff")

		s = re.sub("</?(html|HTML)[^>]*>","",s)

		#s = re.sub("<font [^>]*color=[\"']([^\"']*)[\"'][^>]*>(.*?)</font>",r"<span style='color: \1'>\2</span>",s)
		#s = re.sub("<FONT [^>]*color=[\"']([^\"']*)[\"'][^>]*>(.*?)</FONT>",r"<span style='color: \1'>\2</span>",s)

		# Get rid of tags not supported by xhtml
		#s = re.sub("</?(font|FONT)[^>]*>","",s)
		s = re.sub("<(/?)font",r"<\1span",s)

		s = re.sub("<(body|BODY) ?","<body xmlns='http://www.w3.org/1999/xhtml' ",s);
		#s = re.sub("</BODY>","</body>",s);
		#s = re.sub("<BR/?>","<br/>",s);
		#s = re.sub("<P ?([^>]*)>",r"<p \1>",s);
		#s = re.sub("</P>",r"</p>",s);
		#s = re.sub("<A ?([^>]*)>",r"<a \1>",s);
		#s = re.sub("</A>",r"</a>",s);
		#s = re.sub("<B ?([^>]*)>",r"<b \1>",s);
		#s = re.sub("</B>",r"</b>",s);
		#s = re.sub("<I ?([^>]*)>",r"<i \1>",s);
		#s = re.sub("</I>",r"</i>",s);
		#s = re.sub("<STRONG ?([^>]*)>",r"<strong \1>",s);
		#s = re.sub("</STRONG>",r"</strong>",s);

		# Attempt to reparse so we can make well-formed XML
		ms = microdom.parseString(s, beExtremelyLenient=True)
		ret = ms.toxml()

		# Remove the xml header
		ret = re.sub('<\?xml.*\?>', '', ret)

		# Make sure our root tag is properly namespaced
		ret = "<html xmlns=\""+globals.XHTML+"\">%s</html>"%ret;

		LogEvent(INFO, msg="Made %r" % ret)
		return ret.encode("utf-8","replace")
	except:
		LogEvent(INFO, msg="Failed")
		return None
	
def utf8encode(text):
	if text == None: return text
	encodedstring = ""
	for c in text.encode('utf-8', 'replace'):
		if is_in(set_char, c) and not _controlCharPat.search(c): 
			encodedstring = encodedstring + c
	#encodedstring.replace('\x00','')
	return encodedstring

def copyList(lst):
	""" Does a deep copy of a list """
	out = []
	out.extend(lst)
	return out

def mutilateMe(me):
	""" Mutilates a class :) """
#	for key in dir(me):
#		exec "me." + key + " = None"

def getLang(el):
	return el.getAttribute((u'http://www.w3.org/XML/1998/namespace', u'lang'))

import random
def random_guid():
	format = "{%4X%4X-%4X-%4X-%4X-%4X%4X%4X}"
	data = []
	for x in xrange(8):
		data.append(random.random() * 0xAAFF + 0x1111)
	data = tuple(data)

	return format % data


import base64
def b64enc(s):
	return base64.encodestring(s).replace('\n', '')

def b64dec(s):
	return base64.decodestring(s)

errorCodeMap = {
	"bad-request"			:	400,
	"conflict"			:	409,
	"feature-not-implemented"	:	501,
	"forbidden"			:	403,
	"gone"				:	302,
	"internal-server-error"		:	500,
	"item-not-found"		:	404,
	"jid-malformed"			:	400,
	"not-acceptable"		:	406,
	"not-allowed"			:	405,
	"not-authorized"		:	401,
	"payment-required"		:	402,
	"recipient-unavailable"		:	404,
	"redirect"			:	302,
	"registration-required"		:	407,
	"remote-server-not-found"	:	404,
	"remote-server-timeout"		:	504,
	"resource-constraint"		:	500,
	"service-unavailable"		:	503,
	"subscription-required"		:	407,
	"undefined-condition"		:	500,
	"unexpected-request"		:	400
}

def parseText(text, beExtremelyLenient=False):
	t = TextParser(beExtremelyLenient)
	t.parseString(text)
	return t.root

def parseFile(filename, beExtremelyLenient=False):
	t = TextParser(beExtremelyLenient)
	t.parseFile(filename)
	return t.root

class TextParser:
	""" Taken from http://xoomer.virgilio.it/dialtone/rsschannel.py """

	def __init__(self, beExtremelyLenient=False):
		self.root = None
		self.beExtremelyLenient = beExtremelyLenient

	def parseFile(self, filename):
		return self.parseString(file(filename).read())

	def parseString(self, data):
		es = SuxElementStream()
		es.beExtremelyLenient = self.beExtremelyLenient
		es.DocumentStartEvent = self.docStart
		es.DocumentEndEvent = self.docEnd
		es.ElementEvent = self.element
		es.parse(data)
		return self.root

	def docStart(self, e):
		self.root = e

	def docEnd(self):
		pass

	def element(self, e):
		self.root.addChild(e)

def makeDataFormElement(type, var, label=None, value=None, options=None):
	field = Element((None, "field"))
	if type:
		field.attributes["type"] = type
	if var:
		field.attributes["var"] = var
	if label:
		field.attributes["label"] = label
	if value:
		val = field.addElement("value")
		val.addContent(value)
	if options:
		# Take care of options at some point
		pass

	return field

def getDataFormValue(form, var):
	value = None
	for field in form.elements():
		if field.name == "field" and field.getAttribute("var") == var:
			for child in field.elements():
				if child.name == "value":
					if child.__str__():
						value = child.__str__();
					break
	return value

class NotesToMyself:
	def __init__(self, noteList):
		pre = os.path.abspath(config.spooldir) + X + config.jid + X
		self.filename = pre + X + "notes_to_myself"
		self.notes = []
                
		if os.path.exists(self.filename):
			f = open(self.filename, "r")
			self.notes = [x.strip() for x in f.readlines()]
			f.close()
		elif not os.path.exists(pre):
			self.notes = noteList
			os.makedirs(pre)

	def check(self, note):
		return self.notes.count(note) == 0

	def append(self, note):
		if self.check(note):
			self.notes.append(note)

	def save(self):
		f = open(self.filename, "w")
		for note in self.notes:
			f.write(note + "\n")
		f.close()

def unmangle(jid):
	chunks = jid.split("%")
	end = chunks.pop()
	jid = "%s@%s" % ("%".join(chunks), end)
	return jid
         
def mangle(jid):
	return jid.replace("@", "%")

# Helper functions to encrypt and decrypt passwords
def encryptPassword(password):
	return base64.encodestring(password)

def decryptPassword(password):
	return base64.decodestring(password)
