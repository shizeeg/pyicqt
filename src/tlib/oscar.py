# Copyright (c) 2001-2005 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# vim: set sts=4 ts=4 expandtab :

"""An implementation of the OSCAR protocol, which AIM and ICQ use to communcate.

This module is unstable.

Maintainer: U{Daniel Henninger<mailto:jadestorm@nc.rr.com>}
Previous Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
SMS Related code by Uri Shaked <uri@keves.org>
"""

from __future__ import nested_scopes

from twisted.internet import reactor, defer, protocol
from twisted.python import log

from scheduler import Scheduler

import struct
import md5
import string
import socket
import random
import time
import types
import re
import binascii
import threading
import socks5, sockserror
import countrycodes
import config
import datetime
import utils

def logPacketData(data):
    # Comment out to display packet log data
    return
    lines = len(data)/16
    if lines*16 != len(data): lines=lines+1
    for i in range(lines):
        d = tuple(data[16*i:16*i+16])
        hex = map(lambda x: "%02X"%ord(x),d)
        text = map(lambda x: (len(repr(x))>3 and '.') or x, d)
        log.msg(' '.join(hex)+ ' '*3*(16-len(d)) +''.join(text))
    log.msg('')

def bitstostr(num, size):
    bitstring = ''
    if num < 0: return
    if num == 0: return '0'*size
    cnt = 0
    while cnt < size:
        bitstring = str(num % 2) + bitstring
        num = num >> 1
        cnt = cnt + 1
    return bitstring

def SNAC(fam,sub,id,data,flags=[0,0]):
    head=struct.pack("!HHBBL",fam,sub,
                     flags[0],flags[1],
                     id)
    return head+str(data)

def readSNAC(data):
    try:
        if len(data) < 10: return None
        head=list(struct.unpack("!HHBBL",data[:10]))
        datapos = 10
        if 0x80 & head[2]:
            # Ah flag 0x8000, this is some sort of family indicator, skip it,
            # we don't care.
            sLen,id,length = struct.unpack(">HHH", data[datapos:datapos+6])
            datapos = datapos + 6 + length
        return head+[data[datapos:]]
    except struct.error:
        return None

def oldICQCommand(commandCode, commandData, username, sequence):
    """
    Packs a command for the old ICQ server.
    commandCode (int) - the code of the command,
    commandData - the data payload of the command.
    username (str) - The UIN of the sender
    sequence (int) - The lower word of the SNAC ID that encapsulates the command.
    """
    header = "<HLHH"
    head = struct.pack(header,
                       struct.calcsize(header) + len(commandData) - 2,
                       int(username),
                       commandCode,
                       sequence & 0xffff)
    return head + commandData

def TLV(type,value=''):
    head=struct.pack("!HH",type,len(value))
    return head+str(value)

def readTLVs(data,count=None):
    dict={}
    while data and len(dict)!=count:
        head=struct.unpack("!HH",data[:4])
        dict[head[0]]=data[4:4+head[1]]
        data=data[4+head[1]:]
    if count == None:
        return dict
    return dict,data

def encryptPasswordMD5(password,key):
    m=md5.new()
    m.update(key)
    m.update(md5.new(password).digest())
    m.update("AOL Instant Messenger (SM)")
    return m.digest()

def encryptPasswordICQ(password):
    key=[0xF3,0x26,0x81,0xC4,0x39,0x86,0xDB,0x92,0x71,0xA3,0xB9,0xE6,0x53,0x7A,0x95,0x7C]
    bytes=map(ord,password)
    r=""
    for i in range(len(bytes)):
        r=r+chr(bytes[i]^key[i%len(key)])
    return r

def dehtml(text):
    if (not text):
        text = ""

    # In HTML, line breaks are just whitespace. 
    text=re.sub("\n"," ",text)

    # Convert all of the block-level elements into linebreaks
    text=re.sub('</?[Bb][Rr][^>]*>',"\n",text)
    text=re.sub('</?[Pp][^>]*>',"\n",text)
    text=re.sub('</?[Dd][Ii][Vv][^>]*>',"\n",text)

    # Convert inline images to their alt-tags
    text=re.sub('<[Ii][Mm][Gg] +[^>]*alt=["\']([^"\']*)["\'][^>]*>',r"\1",text)
    
    # Turn bold into stars
    text=re.sub('<[Bb]>(.*?)</[Bb]>',r"*\1*",text)
    text=re.sub('<strong>(.*?)</strong>',r"*\1*",text)
    
    # Turn italics into underscores
    text=re.sub('<[Ii]>(.*?)</[Ii]>',r"_\1_",text)
    
    # Turn quotes into, um quotes.
    text=re.sub('<quote[^>]*>(.*?)</quote>',r'"\1"',text)
    
    # Extract links
    text=re.sub('<[Aa] +[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</[Aa]>',r"\2 &lt;\1&gt; ",text)
    
    # Convert more than two linebreaks into just two
    text=re.sub("\n\n+","\n\n",text)
    
    # Get rid of any leading or trailing whitespace
    text=re.sub("^[ \n]+","",text)
    text=re.sub("[ \n]+$","",text)

    # Convert clumps of whitespace into just one space
    text=re.sub(" +"," ",text)

    # Remove any remaining HTML elements.
    text=re.sub('<[^>]*>','',text)

    # Convert the entities
    text=string.replace(text,'&gt;','>')
    text=string.replace(text,'&lt;','<')
    text=string.replace(text,'&nbsp;',' ')
    text=string.replace(text,'&amp;','&')
    text=string.replace(text,'&quot;',"'")
    return text

def html(text):
    if (not text):
        text = ""
    text=string.replace(text,'&','&amp;')
    text=string.replace(text,'<','&lt;')
    text=string.replace(text,'>','&gt;')
    text=string.replace(text,"\n","<br>")
    return '<html><body bgcolor="white"><font color="black">%s</font></body></html>'%text

def getIconSum(buf):
    sum = 0L
    i = 0
    buflen = len(buf)
    while i+1 < buflen:
        sum += (ord(buf[i+1]) << 8) + ord(buf[i])
        i += 2

    if i < buflen:
        sum += ord(buf[i])

    sum = ((sum & 0xffff0000L) >> 16) + (sum & 0x0000ffffL)

    return sum

# Originally taken from:
# http://www.pyzine.com/Issue008/Section_Articles/article_Encodings.html
# which was adapted from io.py
# in the docutils extension module
# see http://docutils.sourceforge.net
# modified for better use here
def guess_encoding(data, defaultencoding=config.encoding):
    """
    Given a byte string, attempt to decode it.
    Tries 'utf-16be, 'utf-8' and 'iso-8859-1' (or something else) encodings.
    
    If successful it returns 
        (decoded_unicode, successful_encoding)
    If unsuccessful it raises a ``UnicodeError``
    """
    successful_encoding = None
    #encodings = ['utf-8', 'utf-16be', defaultencoding]
    encodings = ['utf-8', defaultencoding]
    for enc in encodings:
        # some of the locale calls 
        # may have returned None
        if not enc:
            continue
        try:
            decoded = unicode(data, enc)
            #decoded = data.decode(enc)
            successful_encoding = enc

        except (UnicodeError, LookupError):
            pass
        else:
            break
    if not successful_encoding:
         decoded = "We have received text in unsupported encoding.\n" + repr(data)
         successful_encoding = "iso-8859-1"
    return (decoded, successful_encoding)


class OSCARUser:
    def __init__(self, name, warn, tlvs):
        self.name = name
        self.warning = warn
        self.flags = []
        self.caps = []
	self.customStatus = dict([])
        self.icqStatus = []
        self.icqFlags = []
        self.icqIPaddy = None
        self.icqLANIPaddy = None
        self.icqLANIPport = None
        self.icqProtocolVersion = None
        self.status = ""
        self.url = ""
        self.statusencoding = None
        self.idleTime = 0
        self.iconmd5sum = None
        self.icontype = None
        self.iconcksum = None
        self.iconlen = None
        self.iconstamp = None

	if tlvs == None:
		pass
	else:
		for k,v in tlvs.items():
			if k == 0x0001: # user flags
				v=struct.unpack('!H',v)[0]
				for o, f in [(0x0001,'unconfirmed'),
						(0x0002,'admin'),
						(0x0004,'staff'),
						(0x0008,'commercial'),
						(0x0010,'free'),
						(0x0020,'away'),
						(0x0040,'icq'),
						(0x0080,'wireless'),
						(0x0100,'unknown'),
						(0x0200,'unknown'),
						(0x0400,'active'),
						(0x0800,'unknown'),
						(0x1000,'abinternal')]:
					if v&o: self.flags.append(f)
			elif k == 0x0002: # account creation time
				self.createdOn = struct.unpack('!L',v)[0]
			elif k == 0x0003: # on-since
				self.onSince = struct.unpack('!L',v)[0]
			elif k == 0x0004: # idle time
				self.idleTime = struct.unpack('!H',v)[0]
			elif k == 0x0005: # member since
				self.memberSince = struct.unpack('!L',v)[0]
			elif k == 0x0006: # icq online status and flags
				# Flags first
				mv=struct.unpack('!H',v[0:2])[0]
				for o, f in [(0x0001,'webaware'),
						(0x0002,'showip'),
						(0x0008,'birthday'),
						(0x0020,'webfront'),
						(0x0100,'dcdisabled'),
						(0x1000,'dcauth'),
						(0x2000,'dccont')]:
					if mv&o: self.icqFlags.append(f)
		
				# Status flags next
				mv=struct.unpack('!H',v[2:4])[0]
				status_dict = [(0x0000,'online'),
					(0x0001,'away'),
					(0x0002,'dnd'),
					(0x0004,'xa'),
					(0x0010,'busy'),
					(0x0020,'chat'),
					(0x0100,'invisible'),
					# Miranda
					(0x0005,'lunch'),
					(0x0011,'phone'),
					# QutIM
					(0x3000,'evil'),
					(0x4000,'depression'),
					(0x5000,'home'),
					(0x6000,'work'),
					(0x2001,'lunch')]
				for o, f in status_dict:
					if o == mv: # if exact match
						self.icqStatus.append(f)
				if len(self.icqStatus) == 0: # strange status. Need try interpret it
					for o, f in status_dict:
						if mv&o:
							self.icqStatus.append(f)
			elif k == 0x0008: # client type?
				pass
			elif k == 0x000a: # icq user ip address
				self.icqIPaddy = socket.inet_ntoa(v)
			elif k == 0x000c: # icq random stuff
				# from http://iserverd1.khstu.ru/oscar/info_block.html
				self.icqRandom = struct.unpack('!4sLBHLLLLLLH',v)
				self.icqLANIPaddy = socket.inet_ntoa(self.icqRandom[0])
				self.icqLANIPport = self.icqRandom[1]
				self.icqProtocolVersion = self.icqRandom[3]
			elif k == 0x000d: # capabilities
				caps=[]
				while v:
					c=v[:16]
			
					if CAPS.has_key(c): caps.append(CAPS[c])
					else: caps.append(("unknown",c))
					v=v[16:]
					
					if c in X_STATUS_CAPS:
						self.customStatus['x-status'] = X_STATUS_NAME[X_STATUS_CAPS[c]]
		
				caps.sort()
				self.caps=caps
			elif k == 0x000e: # AOL capability information
				pass
			elif k == 0x000f: # session length (aim)
				self.sessionLength = struct.unpack('!L',v)[0]
			elif k == 0x0010: # session length (aol)
				self.sessionLength = struct.unpack('!L',v)[0]
			elif k == 0x0019: # OSCAR short capabilities
				pass
			elif k == 0x001a: # AOL short capabilities
				pass
			elif k == 0x001b: # encryption certification MD5 checksum
				pass
			elif k == 0x001d: # AIM Extended Status
				log.msg("AIM Extended Status: user %s\nv: %s"%(self.name,repr(v)))
				while len(v)>4 and ord(v[0]) == 0 and ord(v[3]) != 0:
					exttype,extflags,extlen = struct.unpack('!HBB',v[0:4])
					if exttype == 0x00: # Gaim skips this, so will we
						pass
					elif exttype == 0x01: # Actual interesting buddy icon
						if extlen > 0 and (extflags == 0x00 or extflags == 0x01):
							self.iconmd5sum = v[4:4+extlen]
							self.icontype = extflags
							log.msg("   extracted icon hash: extflags = %s, iconhash = %s" % (str(hex(extflags)), binascii.hexlify(self.iconmd5sum)))
					elif exttype == 0x02: # Extended Status Message
						if extlen >= 4: # Why?  Gaim does this
							availlen = (struct.unpack('!H', v[4:6]))[0]
							self.status = v[6:6+availlen]
							pos = 6+availlen
							if pos < extlen+4:
								hasencoding = (struct.unpack('!H',v[pos:pos+2]))[0]
								pos = pos+2
								if hasencoding == 0x0001:
									enclen = (struct.unpack('!HH',v[pos:pos+4]))[1]
									self.statusencoding = v[pos+4:pos+4+enclen]
							log.msg("   extracted status message: %s"%(self.status))
							zeropos = self.status.find('\x00')
							if zeropos > 0:
								self.status = self.status[:zeropos]
								log.msg('	fixing QIP Infium status message. Status message: %s' % self.status) 
							if self.statusencoding:
								log.msg("   status message encoding: %s"%(str(self.statusencoding)))
					elif exttype == 0x09: # iTunes URL
						statlen = (struct.unpack('!H', v[4:6]))[0]
						#statlen=int((struct.unpack('!H', v[2:4]))[0])-4
						if statlen>2 and v[6+statlen-1:6+statlen] != "\x00":
							self.url=v[6:6+statlen]
						else:
							self.url=None
						log.msg("   extracted itunes URL: %s"%(repr(self.url)))
					elif exttype == 0x0d or exttype ==  0x08:
						#XXX attempt to resolve problem with new ICQ clients: this needs to be verified by reverse engineering of the protocol
						self.statusencoding = "icq51pseudounicode"
						log.msg("   status message encoding: %s"%(str(self.statusencoding)))
						# XXX: there should be probably more information available for extraction here
					elif exttype == 0x0e:
						# ICQ 6 custom status (mood)
						if extlen >= 8:
							icq_mood_iconstr=v[4:(4+extlen)]
							if icq_mood_iconstr.find('icqmood') != -1:
								icq_mood_num = int(icq_mood_iconstr.replace('icqmood',''))
								if icq_mood_num in X_STATUS_MOODS:
									self.customStatus['icqmood'] = X_STATUS_NAME[X_STATUS_MOODS[icq_mood_num]]
								log.msg('    icqmood #:',icq_mood_num)
					else:
						log.msg("   unknown extended status type: %d\ndata: %s"%(ord(v[1]), repr(v[:ord(v[3])+4])))
					#v=v[ord(v[3])+4:]
					v=v[extlen+4:]
			elif k == 0x001e: # unknown
				pass
			elif k == 0x001f: # unknown
				pass
			else:
				log.msg("unknown tlv for user %s\nt: %s\nv: %s"%(self.name,str(hex(k)),repr(v)))

    def __str__(self):
        s = '<OSCARUser %s' % self.name
        o = []
        if self.warning!=0: o.append('warning level %s'%self.warning)
        if hasattr(self, 'flags'): o.append('flags %s'%self.flags)
        if hasattr(self, 'sessionLength'): o.append('online for %i minutes' % (self.sessionLength/60,))
        if hasattr(self, 'idleTime'): o.append('idle for %i minutes' % self.idleTime)
        if self.caps: o.append('caps %s'%self.caps)
        if o:
            s=s+', '+', '.join(o)
        s=s+'>'
        return s

    def __repr__(self):
        return self.__str__()


class SSIGroup:
    def __init__(self, name, groupID, buddyID, tlvs = {}):
        self.name = name
        self.groupID = groupID
        self.buddyID = buddyID
        #self.tlvs = []
        #self.userIDs = []
        self.usersToID = {}
        self.users = []
        #if not tlvs.has_key(0xC8): return
        #buddyIDs = tlvs[0xC8]
        #while buddyIDs:
        #    bid = struct.unpack('!H',buddyIDs[:2])[0]
        #    buddyIDs = buddyIDs[2:]
        #    self.users.append(bid)

    def findIDFor(self, user):
        return self.usersToID[user]

    def addUser(self, buddyID, user):
        self.usersToID[user] = buddyID
        self.users.append(user)
        user.group = self

    def delUser(self, user):
        buddyID = self.usersToID[user]
        self.users.remove(user)
        del self.usersToID[user]
        user.group = None

    def oscarRep(self):
	try:
		name = self.name.encode("utf-8","replace")
	except UnicodeError:
		name = 'unknown'
        data = struct.pack(">H", len(name)) + name
        tlvs = TLV(0xc8, struct.pack(">H",len(self.users)))
        data += struct.pack(">4H", self.groupID, self.buddyID, 1, len(tlvs))
        return data+tlvs
       #if len(self.users) > 0:
       #        tlvData = TLV(0xc8, reduce(lambda x,y:x+y, [struct.pack('!H',self.usersToID[x]) for x in self.users]))
       #else:
       #        tlvData = ""
       #  return struct.pack('!H', len(self.name)) + self.name + \
       #         struct.pack('!HH', groupID, buddyID) + '\000\001' + \
       #         struct.pack(">H", len(tlvData)) + tlvData

    def __str__(self):
        s = '<SSIGroup %s (ID %d)' % (self.name, self.buddyID)
        #if len(self.users) > 0:
        #    s=s+' (Members:'+', '.join(self.users)+')'
        s=s+'>'
        return s

    def __repr__(self):
        return self.__str__()


class SSIBuddy:
    def __init__(self, name, groupID, buddyID, tlvs = {}):
        self.name = name
        self.nick = None
        self.groupID = groupID
        self.buddyID = buddyID
        self.tlvs = tlvs
        self.authorizationRequestSent = False
        self.authorized = True
        self.sms = None
        self.email = None
        self.buddyComment = None
        self.alertSound = None
        self.firstMessage = None
        for k,v in tlvs.items():
            if k == 0x0066: # awaiting authorization
                self.authorized = False
            elif k == 0x0131: # buddy nick
                self.nick = v
            elif k == 0x0137: # buddy email
                self.email = v
            elif k == 0x013a: # sms number
                self.sms = v
            elif k == 0x013c: # buddy comment
                self.buddyComment = v
            elif k == 0x013d: # buddy alerts
                actionFlag = ord(v[0])
                whenFlag = ord(v[1])
                self.alertActions = []
                self.alertWhen = []
                if actionFlag&1:
                    self.alertActions.append('popup')
                if actionFlag&2:
                    self.alertActions.append('sound')
                if whenFlag&1:
                    self.alertWhen.append('online')
                if whenFlag&2:
                    self.alertWhen.append('unidle')
                if whenFlag&4:
                    self.alertWhen.append('unaway')
            elif k == 0x013e:
                self.alertSound = v
            elif k == 0x0145: # first time we sent a message to this person
                self.firstMessage = v # unix timestamp
 
    def oscarRep(self):
        data = struct.pack(">H", len(self.name)) + self.name.encode("utf-8")
        tlvs = ""
        if not self.authorized:
            tlvs += TLV(0x0066) # awaiting authorization
        if self.nick:
            tlvs += TLV(0x0131, self.nick)
        if self.email:
            tlvs += TLV(0x0137, self.email)
        if self.sms:
            tlvs += TLV(0x013a, self.sms)
        if self.buddyComment:
            tlvs += TLV(0x013c, self.buddyComment)
        # Should do buddy alerts here too
        if self.alertSound:
            tlvs += TLV(0x013e, self.alertSound)
        if self.firstMessage:
            tlvs += TLV(0x0145, self.firstMessage)
        data += struct.pack(">4H", self.groupID, self.buddyID, 0, len(tlvs))
        return data+tlvs
        #tlvData = reduce(lambda x,y: x+y, map(lambda (k,v):TLV(k,v), self.tlvs.items()), '\000\000')
        #return struct.pack('!H', len(self.name)) + self.name + \
        #       struct.pack('!HH', groupID, buddyID) + '\000\000' + tlvData

    def __str__(self):
        s = '<SSIBuddy %s (ID %d)' % (self.name, self.buddyID)
        s=s+'>'
        return s

    def __repr__(self):
        return self.__str__()


class SSIIconSum:
    def __init__(self, name="1", groupID=0x0000, buddyID=0x51f4, tlvs = {}):
        self.name = name
        self.buddyID = buddyID
        self.groupID = groupID
        self.iconSum = tlvs.get(0xd5,"")

    def updateIcon(self, iconData):
        m=md5.new()
        m.update(iconData)
        self.iconSum = m.digest()
        log.msg("icon sum is %s" % binascii.hexlify(self.iconSum))
 
    def oscarRep(self):
        data = struct.pack(">H", len(self.name)) + self.name.encode("utf-8")
        tlvs = TLV(0x00d5,struct.pack('!BB', 0x00, len(self.iconSum))+self.iconSum)+TLV(0x0131, "")
        data += struct.pack(">4H", self.groupID, self.buddyID, AIM_SSI_TYPE_ICONINFO, len(tlvs))
        return data+tlvs

    def __str__(self):
        s = '<SSIIconSum %s:%s (ID %d)' % (self.name, binascii.hexlify(self.iconSum), self.buddyID)
        s=s+'>'
        return s

    def __repr__(self):
        return self.__str__()


class SSIPDInfo:
    def __init__(self, name="", groupID=0x0000, buddyID=0xffff, tlvs = {}):
        self.name = name
        self.groupID = groupID
        self.buddyID = buddyID
        self.permitMode = tlvs.get(0xca, None)
        self.visibility = tlvs.get(0xcb, None)

    def oscarRep(self):
        data = struct.pack(">H", len(self.name)) + self.name.encode("utf-8")
        tlvs = ""
        if self.permitMode:
            tlvs += TLV(0xca,struct.pack('!B', self.permitMode))
        if self.visibility:
            tlvs += TLV(0xcb,self.visibility)
        data += struct.pack(">4H", self.groupID, self.buddyID, AIM_SSI_TYPE_PDINFO, len(tlvs))
        return data+tlvs

    def __str__(self):
        s = '<SSIPDInfo perm:'
        if self.permitMode:
            s=s+{AIM_SSI_PERMDENY_PERMIT_ALL:'permitall',AIM_SSI_PERMDENY_DENY_ALL:'denyall',AIM_SSI_PERMDENY_PERMIT_SOME:'permitsome',AIM_SSI_PERMDENY_DENY_SOME:'denysome',AIM_SSI_PERMDENY_PERMIT_BUDDIES:'permitbuddies'}.get(ord(self.permitMode),"unknown")
        else:
            s=s+"notset"
        s=s+' visi:'
        if self.visibility:
            s=s+{AIM_SSI_VISIBILITY_ALL:'all',AIM_SSI_VISIBILITY_NOTAIM:'notaim'}.get(self.visibility,"unknown")
        else:
            s=s+"notset"
        s=s+' (ID %d)' % (self.buddyID)
        s=s+'>'
        return s

    def __repr__(self):
        return self.__str__()


class OscarConnection(protocol.Protocol):
    def connectionMade(self):
        self.state=""
        self.seqnum=0
        self.buf=''
        self.outRate=6000
        self.outTime=time.time()
        self.stopKeepAliveID = None
        self.setKeepAlive(240) # 240 seconds = 4 minutes
        self.transport.setTcpNoDelay(True)

    def connectionLost(self, reason):
        log.msg("Connection Lost! %s" % self)
        self.stopKeepAlive()
        self.transport.loseConnection()

    def connectionFailed(self):
        log.msg("Connection Failed! %s" % self)
        self.stopKeepAlive()

    def sendFLAP(self,data,channel = 0x02):
        if not hasattr(self, "seqnum"):
             self.seqnum = 0
        self.seqnum=(self.seqnum+1)%0xFFFF
        seqnum=self.seqnum
        head=struct.pack("!BBHH", 0x2a, channel,
                         seqnum, len(data))
        reactor.callFromThread(self.transport.write,head+str(data))
        #if isinstance(self, ChatService):
        #    logPacketData(head+str(data))

    def readFlap(self):
        if len(self.buf)<6: return # We don't have a whole FLAP yet
        flap=struct.unpack("!BBHH",self.buf[:6])
        if len(self.buf)<6+flap[3]: return # We don't have a whole FLAP yet
        if flap[0] != 0x2a:
            log.msg("WHOA! Illegal FLAP id!  %x" % flap[0])
            return
        data,self.buf=self.buf[6:6+flap[3]],self.buf[6+flap[3]:]
        return [flap[1],data]

    def dataReceived(self,data):
        logPacketData(data)
        self.buf=self.buf+data
        flap=self.readFlap()
        while flap:
            if flap[0] == 0x04:
                # We failed to connect properly
                self.connectionLost("Connection rejected.")
            func=getattr(self,"oscar_%s"%self.state,None)
            if not func:
                log.msg("no func for state: %s" % self.state)
                return
            state=func(flap)
            if state:
                self.state=state
            flap=self.readFlap()

    def setKeepAlive(self,t):
        self.keepAliveDelay=t
        if hasattr(self,"stopKeepAliveID") and self.stopKeepAliveID:
            self.stopKeepAlive()
        self.stopKeepAliveID = reactor.callLater(t, self.sendKeepAlive)

    def sendKeepAlive(self):
        self.sendFLAP("",0x05)
        self.stopKeepAliveID = reactor.callLater(self.keepAliveDelay, self.sendKeepAlive)

    def stopKeepAlive(self):
        if hasattr(self,"stopKeepAliveID") and self.stopKeepAliveID:
            self.stopKeepAliveID.cancel()
            self.stopKeepAliveID = None

    def disconnect(self):
        """
        send the disconnect flap, and sever the connection
        """
        self.sendFLAP('', 0x04)
        def f(reason): pass
        self.connectionLost = f
        self.transport.loseConnection()


class SNACBased(OscarConnection):
    snacFamilies = {
        # family : (version, toolID, toolVersion)
    }
    def __init__(self,cookie):
        self.cookie=cookie
        self.lastID=0
        self.supportedFamilies = {}
        self.requestCallbacks={} # request id:Deferred
        self.scheduler=Scheduler(self.sendFLAP)

    def sendSNAC(self,fam,sub,data,flags=[0,0]):
        """
        send a snac and wait for the response by returning a Deferred.
        """
        if not self.supportedFamilies.has_key(fam):
            log.msg("Ignoring attempt to send unsupported SNAC family %s." % (str(hex(fam))))
            return defer.fail("Attempted to send unsupported SNAC family.")

        reqid=self.lastID
        self.lastID=reqid+1
        d = defer.Deferred()
        d.reqid = reqid

        d.addErrback(self._ebDeferredError,fam,sub,data) # XXX for testing

        self.requestCallbacks[reqid] = d
        snac=SNAC(fam,sub,reqid,data)
        self.scheduler.enqueue(fam,sub,snac)
        return d

    def _ebDeferredError(self, error, fam, sub, data):
        log.msg('ERROR IN DEFERRED %s' % error)
        log.msg('on sending of message, family 0x%02x, subtype 0x%02x' % (fam, sub))
        log.msg('data: %s' % repr(data))

    def sendSNACnr(self,fam,sub,data,flags=[0,0]):
        """
        send a snac, but don't bother adding a deferred, we don't care.
        """
        if not self.supportedFamilies.has_key(fam):
            log.msg("Ignoring attempt to send unsupported SNAC family %s." % (str(hex(fam))))
            return

        snac=SNAC(fam,sub,0x10000*fam+sub,data)
        self.scheduler.enqueue(fam,sub,snac)

    def sendOldICQCommand(self,commandCode,commandData):
        """
        Sends a command to the old ICQ server.
        commandCode - the code of the command to be sent
        commandData - data payload.
        """
        reqid=self.lastID
        self.lastID=reqid+1
        d = defer.Deferred()
        d.reqid = reqid

        # Prepare the ICQ Command data
        data = oldICQCommand(commandCode, commandData, self.username, reqid)

        self.requestCallbacks[reqid] = d
        snac=SNAC(0x15, 0x2, reqid, TLV(1, data))
        self.scheduler.enqueue(0x15,0x2,snac)
        return d

    def oscar_(self,data):
        self.sendFLAP("\000\000\000\001"+TLV(6,self.cookie), 0x01)
        return "Data"

    def oscar_Data(self,data):
        snac=readSNAC(data[1])
        if not snac:
            log.msg("Illegal SNAC data received in oscar_Data: %s" % data)
            return
        if self.requestCallbacks.has_key(snac[4]):
            d = self.requestCallbacks[snac[4]]
            del self.requestCallbacks[snac[4]]
            if snac[1]!=1:
                d.callback(snac)
            else:
                d.errback(snac)
            return
        func=getattr(self,'oscar_%02X_%02X'%(snac[0],snac[1]),None)
        if not func:
            self.oscar_unknown(snac)
        else:
            func(snac)
        return "Data"

    def oscar_unknown(self,snac):
        log.msg("unknown for %s" % self)
        log.msg(snac)


    def oscar_01_03(self, snac):
        numFamilies = len(snac[5])/2
        serverFamilies = struct.unpack("!"+str(numFamilies)+'H', snac[5])
        d = ''
        for fam in serverFamilies:
            log.msg("Server supports SNAC family %s" % (str(hex(fam))))
            self.supportedFamilies[fam] = True
            if self.snacFamilies.has_key(fam):
                d=d+struct.pack('!2H',fam,self.snacFamilies[fam][0])
        self.sendSNACnr(0x01,0x17, d)

    def oscar_01_0A(self,snac):
        """
        change of rate information.
        """
        # this can be parsed, maybe we can even work it in
        try:
            info=struct.unpack('!HHLLLLLLL',snac[5][8:40])
        except struct.error:
            return
        code=info[0]
        rateclass=info[1]
        window=info[2]
        clear=info[3]
        alert=info[4]
        limit=info[5]
        disconnect=info[6]
        current=info[7]
        maxrate=info[8]
      
        self.scheduler.setStat(rateclass,window=window,clear=clear,alert=alert,limit=limit,disconnect=disconnect,rate=current,maxrate=maxrate)

        #need to figure out a better way to do this
        #if (code==3):
        #    import sys
        #    sys.exit()

    def oscar_01_18(self,snac):
        """
        host versions, in the same format as we sent
        """
        self.sendSNACnr(0x01,0x06,"") #pass

    def oscar_04_0B(self, snac):
	"""
	client autoresponse received
	"""
	CustomStatus = {}
	
	snacdata = snac[5]
	buddylen = struct.unpack('!B',snacdata[10:11])[0]
	buddy_end = 11+buddylen
	buddy = snacdata[11:buddy_end] # buddy uin
	
	extdata = snacdata[buddy_end+2:]
	headerlen1 = struct.unpack('<H',extdata[0:2])[0] # skip 'first header' 
	headerlen2 = struct.unpack('<H',extdata[2+headerlen1:4+headerlen1])[0] # skip 'second header' 	
	msg_features_pos = 2 + headerlen1 + 2 + headerlen2
	msgtype = struct.unpack('!B',extdata[msg_features_pos:msg_features_pos+1])[0]
	if msgtype in (0xe7, 0xe8): # auto away message
		log.msg("Received status message response from %s" % buddy)
		msgflags = struct.unpack('!B',extdata[msg_features_pos+1:msg_features_pos+2])[0]
		msgstatus = struct.unpack('!H',extdata[msg_features_pos+2:msg_features_pos+4])[0]
		msgpriority = struct.unpack('!H',extdata[msg_features_pos+4:msg_features_pos+6])[0]	
		msglen = struct.unpack('<H',extdata[msg_features_pos+6:msg_features_pos+8])[0]
		msg = extdata[msg_features_pos+8:msg_features_pos+8+msglen]
		CustomStatus = {}
		CustomStatus['autoaway message'] = msg
	elif msgtype == 0x01: # plain text message
		log.msg("Received plain text message from %s" % buddy)
		self.processIncomingMessageType2(None, extdata)
		# empty msg - seems ask
	else:
		log.msg("Received x-status message response from %s" % buddy)
		buddy = ''
		title = ''
		desc = ''
		UnSafe_Notification = self.extractXStatusNotification(extdata)
					
		title_begin_pos = UnSafe_Notification.find('<title>')
		title_end_pos = UnSafe_Notification.find('</title>')
		if title_begin_pos !=-1 and title_end_pos !=-1:
			title = UnSafe_Notification[title_begin_pos+len('<title>'):title_end_pos]
						
		desc_begin_pos = UnSafe_Notification.find('<desc>')
		desc_end_pos = UnSafe_Notification.find('</desc>')
		if desc_begin_pos !=-1 and desc_end_pos !=-1:
			desc = UnSafe_Notification[desc_begin_pos+len('<desc>'):desc_end_pos]
		
		CustomStatus = {}
		CustomStatus['x-status title'] = title
		CustomStatus['x-status desc'] = desc
		
	if len(CustomStatus) > 0:
		self.oscarcon.legacyList.setCustomStatus(buddy, CustomStatus)
		saved_snac = self.oscarcon.getSavedSnac(buddy)
		if saved_snac != '':
			self.updateBuddy(self.parseUser(saved_snac), True)
			log.msg('Buddy %s updated from saved snac' % buddy)	

    def clientReady(self):
        """
        called when the client is ready to be online
        """
        d = ''
        for fam in self.supportedFamilies:
            log.msg("Checking for client SNAC family support %s" % str(hex(fam)))
            if self.snacFamilies.has_key(fam):
                version, toolID, toolVersion = self.snacFamilies[fam]
                log.msg("    We do support at %s %s %s" % (str(version), str(hex(toolID)), str(hex(toolVersion))))
                d = d + struct.pack('!4H',fam,version,toolID,toolVersion)
        self.sendSNACnr(0x01,0x02,d)
	
    def extractXStatusNotification(self, extdata):
	"""
	extract notification text from extended body of message
        """
	UnSafe_Notification = ''
	
	# skip 'first header' 
	headerlen1 = struct.unpack('<H',extdata[0:2])[0]
	# skip 'second header' 	
	headerlen2 = struct.unpack('<H',extdata[2+headerlen1:4+headerlen1])[0]
	# message type, flags, status and priority. It don't matter usually
	msg_features_pos = 2 + headerlen1 + 2 + headerlen2
	msgtype = struct.unpack('!B',extdata[msg_features_pos:msg_features_pos+1])[0]
	msgflags = struct.unpack('!B',extdata[msg_features_pos+1:msg_features_pos+2])[0]
	msgstatus = struct.unpack('!H',extdata[msg_features_pos+2:msg_features_pos+4])[0]
	msgpriority = struct.unpack('!H',extdata[msg_features_pos+4:msg_features_pos+6])[0]
			
	emptymsglen = struct.unpack('<H',extdata[msg_features_pos+6:msg_features_pos+8])[0]
				
	msgcontent_pos = msg_features_pos + 8 + emptymsglen
	msgcontent = extdata[msgcontent_pos:]
			
	if len(msgcontent) > 0:
		PluginTypeIdLen = struct.unpack('<H',msgcontent[0:2])[0]
		# check for xtraz request
		MsgTypeId = struct.unpack('!LLLL',msgcontent[2:18])
		if MsgTypeId == MSGTYPE_ID_XTRAZ_SCRIPT:
			MsgSubType = struct.unpack('<H',msgcontent[18:20])[0]
			if MsgSubType == MSGSUBTYPE_SCRIPT_NOTIFY:
				MsgAction = struct.unpack('<L',msgcontent[20:24])[0]
				if MsgAction == MSGACTION_REQUEST_TYPE_STRING:
					MsgActionText = msgcontent[24:PluginTypeIdLen + 2 - 15]
					# 15 bytes after - unknown
					NotificationLen = struct.unpack('<LL',msgcontent[PluginTypeIdLen+2:PluginTypeIdLen+10])[1]
					Notification = msgcontent[PluginTypeIdLen+10:PluginTypeIdLen+10+NotificationLen]
					# TODO: parse as XML
					UnSafe_Notification = utils.getUnSafeXML(Notification)
	return UnSafe_Notification
				
    def processIncomingMessageType2(self, user, extdata, cookie=None):
	"""
	process data in incoming type-2 message
	"""
	encoding = 'unknown'
	
	# skip 'first header' 
	headerlen1 = struct.unpack('<H',extdata[0:2])[0]
	# skip 'second header' 	
	headerlen2 = struct.unpack('<H',extdata[2+headerlen1:4+headerlen1])[0]
	# message type, flags, status and priority. It don't matter usually
	msg_features_pos = 2 + headerlen1 + 2 + headerlen2
	msgtype = struct.unpack('!B',extdata[msg_features_pos:msg_features_pos+1])[0]
	msgflags = struct.unpack('!B',extdata[msg_features_pos+1:msg_features_pos+2])[0]
	msgstatus = struct.unpack('!H',extdata[msg_features_pos+2:msg_features_pos+4])[0]
	msgpriority = struct.unpack('!H',extdata[msg_features_pos+4:msg_features_pos+6])[0]	
	msglen = struct.unpack('<H',extdata[msg_features_pos+6:msg_features_pos+8])[0]
	msg = extdata[msg_features_pos+8:msg_features_pos+8+msglen]

	msgcontent_pos = msg_features_pos + 8 + msglen
	msgcontent = extdata[msgcontent_pos:]
	# check encoding
	if len(msgcontent) >= 0x2E:
		foreground_color = struct.unpack('<L', msgcontent[0:4])[0] # TODO: use this stuff
		background_color = struct.unpack('<L', msgcontent[4:8])[0] # TODO: use this stuff
		cap_len = struct.unpack('<L', msgcontent[8:12])[0]
		if cap_len == 0x26:
			cap = msgcontent[12:12+cap_len]
			if cap == MSGTYPE_TEXT_ID_UTF8MSGS:
				encoding = "utf8"
	# do actions			
	if msglen == 1 and msg == '\x00': # is message ack
		pass # TODO: add XEP-0184: Message Receipts support
	elif user: # usual message
		# prepare message
		delay = None
		flags = []
		multiparts = []
		message = [msg]
		message.append(encoding)
		if msglen > 0:
			multiparts.append(tuple(message))
		# send it to user's jabber client
		self.receiveMessage(user, multiparts, flags, delay)
		# send confirmation
		if self.settingsOptionEnabled('send_confirm_for_ut8_msg'):
			self.sendMessageType2Confirmation(user.name, cookie)


class BOSConnection(SNACBased):
    #snacFamilies = {
    #    0x01:(3, 0x0110, 0x0629),
    #    0x02:(1, 0x0110, 0x0629),
    #    0x03:(1, 0x0110, 0x0629),
    #    0x04:(1, 0x0110, 0x0629),
    #    0x06:(1, 0x0110, 0x0629),
    #    0x08:(1, 0x0104, 0x0001),
    #    0x09:(1, 0x0110, 0x0629),
    #    0x0a:(1, 0x0110, 0x0629),
    #    0x0b:(1, 0x0104, 0x0001),
    #    0x0c:(1, 0x0104, 0x0001),
    #    0x13:(3, 0x0110, 0x0629),
    #    0x15:(1, 0x0110, 0x047c)
    #}
    snacFamilies = {
        0x01:(4, 0x0110, 0x08e4),
        0x02:(1, 0x0110, 0x08e4),
        0x03:(1, 0x0110, 0x08e4),
        0x04:(1, 0x0110, 0x08e4),
        0x06:(1, 0x0110, 0x08e4),
        0x08:(1, 0x0104, 0x0001),
        0x09:(1, 0x0110, 0x08e4),
        0x0a:(1, 0x0110, 0x08e4),
        0x0b:(1, 0x0104, 0x08e4),
        0x0c:(1, 0x0104, 0x0001),
        0x13:(4, 0x0110, 0x08e4),
        0x15:(1, 0x0110, 0x08e4)
    }

    capabilities = None
    statusindicators = 0x0000
    icqStatus = 0x0000

    def __init__(self,username,cookie):
        SNACBased.__init__(self,cookie)
        self.username=username
        self.profile = None
        self.awayMessage = None
        self.services = {}
        self.socksProxyServer = None
        self.socksProxyPort = None
        self.connectPort = 5190
        # Note that this is "no unicode" default encoding
        # We use unicode if it's there
        self.defaultEncoding = config.encoding

        if not self.capabilities:
            self.capabilities = [CAP_CHAT]

	self.ssistats = dict([])
	self.ssistats['buddies'] = 0
	self.ssistats['phantombuddies'] = 0
	self.ssistats['groups'] = 0
	self.ssistats['ssipackets'] = 0
	self.ssistats['least_groupID'] = -1

	self.selfCustomStatus = dict([])
	self.selfSettings = dict([])
	self.icqStatus = 0x0000
	self.updateSelfXstatusOnStart = False
	
	if hasattr(self.session,'pytrans'):
		self.selfSettings = self.session.pytrans.xdb.getCSettingList(self.session.jabberID)
		self.selfSettings = self.addSelfSettingsByDefault(self.selfSettings)
		log.msg("CSettings for user %s is %s" % (self.session.jabberID, self.selfSettings))
	
		if config.xstatusessupport:
			if self.settingsOptionEnabled('xstatus_saving_enabled'):
				if 'latest_xstatus_number' in self.selfSettings: # if it saved
					latest_xstatus_number = self.selfSettings['latest_xstatus_number']
					if int(latest_xstatus_number) > 0:
						self.selfCustomStatus['x-status name'] = X_STATUS_NAME[int(latest_xstatus_number)]
						self.selfCustomStatus['x-status title'], self.selfCustomStatus['x-status desc'] = self.session.pytrans.xdb.getXstatusText(self.session.jabberID, latest_xstatus_number)
					if int(self.settingsOptionValue('xstatus_sending_mode')) != 0:
						self.updateSelfXstatusOnStart = True
		log.msg("CustomStatus for user %s is %s" % (self.session.jabberID, self.selfCustomStatus))

    def addSelfSettingsByDefault(self, settings = None):
	dsettings = dict([
	('xstatus_receiving_mode', 0),
	('xstatus_sending_mode', 0),
	('xstatus_saving_enabled', 1),
	('xstatus_option_smooth', 1),
	('xstatus_display_icon_as_PEP', 1),
	('xstatus_display_text_as_PEP', 1),
	('away_messages_receiving', 1),
	('clist_show_phantombuddies', 0),
	('utf8_messages_sendmode', 1),
	('send_confirm_for_ut8_msg', 1)
	])
	if settings and len(settings) != 0:
		for key in settings:
			dsettings[key] = settings[key]
	return dsettings
		
    def addToSelfSettings(self, settings = None):
	if settings:
		for key in settings:
			self.selfSettings[key] = settings[key]

    def parseUser(self,data,wantRest=0):
        l=ord(data[0])
        name=data[1:1+l]
        warn,tlvcnt=struct.unpack("!HH",data[1+l:5+l])
        warn=int(warn/10)
        #if count == None:
        #    tlvs,rest = readTLVs(data[5+l:]), None
        #else:
        #    tlvs,rest = readTLVs(data[5+l:],tlvcnt)
        tlvs,rest = readTLVs(data[5+l:],tlvcnt)
        u = OSCARUser(name, warn, tlvs)
        if wantRest:
            return u, rest
        else:
            return u

    def parseProfile(self, data):
        l=ord(data[0])
        warn, tlvcnt = struct.unpack("!HH",data[1+l:5+l])
        return readTLVs(data[5+l:], tlvcnt)[0]

    def parseAway(self, data):
        l=ord(data[0])
        warn, tlvcnt = struct.unpack("!HH",data[1+l:5+l])
        return readTLVs(data[5+l:], tlvcnt)[0]


    def parseMoreInfo(self, data):
        # why did i have this here and why did dsh remove it
        #result = ord(data[0])
        #if result != 0xa:
        #    return

        pos = 3
        homepagelen = struct.unpack("<H", data[pos:pos+2])[0]
        pos += 2
        homepage = data[pos:pos+homepagelen-1]

        pos += homepagelen
        year  = struct.unpack("<H", data[pos:pos+2])[0]
        month = struct.unpack("B", data[pos+2:pos+3])[0]
        day   = struct.unpack("B", data[pos+3:pos+4])[0]
        if year and month and day:
            birth = "%04d-%02d-%02d"%(year,month,day)
        else:
            birth = ""
 
        return homepage,birth

    def parseWorkInfo(self, data):
        #result = ord(data[0])
        #if result != 0xa:
        #    return

        pos = 0
        citylen = struct.unpack("<H",data[pos:pos+2])[0]
        pos += 2
        city = data[pos:pos+citylen-1]

        pos += citylen
        statelen = struct.unpack("<H",data[pos:pos+2])[0]
        pos += 2
        state = data[pos:pos+statelen-1]

        pos += statelen
        phonelen = struct.unpack("<H",data[pos:pos+2])[0]
        pos += 2
        phone = data[pos:pos+phonelen-1]

        pos += phonelen
        faxlen = struct.unpack("<H",data[pos:pos+2])[0]
        pos += 2
        fax = data[pos:pos+faxlen-1]

        pos += faxlen
        addresslen = struct.unpack("<H",data[pos:pos+2])[0]
        pos += 2
        address = data[pos:pos+addresslen-1]

        pos += addresslen
        ziplen = struct.unpack("<H",data[pos:pos+2])[0]
        pos += 2
        zip = data[pos:pos+ziplen-1]

        pos += ziplen
        countrycode = struct.unpack(">H",data[pos:pos+2])[0]
        if countrycode in countrycodes.countryCodes:
            country = countrycodes.countryCodes[countrycode]
        else:
            country = ""

        pos += 2
        companylen = struct.unpack("<H",data[pos:pos+2])[0]
        pos += 2
        company = data[pos:pos+companylen-1]

        pos += companylen
        departmentlen = struct.unpack("<H",data[pos:pos+2])[0]
        pos += 2
        department = data[pos:pos+departmentlen-1]

        pos += departmentlen
        positionlen = struct.unpack("<H",data[pos:pos+2])[0]
        pos += 2
        position = data[pos:pos+positionlen-1]

        return city,state,phone,fax,address,zip,country,company,department,position

    def parseNotesInfo(self, data):
        #result = ord(data[0])
        #if result != 0xa:
        #    return

        noteslen = struct.unpack("<H", data[0:2])[0]
        notes = data[2:2+noteslen-1]
        return notes

    def parseFullInfo(self, data):
        #result = ord(data[0])
        #if result != 0xa:
        #    return
        pos = 0
        nicklen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        nick = data[pos:pos + nicklen - 1]

        pos += nicklen
        firstlen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        first = data[pos:pos + firstlen - 1]

        pos += firstlen
        lastlen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        last = data[pos:pos + lastlen - 1]

        pos += lastlen
        emaillen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        email = data[pos:pos + emaillen - 1]

        pos += emaillen
        homeCitylen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        homeCity = data[pos:pos + homeCitylen - 1]

        pos += homeCitylen
        homeStatelen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        homeState = data[pos:pos + homeStatelen - 1]

        pos += homeStatelen
        homePhonelen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        homePhone = data[pos:pos + homePhonelen - 1]

        pos += homePhonelen
        homeFaxlen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        homeFax = data[pos:pos + homeFaxlen - 1]

        pos += homeFaxlen
        homeAddresslen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        homeAddress = data[pos:pos + homeAddresslen - 1]

        pos += homeAddresslen
        cellPhonelen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        cellPhone = data[pos:pos + cellPhonelen - 1]

        pos += cellPhonelen
        homeZiplen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        homeZip = data[pos:pos + homeZiplen - 1]

        pos += homeZiplen
        homeCountrycode = struct.unpack("<H", data[pos:pos+2])[0]

        if homeCountrycode in countrycodes.countryCodes:
            homeCountry = countrycodes.countryCodes[homeCountrycode]
        else:
            homeCountry = ""

        return nick,first,last,email,homeCity,homeState,homePhone,homeFax,homeAddress,cellPhone,homeZip,homeCountry

    def parseBasicInfo(self,data):
        pos = 0
        result = ord(data[pos])
        if result != 0x0a:
            return None,None,None,None
        pos += 1
        nicklen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        nick = data[pos:pos + nicklen - 1]

        pos += nicklen
        firstlen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        first = data[pos:pos + firstlen - 1]

        pos += firstlen
        lastlen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        last = data[pos:pos + lastlen - 1]

        pos += lastlen
        emaillen = struct.unpack('<H', data[pos:pos+2])[0]
        pos += 2
        email = data[pos:pos + emaillen - 1]

        return nick,first,last,email

    def oscar_01_05(self, snac, d = None):
        """
        data for a new service connection
        d might be a deferred to be called back when the service is ready
        """
        tlvs = readTLVs(snac[5][0:])
        service = struct.unpack('!H',tlvs[0x0d])[0]
        ip = tlvs[5]
        cookie = tlvs[6]

        def addService(x):
            self.services[service] = x

        #c = serviceClasses[service](self, cookie, d)
        if self.socksProxyServer and self.socksProxyPort:
            c = protocol.ProxyClientCreator(reactor, serviceClasses[service], self, cookie, d)
            c.connectSocks5Proxy(ip, self.connectPort, self.socksProxyServer, int(self.socksProxyPort), "BOSCONN").addCallback(addService)
        else:
            c = protocol.ClientCreator(reactor, serviceClasses[service], self, cookie, d)
            c.connectTCP(ip, self.connectPort).addCallback(addService)
        #self.services[service] = c

    def oscar_01_07(self,snac):
        """
        rate paramaters
        """
        self.outRateInfo={}
        self.outRateTable={}
        count=struct.unpack('!H',snac[5][0:2])[0]
        snac[5]=snac[5][2:]
        for i in range(count):
            info=struct.unpack('!HLLLLLLL',snac[5][:30])
            classid=info[0]
            window=info[1]
            clear=info[2]
            currentrate=info[6]
            lasttime=time.time()
            maxrate=info[7]
            self.scheduler.setStat(classid,window=window,clear=clear,rate=currentrate,lasttime=lasttime,maxrate=maxrate)
            snac[5]=snac[5][35:]

        while (len(snac[5]) > 0):
            info=struct.unpack('!HH',snac[5][:4])
            classid=info[0]
            count=info[1]
            info=struct.unpack('!'+str(2*count)+'H',snac[5][4:4+count*4])
            while (len(info)>0):
                fam,sub=str(info[0]),str(info[1])
                self.scheduler.bindIntoClass(fam,sub,classid)
                info=info[2:]
            snac[5]=snac[5][4+count*4:]             

        self.sendSNACnr(0x01,0x08,"\x00\x01\x00\x02\x00\x03\x00\x04\x00\x05") # ack
        self.initDone()
        self.sendSNACnr(0x13,0x02,'') # SSI rights info
        self.sendSNACnr(0x02,0x02,'') # location rights info
        self.sendSNACnr(0x03,0x02,'') # buddy list rights
        self.sendSNACnr(0x04,0x04,'') # ICBM parms
        self.sendSNACnr(0x09,0x02,'') # BOS rights

    def oscar_01_0F(self,snac):
        """
        Receive Self User Info
        """
        log.msg('Received Self User Info %s' % str(snac))
        self.receivedSelfInfo(self.parseUser(snac[5]))

    def oscar_01_10(self,snac):
        """
        we've been warned
        """
        skip = struct.unpack('!H',snac[5][:2])[0]
        newLevel = struct.unpack('!H',snac[5][2+skip:4+skip])[0]/10
        if len(snac[5])>4+skip:
            by = self.parseUser(snac[5][4+skip:])
        else:
            by = None
        self.receiveWarning(newLevel, by)

    def oscar_01_13(self,snac):
        """
        MOTD
        """
        motd_msg_type = struct.unpack('!H', snac[5][:2])[0]
        if MOTDS.has_key(motd_msg_type):
            tlvs = readTLVs(snac[5][2:])
            motd_msg_string = tlvs[0x0b]

    def oscar_01_21(self,snac):
        """
        Receive extended status info
        """
        v = snac[5]
        log.msg('Received self extended status info for %s: %s' % (self.username, str(snac)))

        while len(v)>4 and ord(v[0]) == 0 and ord(v[3]) != 0:
            exttype = (struct.unpack('!H',v[0:2]))[0]
            if exttype == 0x00 or exttype == 0x01: # Why are there two?
                iconflags, iconhashlen = struct.unpack('!BB',v[2:4])
                iconhash = v[4:4+iconhashlen]
                log.msg("   extracted icon hash: flags = %s, flags-as-hex = %s, iconhash = %s" % (bitstostr(iconflags, 8), str(hex(iconflags)), binascii.hexlify(iconhash)))
                if iconflags == 0x41:
                    self.receivedIconUploadRequest(iconhash)
            elif exttype == 0x02: # Extended Status Message
                # I'm not sure if we should do something about this here?
		statlen=int((struct.unpack('!H', v[4:6]))[0])
		status=v[6:6+statlen]
		log.msg("   extracted status message: %s"%(status))
		self.status = status
	    elif exttype == 0x06: # online status
		st_len = int((struct.unpack('!H', v[2:4]))[0])
		if st_len == 4:
			st_ind = int((struct.unpack('!H', v[4:6]))[0])
			st_cod = int((struct.unpack('!H', v[6:8]))[0])
			if st_cod == 0x00:
				status = 'online'
		        elif st_cod == 0x01:
            			status = 'away'
			elif st_cod == 0x02:
            			status = 'dnd'
			elif st_cod == 0x04:
            			status = 'xa'
			elif st_cod == 0x20:
            			status = 'chat'
			else:
				status = 'unknown: %s' % st_cod
			log.msg("   extracted online status: %s"%(status))
	    elif exttype == 0x0e: # ICQ6 mood only or mood + available message?
		mood_str_len = int((struct.unpack('!H', v[2:4]))[0])
		mood_str = v[4:4+mood_str_len]
		log.msg("   extracted icqmood: %s" % (mood_str))
            else:
                log.msg("   unknown extended status type: %d\ndata: %s"%(ord(v[1]), repr(v[:ord(v[3])+4])))
            v=v[ord(v[3])+4:]

    def oscar_02_03(self, snac):
        """
        location rights response
        """
        tlvs = readTLVs(snac[5])
        self.maxProfileLength = tlvs[1]

    def oscar_03_03(self, snac):
        """
        buddy list rights response
        """
        tlvs = readTLVs(snac[5])
        self.maxBuddies = tlvs[1]
        self.maxWatchers = tlvs[2]

    def oscar_03_0B(self, snac):
        """
        buddy update
        """
	l=ord(snac[5][0]) # uin length
        name=snac[5][1:1+l] # uin
        self.updateBuddy(self.parseUser(snac[5])) # update buddy
	self.oscarcon.setSavedSnac(name, snac[5]) # save snac (will used on Xstatus message response)

    def oscar_03_0C(self, snac):
        """
        buddy offline
        """
        self.offlineBuddy(self.parseUser(snac[5]))

    def oscar_04_01(self, snac):
        """
        ICBM Error
        """
        data = snac[5]
        errorcode = struct.unpack('!H',data[:2])[0]
        data = data[2:]
        if errorcode==0x04:
            errortxt="client is offline"
        elif errorcode==0x09:
            errortxt="this message not supported by client"
        elif errorcode==0x0e:
            errortxt="invalid (incorrectly formatted) message"
        elif errorcode==0x10:
            errortxt="the receiver or sender is blocked"
        else:
            errortxt="an unknown error has occured. (0x%02x)"%(errorcode)
        
        log.msg('ICBM Error: %s' % (errortxt))
        self.errorMessage('Unable to deliver message because %s' % (errortxt))
        log.msg(snac)

    def oscar_04_05(self, snac):
        """
        ICBM parms response
        """
        self.sendSNACnr(0x04,0x02,'\x00\x00\x00\x00\x00\x0b\x1f@\x03\xe7\x03\xe7\x00\x00\x00\x00') # IM rights

    def oscar_04_07(self, snac):
        """
        ICBM message (instant message)
        """
        data = snac[5]
        cookie, data = data[:8], data[8:]
        channel = struct.unpack('!H',data[:2])[0]
        log.msg("channel = %d" % (channel))
        data = data[2:]
        user, data = self.parseUser(data, 1)
        log.msg("user = %s, data = %s" % (user, binascii.hexlify(data)))
        tlvs = readTLVs(data)
        log.msg("tlvs = %s" % (tlvs))
        if channel == 1: # message
	    delay = None # time of message receiving
            flags = []
            multiparts = []
            for k, v in tlvs.items():
                if k == 0x02: # message data
                    log.msg("Message data: %s" % (repr(v)))
                    while v:
                        #2005/09/25 13:55 EDT [B,client] Message data: '\x05\x01\x00\x01\x01\x01\x01\x00\xaf\x00\x03\x00\x00<html><body ichatballooncolor="#7BB5EE" ichattextcolor="#000000"><font face="Courier" ABSZ=12 color="#000000">test\xe4ng the transport for fun and profit</font></body></html>'
                        fragtype,fragver,fraglen = struct.unpack('!BBH', v[:4])
                        if fragtype == 0x05:
                            # This is a required capabilities list
                            # We really have no idea what to do with this...
                            # actual capabilities seen have been 0x01... text?
                            # we shall move on with our lives
                            pass
                        elif fragtype == 0x01:
                            # This is what we're realllly after.. message data.
                            charSet, charSubSet = struct.unpack('!HH', v[4:8])
                            messageLength = fraglen - 4 # ditch the charsets
                            message = [v[8:8+messageLength]]

                            if charSet == 0x0000:
                                message.append('ascii')
                            elif charSet == 0x0002:
                                message.append('unicode')
                            elif charSet == 0x0003:
                                message.append('custom') # iso-8859-1?
                            elif charSet == 0xffff:
                                message.append('none')
                            else:
                                message.append('unknown')

                            if charSubSet == 0x0000:
                                message.append('standard')
                            elif charSubSet == 0x000b:
                                message.append('macintosh')
                            elif charSubSet == 0xffff:
                                message.append('none')
                            else:
                                message.append('unknown')
				
				log.msg("Encoding: %s" % charSubSet)
			
                            if messageLength > 0:
					multiparts.append(tuple(message))	
                        else:
                            # Uh... what is this???
                            log.msg("unknown message fragment %d %d: %s" % (fragtype, fragver, str(v)))
                        v = v[4+fraglen:]
                elif k == 0x03: # server ack requested
                    flags.append('acknowledge')
                elif k == 0x04: # message is auto response
                    flags.append('auto')
                elif k == 0x06: # message received offline
                    flags.append('offline')
                elif k == 0x08: # has a buddy icon
                    iconLength, foo, iconSum, iconStamp = struct.unpack('!LHHL',v)
                    if iconLength:
                        flags.append('icon')
                        # why exactly was I doing it like this?
                        #flags.append((iconLength, iconSum, iconStamp))
                        user.iconcksum = iconSum
                        user.iconlen = iconLength
                        user.iconstamp = iconStamp
                elif k == 0x09: # request for buddy icon
                    flags.append('iconrequest')
                elif k == 0x0b: # non-direct connect typing notification
                    flags.append('typingnot')
                elif k == 0x17: # extra data.. wonder what this is?
                    flags.append('extradata')
                    flags.append(v)
		elif k == 0x16: # message timestamp
			s = struct.unpack('!I',v)
			dt = datetime.datetime.utcfromtimestamp(s[0])
			delay=dt.isoformat().replace('Z','')+'Z' # datetime in format 2008-06-20T20:14:21Z
			log.msg("Timestamp: %s, datetime %s" % (s,dt))
			log.msg("Multiparts: %s" % multiparts)
			log.msg("Flags: %s" % flags)
                else:
                    log.msg('unknown TLV for incoming IM, %04x, %s' % (k,repr(v)))

                    #  unknown tlv for user SNewdorf
                    #  t: 29
                    #  v: '\x00\x00\x00\x05\x02\x01\xd2\x04r\x00\x01\x01\x10/\x8c\x8b\x8a\x1e\x94*\xbc\x80}\x8d\xc4;\x1dEM'
                    # XXX what is this?
		    
	    uvars = {}
	    uvars['utf8_msg_using'] = 0 # is not utf8 message
	    self.oscarcon.legacyList.setUserVars(user.name, uvars)

            self.receiveMessage(user, multiparts, flags, delay)
        elif channel == 2: # rendezvous
            status = struct.unpack('!H',tlvs[5][:2])[0]
            cookie2 = tlvs[5][2:10]
            requestClass = tlvs[5][10:26]
            moreTLVs = readTLVs(tlvs[5][26:])
            if requestClass == CAP_CHAT: # a chat request
                exchange = None
                name = None
                instance = None
                if moreTLVs.has_key(10001):
                    exchange = struct.unpack('!H',moreTLVs[10001][:2])[0]
                    name = moreTLVs[10001][3:-2]
                    instance = struct.unpack('!H',moreTLVs[10001][-2:])[0]
                if not exchange or not name or not instance:
                    self.chatInvitationAccepted(user)
                    return
                if not self.services.has_key(SERVICE_CHATNAV):
                    self.connectService(SERVICE_CHATNAV,1).addCallback(lambda x: self.services[SERVICE_CHATNAV].getChatInfo(exchange, name, instance).\
                        addCallback(self._cbGetChatInfoForInvite, user, moreTLVs[12]))
                else:
                    self.services[SERVICE_CHATNAV].getChatInfo(exchange, name, instance).\
                        addCallback(self._cbGetChatInfoForInvite, user, moreTLVs[12])
            elif requestClass == CAP_SEND_FILE:
                if moreTLVs.has_key(11): # cancel
                    log.msg('cancelled file request')
                    log.msg(status)
                    return # handle this later
                if moreTLVs.has_key(10001):
                    name = moreTLVs[10001][9:-7]
                    desc = moreTLVs[12]
                    log.msg('file request from %s, %s, %s' % (user, name, desc))
                    self.receiveSendFileRequest(user, name, desc, cookie)
            elif requestClass == CAP_ICON:
                if moreTLVs.has_key(10001):
                    checksum,length,timestamp = struct.unpack('!III',moreTLVs[10001][:12])
                    length = int(length)
                    icondata = moreTLVs[10001][12:12+length+1]
                    user.iconcksum = checksum
                    user.iconlen = length
                    user.iconstamp = timestamp
                    log.msg('received icbm icon, length %d' % (length))
                    self.receivedIconDirect(user, icondata)
            elif requestClass == CAP_SEND_LIST:
                pass
            elif requestClass == CAP_SERV_REL:
                if 0x2711 in moreTLVs:
			# Extended data
			extdata = moreTLVs[0x2711]
			headerlen1 = struct.unpack('<H',extdata[0:2])[0] # skip 'first header' 
			headerlen2 = struct.unpack('<H',extdata[2+headerlen1:4+headerlen1])[0] # skip 'second header' 	
			msg_features_pos = 2 + headerlen1 + 2 + headerlen2
			msgtype = struct.unpack('!B',extdata[msg_features_pos:msg_features_pos+1])[0]
			if msgtype in (0xe7, 0xe8): # auto away message
				log.msg('Request for status details from %s' % user.name)
				if config.xstatusessupport:
					if int(self.settingsOptionValue('xstatus_sending_mode')) in (1,3):
						self.sendStatusMessageResponse(user.name, cookie2)
			elif msgtype == 0x01: # plain text message
				log.msg('Plain text message from %s' % user.name)
				uvars = {}
				uvars['utf8_msg_using'] = 1 # is utf8 message
				self.oscarcon.legacyList.setUserVars(user.name, uvars) # set vars
				self.processIncomingMessageType2(user, extdata, cookie2) # send message to jabber-client
			else:
				try:
					UnSafe_Notification = self.extractXStatusNotification(extdata)
					request_pos_begin = UnSafe_Notification.find('<req><id>AwayStat</id>')
					request_pos_end = UnSafe_Notification.find('</req>')
					if request_pos_begin != -1 and request_pos_end != -1 and request_pos_begin < request_pos_end:
						log.msg('Request for x-status details from %s' % user.name)
						if config.xstatusessupport:
							if int(self.settingsOptionValue('xstatus_sending_mode')) in (1,3):
								self.sendXstatusMessageResponse(user.name, cookie2)
				except:
					log.msg('Strange rendezvous')
					log.msg(repr(moreTLVs))
		else:
			log.msg('more TLVs for serv_relay: %s' % moreTLVs)
            else:
                log.msg('unsupported rendezvous: %s' % requestClass)
                log.msg(repr(moreTLVs))
        elif channel == 4:
            for k,v in tlvs.items():
                if k == 5:
                    # message data
                    uinHandle = struct.unpack("<I", v[:4])[0]
                    uin = "%s"%uinHandle
                    messageType = ord(v[4])
                    messageFlags = ord(v[5])
                    messageStringLength = struct.unpack("<H", v[6:8])[0]
                    messageString = v[8:8+messageStringLength]
                    message = [messageString]
                    messageParts = re.split('\xfe', messageString)
                    log.msg("messageParts = %s" % (messageParts))

                    #log.msg("type = %d" % (messageType))
                    #log.msg("uin = %s" % (uin))
                    #log.msg("flags = %d" % (messageFlags))
                    #log.msg("strlen = %d" % (messageStringLength))
                    #log.msg("msg = %s" % (messageString))
                    if messageType == 0x01:
                        # old style plain text message
                        log.msg("received plain text message")
                        flags = []
                        multiparts = []
                        if messageStringLength > 0: multiparts.append(tuple(message))
                        self.receiveMessage(user, multiparts, flags)
                    elif messageType == 0x02:
                        # chat request message
                        log.msg("received chat request message")
                        pass
                    elif messageType == 0x03:
                        # file request/file ok message
                        log.msg("received file request message")
                        pass
                    elif messageType == 0x04:
                        # url message
                        log.msg("received url message")
                        pass
                    elif messageType == 0x06:
                        # authorization request
                        self.gotAuthorizationRequest(uin)
                    elif messageType == 0x07:
                        # authorization denied
                        self.gotAuthorizationResponse(uin, False)
                    elif messageType == 0x08:
                        # authorization ok
                        self.gotAuthorizationResponse(uin, True)
                    elif messageType == 0x09:
                        # message from oscar server
                        log.msg("received oscar server message")
                        pass
                    elif messageType == 0x0c:
                        # you were added message
                        log.msg("received you were added message")
                        pass
                    elif messageType == 0x0d:
                        # web pager message
                        log.msg("received web pager message")
                        flags = []
                        multiparts = []
                        msg = "ICQ page from %s [%s]\n%s" % (messageParts[0], messageParts[3], messageParts[5])
                        if messageStringLength > 0: multiparts.append(tuple([msg]))
                        self.receiveMessage(user, multiparts, flags)
                    elif messageType == 0x0e:
                        # email express message
                        log.msg("received email express message")
                        flags = []
                        multiparts = []
                        msg = "ICQ e-mail from %s [%s]\n%s" % (messageParts[0], messageParts[3], messageParts[5])
                        if messageStringLength > 0: multiparts.append(tuple([msg]))
                        self.receiveMessage(user, multiparts, flags)
                    elif messageType == 0x13:
                        # contact list message (send contacts for buddy list)
                        log.msg("received contact list message")
                        pass
                    elif messageType == 0x1a:
                        # plugin message
                        log.msg("received plugin message")
                        pass
                    elif messageType == 0xe8:
                        # automatic away message
                        log.msg("received autoaway message")
                        pass
                    elif messageType == 0xe9:
                        # automatic busy message
                        log.msg("received autobusy message")
                        pass
                    elif messageType == 0xea:
                        # automatic not available message
                        log.msg("received auton/a message")
                        pass
                    elif messageType == 0xeb:
                        # automatic do not disturb message
                        log.msg("received autodnd message")
                        pass
                    elif messageType == 0xec:
                        # automatic free for chat message
                        log.msg("received autoffc message")
                        pass
        else:
            log.msg('unknown channel %02x' % channel)
            log.msg(tlvs)

    def oscar_04_0C(self, snac):
        """
        ICBM message ack
        """
        log.msg("Received message ack: %s" % (snac))
        pass

    def oscar_04_14(self, snac):
        """
        client/server typing notifications
        """
        data = snac[5]
        scrnnamelen = int(struct.unpack('B',data[10:11])[0])
        scrnname = str(data[11:11+scrnnamelen])
        typestart = 11+scrnnamelen+1
        type = struct.unpack('B', data[typestart])[0]
        tlvs = dict()
        user = OSCARUser(scrnname, None, tlvs)

        if (type == 0x02):
            self.receiveTypingNotify("begin", user)
        elif (type == 0x01):
            self.receiveTypingNotify("idle", user)
        elif (type == 0x00):
            self.receiveTypingNotify("finish", user)

    def _cbGetChatInfoForInvite(self, info, user, message):
        apply(self.receiveChatInvite, (user,message)+info)

    def oscar_09_03(self, snac):
        """
        BOS rights response
        """
        tlvs = readTLVs(snac[5])
        self.maxPermitList = tlvs[1]
        self.maxDenyList = tlvs[2]

    def oscar_0B_02(self, snac):
        """
        stats reporting interval
        """
        self.reportingInterval = struct.unpack('!H',snac[5][:2])[0]

    def oscar_13_03(self, snac):
        """
        SSI rights response
        """
        #tlvs = readTLVs(snac[5])
        pass # we don't know how to parse this

    def oscar_13_08(self, snac):
        # SSI Edit: add items
        # Why does this come to the client?
        pass
        #uinLen = ord(snac[5][pos])
        #uin = snac[5][pos+1:pos+1+uinLen]

    def oscar_13_0E(self, snac):
        """
        SSI modification response
        """
        #tlvs = readTLVs(snac[5])
        pass # we don't know how to parse this

    def oscar_13_19(self, snac):
        """
        Got authorization request
        """
        pos = 0
        #if 0x80 & snac[2] or 0x80 & snac[3]:
        #    sLen,id,length = struct.unpack(">HHH", snac[5][:6])
        #    pos = 6 + length
        uinlen = ord(snac[5][pos])
        pos += 1
        uin = snac[5][pos:pos+uinlen]
        pos += uinlen
        self.gotAuthorizationRequest(uin)

    def oscar_13_1B(self, snac):
        """
        Got authorization response
        """
        pos = 0
        #if 0x80 & snac[2] or 0x80 & snac[3]:
        #    sLen,id,length = struct.unpack(">HHH", snac[5][:6])
        #    pos = 6 + length
        uinlen = ord(snac[5][pos])
        pos += 1
        uin = snac[5][pos:pos+uinlen]
        pos += uinlen
        success = ord(snac[5][pos])
        pos += 1
        reasonlen = struct.unpack(">H", snac[5][pos:pos+2])[0]
        pos += 2
        reason = snac[5][pos:]
        if success:
            # authorization request successfully granted
            self.gotAuthorizationResponse(uin, True)
        else:
            # authorization request was not granted
            self.gotAuthorizationResponse(uin, False)

    def oscar_13_1C(self, snac):
        """
        SSI Your were added to someone's buddylist
        """
        pos = 0
        #if 0x80 & snac[2] or 0x80 & snac[3]:
        #    sLen,id,length = struct.unpack(">HHH", snac[5][:6])
        #    pos = 6 + length
        #    val = snac[5][4:pos]
        uinLen = ord(snac[5][pos])
        uin = snac[5][pos+1:pos+1+uinLen]
        self.youWereAdded(uin)

# Methods to be called by the client, and their support methods
    def requestSelfInfo(self):
        """
        ask for the OSCARUser for ourselves
        """
        d = defer.Deferred()
        d.addErrback(self._ebDeferredSelfInfoError)
        self.sendSNAC(0x01, 0x0E, '').addCallback(self._cbRequestSelfInfo, d)
        return d

    def _ebDeferredSelfInfoError(self, error):
        log.msg('ERROR IN SELFINFO DEFERRED %s' % error)

    def _cbRequestSelfInfo(self, snac, d):
        self.receivedSelfInfo(self.parseUser(snac[5]))
        #d.callback(self.parseUser(snac[5]))

    def oscar_15_03(self, snac):
        """
        Meta information (Offline messages, extended info about users)
        """
        tlvs = readTLVs(snac[5])
        for k, v in tlvs.items():
            if (k == 1):
                targetuin,type = struct.unpack('<IH',v[2:8])
                if (type == 0x41):
                    log.msg("Received Offline Message: %r" % (v))
                    # Offline message
                    senderuin = struct.unpack('<I',v[10:14])[0]
                    #print "senderuin: "+str(senderuin)+"\n"
                    msg_date = str( "%4d-%02d-%02dT%02d:%02d:00Z" #XEP-091 date format
                                 % struct.unpack('<HBBBB', v[14:20]) )
                    messagetype, messageflags,messagelen = struct.unpack('<BBH',v[20:24])
                    umessage, encoding = guess_encoding(v[24:24+messagelen-1],self.defaultEncoding)
                    log.msg("Converted message, encoding %r: %r" % (encoding, umessage))
                    #umessage = umessage + "\n\n/sent " + msg_date
                    message = [ umessage.encode("utf-16be"), "unicode" ]
                    #message = [ str( v[24:24+messagelen-1] )
                    #            + "\n\n/sent " + msg_date ]

                    if (messagelen > 0):
                        flags = []
                        multiparts = []
                        tlvs = dict()
                        multiparts.append(tuple(message))
                        user = OSCARUser(str(senderuin), None, tlvs)
                        self.receiveMessage(user, multiparts, flags, msg_date)
                elif (type == 0x42):
                    # End of offline messages
                    reqdata = '\x08\x00'+struct.pack("<I",int(self.username))+'\x3e\x00\x02\x00'
                    tlvs = TLV(0x01, reqdata)
                    self.sendSNAC(0x15, 0x02, tlvs)
                elif (type == 0x7da):
                    # Meta information
                    # print [ "%x" % ord(n) for n in v ]
                    sequenceNumber,rType,success = struct.unpack("<HHB",v[8:13])
                    if success == 0x0a:
                        if rType == 0xc8:
                            # SNAC(15,03)/07DA/00C8 | META_BASIC_USERINFO
                            # http://iserverd1.khstu.ru/oscar/snac_15_03_07da_00c8.html
                            nick,first,last,email,homeCity,homeState,homePhone,homeFax,homeAddress,cellPhone,homeZip,homeCountry = self.parseFullInfo(v[13:])
                            self.gotUserInfo(sequenceNumber, rType, [nick,first,last,email,homeCity,homeState,homePhone,homeFax,homeAddress,cellPhone,homeZip,homeCountry])
                        elif rType == 0xdc:
                            # SNAC(15,03)/07DA/00DC | META_MORE_USERINFO
                            # http://iserverd1.khstu.ru/oscar/snac_15_03_07da_00dc.html
                            homepage,birth = self.parseMoreInfo(v[13:])
                            self.gotUserInfo(sequenceNumber, rType, [homepage,birth])
                        elif rType == 0xeb or rType == 0x10e or rType == 0xf0 or rType == 0xfa:
                            # for now we don't care about these
                            self.gotUserInfo(sequenceNumber, rType, None)
                        elif rType == 0xd2:
                            # SNAC(15,03)/07DA/00D2 | META_WORK_USERINFO
                            # http://iserverd1.khstu.ru/oscar/snac_15_03_07da_00d2.html
                            city,state,phone,fax,address,zip,country,company,department,position = self.parseWorkInfo(v[13:])
                            self.gotUserInfo(sequenceNumber, rType, [city,state,phone,fax,address,zip,country,company,department,position])
                        elif rType == 0xe6:
                            # SNAC(15,03)/07DA/00E6 | META_NOTES_USERINFO
                            # http://iserverd1.khstu.ru/oscar/snac_15_03_07da_00e6.html
                            usernotes = self.parseNotesInfo(v[13:])
                            self.gotUserInfo(sequenceNumber, rType, [usernotes])
                    else:
                        self.gotUserInfo(sequenceNumber, 0xffff, None)
                else:
                    # can there be anything else
                    pass
            elif (k == 2):
                pass
            elif (k == 3):
                pass
            #else:
            #    print str(k)+":::"+str(v)+"\n"

    def initSSI(self):
        """
        this sends the rate request for family 0x13 (Server Side Information)
        so we can then use it
        """
        return self.sendSNAC(0x13, 0x02, '').addCallback(self._cbInitSSI)

    def _cbInitSSI(self, snac, d):
        return {} # don't even bother parsing this

    def requestSSI(self, timestamp = 0, revision = 0):
        """
        request the server side information
        if the deferred gets None, it means the SSI is the same
        """
        return self.sendSNAC(0x13, 0x05,
            struct.pack('!LH',timestamp,revision)).addCallback(self._cbRequestSSI)

    def _cbRequestSSI(self, snac, args = ()):
        if snac[1] == 0x0f: # same SSI as we have
            return
        itemdata = snac[5][3:]
        if args:
            revision, groups, permit, deny, permitMode, visibility, iconcksum, permitDenyInfo = args
        else:
            version, revision = struct.unpack('!BH', snac[5][:3])
            groups = {}
            permit = []
            deny = []
            permitMode = None
            visibility = None
            iconcksum = []
            permitDenyInfo = None
	least_groupID = self.ssistats['least_groupID']
        while len(itemdata)>4:
            nameLength = struct.unpack('!H', itemdata[:2])[0]
            name = itemdata[2:2+nameLength]
            groupID, buddyID, itemType, restLength = \
                struct.unpack('!4H', itemdata[2+nameLength:10+nameLength])
	    if least_groupID == -1:
		least_groupID = groupID
		self.ssistats['least_groupID'] = least_groupID
            tlvs = readTLVs(itemdata[10+nameLength:10+nameLength+restLength])
            itemdata = itemdata[10+nameLength+restLength:]
            if itemType == AIM_SSI_TYPE_BUDDY: # buddies
                groups[groupID].addUser(buddyID, SSIBuddy(name, groupID, buddyID, tlvs))
		self.ssistats['buddies'] += 1
            elif itemType == AIM_SSI_TYPE_GROUP: # group
                g = SSIGroup(name, groupID, buddyID, tlvs)
                if least_groupID in groups: 
			groups[least_groupID].addUser(groupID, g)
                groups[groupID] = g
		self.ssistats['groups'] += 1
            elif itemType == AIM_SSI_TYPE_PERMIT: # permit
                permit.append(name)
            elif itemType == AIM_SSI_TYPE_DENY: # deny
                deny.append(name)
            elif itemType == AIM_SSI_TYPE_PDINFO: # permit deny info
                permitDenyInfo = SSIPDInfo(name, groupID, buddyID, tlvs)
                if tlvs.has_key(0xca):
                    permitMode = {AIM_SSI_PERMDENY_PERMIT_ALL:'permitall',AIM_SSI_PERMDENY_DENY_ALL:'denyall',AIM_SSI_PERMDENY_PERMIT_SOME:'permitsome',AIM_SSI_PERMDENY_DENY_SOME:'denysome',AIM_SSI_PERMDENY_PERMIT_BUDDIES:'permitbuddies'}.get(ord(tlvs[0xca]),None)
                if tlvs.has_key(0xcb):
                    visibility = {AIM_SSI_VISIBILITY_ALL:'all',AIM_SSI_VISIBILITY_NOTAIM:'notaim'}.get(tlvs[0xcb],None)
            elif itemType == AIM_SSI_TYPE_PRESENCEPREFS: # presence preferences
                pass
            elif itemType == AIM_SSI_TYPE_ICQSHORTCUT: # ICQ2K shortcuts bar?
                pass
            elif itemType == AIM_SSI_TYPE_IGNORE: # Ignore list record
                pass
            elif itemType == AIM_SSI_TYPE_LASTUPDATE: # Last update time
                pass
            elif itemType == AIM_SSI_TYPE_SMS: # SMS contact. Like 1#EXT, 2#EXT, etc
                pass
            elif itemType == AIM_SSI_TYPE_IMPORTTIME: # Roster import time
                pass
            elif itemType == AIM_SSI_TYPE_ICONINFO: # icon information
                # I'm not sure why there are multiple of these sometimes
                # We're going to return all of them though...
                iconcksum.append(SSIIconSum(name, groupID, buddyID, tlvs))
            elif itemType == AIM_SSI_TYPE_LOCALBUDDYNAME: # locally stored buddy name
                pass
	    elif itemType == AIM_SSI_TYPE_PHANTOMBUDDY:
		if self.settingsOptionEnabled('clist_show_phantombuddies'):
			if groupID in groups:
				groups[groupID].addUser(buddyID, SSIBuddy(name, groupID, buddyID, tlvs))
		else:
			log.msg('SSI phantombuddy : %s %s %s %s %s' % (name, groupID, buddyID, itemType, tlvs)) 
		self.ssistats['phantombuddies'] += 1
	    elif itemType == AIM_SSI_TYPE_UNKNOWN0:
		log.msg('SSI entry with type unknown0: %s %s %s %s %s' % (name, groupID, buddyID, itemType, tlvs)) 
            else:
                log.msg('unknown SSI entry: %s %s %s %s %s' % (name, groupID, buddyID, itemType, tlvs))
	self.ssistats['ssipackets'] += 1
        timestamp = struct.unpack('!L',itemdata)[0]
        if not timestamp: # we've got more packets coming
            # which means add some deferred stuff
            d = defer.Deferred()
            self.requestCallbacks[snac[4]] = d
            d.addCallback(self._cbRequestSSI, (revision, groups, permit, deny, permitMode, visibility, iconcksum, permitDenyInfo))
            d.addErrback(self._ebDeferredRequestSSIError, revision, groups, permit, deny, permitMode, visibility, iconcksum, permitDenyInfo)
            return d
        if (len(groups) <= 0):
            gusers = None
        else:
	    if least_groupID in groups:
        	gusers = groups[least_groupID].users
	    else:
		log.msg('Contact-list have interesting format')
	log.msg('Contact-list imported from server. Found %s groups, %s contacts and %s temporary contacts' % (self.ssistats['groups'], self.ssistats['buddies'], self.ssistats['phantombuddies'])) # write in stats
	log.msg('Root groupID: %s. Import took %s packets' % (self.ssistats['least_groupID'], self.ssistats['ssipackets']))
        return (gusers,permit,deny,permitMode,visibility,iconcksum,timestamp,revision,permitDenyInfo)

    def _ebDeferredRequestSSIError(self, error, revision, groups, permit, deny, permitMode, visibility, iconcksum, permitDenyInfo):
        log.msg('ERROR IN REQUEST SSI DEFERRED %s' % error)

    def activateSSI(self):
        """
        activate the data stored on the server (use buddy list, permit deny settings, etc.)
        """
        self.sendSNACnr(0x13,0x07,'')

    def startModifySSI(self):
        """
        tell the OSCAR server to be on the lookout for SSI modifications
        """
        self.sendSNACnr(0x13,0x11,'')

    def addItemSSI(self, item):
        """
        add an item to the SSI server.  if buddyID == 0, then this should be a group.
        this gets a callback when it's finished, but you can probably ignore it.
        """
        d = self.sendSNAC(0x13,0x08, item.oscarRep())
        log.msg("addItemSSI: adding %s, g:%d, u:%d"%(item.name, item.groupID, item.buddyID))
        d.addCallback(self._cbAddItemSSI, item)
        return d

    def _cbAddItemSSI(self, snac, item):
        pos = 0
        #if snac[2] & 0x80 or snac[3] & 0x80:
        #    sLen,id,length = struct.unpack(">HHH", snac[5][:6])
        #    pos = 6 + length
        if snac[5][pos:pos+2] == "\00\00":
                #success
                #data = struct.pack(">H", len(groupName))+groupName
                #data += struct.pack(">HH", 0, 1)
                #tlvData = TLV(0xc8, struct.pack(">H", buddyID))
                #data += struct.pack(">H", len(tlvData))+tlvData
                #self.sendSNACnr(0x13,0x09, data)
            if item.buddyID != 0: # is it a buddy or a group?
                self.buddyAdded(item.name)
        elif snac[5][pos:pos+2] == "\00\x0a":
            # invalid, error while adding
            pass
        elif snac[5][pos:pos+2] == "\00\x0c":
            # limit exceeded
            self.errorMessage("Contact list limit exceeded")
        elif snac[5][pos:pos+2] == "\00\x0d":
            # Trying to add ICQ contact to an AIM list
            self.errorMessage("Trying to add ICQ contact to an AIM list")
        elif snac[5][pos:pos+2] == "\00\x0e":
            # requires authorization
            log.msg("Authorization needed... requesting")
            self.sendAuthorizationRequest(item.name, "Please authorize me")
            item.authorizationRequestSent = True
            item.authorized = False
            self.addItemSSI(item)

    def modifyItemSSI(self, item, groupID = None, buddyID = None):
        if groupID is None:
	    least_groupID = self.ssistats['least_groupID']
	    if not least_groupID:
		least_groupID = 0
            if isinstance(item, SSIIconSum):
                groupID = least_groupID
            elif isinstance(item, SSIPDInfo):
                groupID = least_groupID
            elif isinstance(item, SSIGroup):
                groupID = least_groupID
	    else:
		groupID = item.group.group.findIDFor(item.group)
        if buddyID is None:
            if isinstance(item, SSIIconSum):
                buddyID = 0x5dd6
            elif isinstance(item, SSIPDInfo):
                buddyID = 0xffff
            elif hasattr(item, "group"):
                buddyID = item.group.findIDFor(item)
            else:
                buddyID = 0
        return self.sendSNAC(0x13,0x09, item.oscarRep())

    def delItemSSI(self, item):
        return self.sendSNAC(0x13,0x0A, item.oscarRep())

    def endModifySSI(self):
        self.sendSNACnr(0x13,0x12,'')

    def setProfile(self, profile=None):
        """
        set the profile.
        send None to not set a profile (different from '' for a blank one)
        """
        self.profile = profile
        tlvs = ''
        if self.profile is not None:
            tlvs =  TLV(1,'text/aolrtf; charset="us-ascii"') + \
                    TLV(2,self.profile)

        tlvs = tlvs + TLV(5, ''.join(self.capabilities))
        self.sendSNACnr(0x02, 0x04, tlvs)

    def setAway(self, away = None):
        """
        set the away message, or return (if away == None)
        """
        self.awayMessage = away
        tlvs = TLV(3,'text/aolrtf; charset="us-ascii"') + \
               TLV(4,away or '')
        self.sendSNACnr(0x02, 0x04, tlvs)

    def setBack(self, status=None):
        """
        set the extended status message
	deprecated. Use setExtendedStatusRequest instead
        """
        # If our away message is set, clear it.
        #if self.awayMessage:
        #    self.setAway()
        
        if not status:
            status = ""
        else:
            status = status[:220]
               
        log.msg("Setting extended status message to \"%s\""%status)
        self.backMessage = status
        packet = struct.pack(
               "!HHHbbH",
               0x001d,         # H
               len(status)+8,  # H
               0x0002,         # H
               0x04,           # b
               len(status)+4,  # b
               len(status)     # H
        ) + str(status) + struct.pack("H",0x0000)
        
        self.sendSNACnr(0x01, 0x1e, packet)

    def setURL(self, status=None):
        """
        set the extended status URL
        """
               
        if not status:
            status = ""
        else:
            status = status[:220]
        log.msg("Setting extended status URL to \"%s\""%status)
        self.backMessage = status
        packet = struct.pack(
               "!HHHbbH",
               0x001d,         # H
               len(status)+8,  # H
               0x0006,         # H
               0x04,           # b
               len(status)+4,  # b
               len(status)     # H
        ) + str(status) + struct.pack("H",0x0000)
        
        self.sendSNACnr(0x01, 0x1e, packet)

    def sendAuthorizationRequest(self, uin, authString):
        """
        send an authorization request
        """
        packet = struct.pack("b", len(uin))
        packet += uin
        packet += struct.pack(">H", len(authString))
        packet += authString
        packet += struct.pack("H", 0x00)
        log.msg("sending authorization request to %s"%uin)
        self.sendSNACnr(0x13, 0x18, packet)

    def sendAuthorizationResponse(self, uin, success, responsString):
        """
        send an authorization response
        """
        packet  = struct.pack("b", len(uin)) + uin
        if success:
            packet += struct.pack("b", 1)
        else:
            packet += struct.pack("b", 0)
        packet += struct.pack(">H", len(responsString)) + responsString
        self.sendSNACnr(0x13, 0x1a, packet)

    def setICQStatus(self, status):
        """
        set status of user: online, away, xa, dnd or chat
        """
        if status == "away":
            icqStatus = 0x01
        elif status == "dnd":
            icqStatus = 0x02
        elif status == "xa":
            icqStatus = 0x04
        elif status == "chat":
            icqStatus = 0x20
        else:
            icqStatus = 0x00
	self.icqStatus = icqStatus
	status = struct.pack('>HH', self.statusindicators, self.icqStatus)
	onlinestatusTLV = TLV(0x0006, status) # status
        self.sendSNACnr(0x01, 0x1e, onlinestatusTLV)

    def setIdleTime(self, idleTime):
        """
        set our idle time.  don't call more than once with a non-0 idle time.
        """
        self.sendSNACnr(0x01, 0x11, struct.pack('!L',idleTime))

    def sendMessage(self, user, message, wantAck = 0, autoResponse = 0, offline = 0, wantIcon = 0, iconSum = None, iconLen = None, iconStamp = None ):
        """
        send a message to user (not an OSCARUseR).
        message can be a string, or a multipart tuple.
        if wantAck, we return a Deferred that gets a callback when the message is sent.
        if autoResponse, this message is an autoResponse, as if from an away message.
        if offline, this is an offline message (ICQ only, I think)
        if iconLen, iconSum, and iconStamp, we have a buddy icon and want user to know
        if wantIcon, we want their buddy icon, tell us if you have it
        """
        cookie = ''.join([chr(random.randrange(0, 127)) for i in range(8)]) # cookie
        data = cookie + struct.pack("!HB", 0x0001, len(user)) + user
        if not type(message) in (types.TupleType, types.ListType):
            message = [[message,]]
            if type(message[0][0]) == types.UnicodeType:
                message[0].append('unicode')
        messageData = ''
        for part in message:
            charSet = 0x0000
            if 'none' in part[1:]:
                charSet = 0xffff
            else:
                try:
                    part[0] = part[0].encode('ascii')
                    charSet = 0x0000
                except:
                    try:
                        part[0] = part[0].encode(config.encoding)
                        charSet = 0x0003
                    except:
                        try:
                            part[0] = part[0].encode('utf-16be', 'replace')
                            charSet = 0x0002
                        except:
                            part[0] = part[0].encode('iso-8859-1', 'replace')
                            charSet = 0x0003
            if 'macintosh' in part[1:]:
                charSubSet = 0x000b
            elif 'none' in part[1:]:
                charSubSet = 0xffff
            else:
                charSubSet = 0x0000
            messageData = messageData + struct.pack('!HHHH',0x0101,len(part[0])+4,charSet,charSubSet) + part[0]

        # We'll investigate this in more detail later.
        features = '\x01\x01\x02'
        # Why do i need to encode this?  I shouldn't .. it's data.
        data = data.encode('iso-8859-1', 'replace') + TLV(2, TLV(0x0501, features)+messageData)
        if wantAck:
            log.msg("sendMessage: Sending wanting ACK")
            data = data + TLV(3)
        if autoResponse:
            log.msg("sendMessage: Sending as an auto-response")
            data = data + TLV(4)
        if offline:
            log.msg("sendMessage: Sending offline")
            data = data + TLV(6)
        if iconSum and iconLen and iconStamp:
            log.msg("sendMessage: Sending info about our icon")
            data = data + TLV(8,struct.pack('!IHHI', iconLen, 0x0001, iconSum, iconStamp))
        if wantIcon:
            log.msg("sendMessage: Sending request for their icon")
            data = data + TLV(9)
        if wantAck:
            return self.sendSNAC(0x04, 0x06, data).addCallback(self._cbSendMessageAck, user, message)
        self.sendSNACnr(0x04, 0x06, data)

    def _cbSendMessageAck(self, snac, user, message):
        return user, message
 
    def sendXstatusMessageRequest(self, user):
	"""
	send request for x-status message to user
        """
	if user in self.oscarcon.legacyList.usercaps:
		if 'icqxtraz' in self.oscarcon.legacyList.usercaps[user]: # xtraz supported by client
			if user in self.oscarcon.legacyList.usercustomstatuses and 'x-status' in self.oscarcon.legacyList.usercustomstatuses[user]: # and x-status was set
				log.msg("Sending x-status details request to %s" % user)
				# AIM messaging header
				cookie = ''.join([chr(random.randrange(0, 127)) for i in range(8)]) # ICBM cookie
				header = cookie + struct.pack("!HB", 0x0002, len(user)) + user # channel 2, user UIN
				# xtraz request
				notifyBody='<srv><id>cAwaySrv</id><req><id>AwayStat</id><trans>1</trans><senderId>%s</senderId></req></srv>'  % self.name
				queryBody = '<Q><PluginID>srvMng</PluginID></Q>'
				query = '<N><QUERY>%s</QUERY><NOTIFY>%s</NOTIFY></N>' % (utils.getSafeXML(queryBody), utils.getSafeXML(notifyBody))
				# request TLV
				extdataTLV = TLV(0x2711, self.prepareExtendedDataBody(query)) # make TLV with extended data
				# Render Vous Data body
				rvdataTLV = struct.pack('!H',0x0000) # request
				rvdataTLV = rvdataTLV + cookie # ICBM cookie
				rvdataTLV = rvdataTLV + CAP_SERV_REL # ICQ Server Relaying
				# additional TLVs
				addTLV1 = TLV(0x0a, struct.pack('!H',1)) # Acktype: 1 - normal, 2 - ack
				addTLV2 = TLV(0x0f) # empty TLV
				# concat TLVs
				rvdataTLV = rvdataTLV + addTLV1 + addTLV2 + extdataTLV
				# make Render Vous Data TLV
				rvdataTLV = TLV(0x0005, rvdataTLV)
				# server Ack requested
				TLVask = TLV(3)
				# result data
				data = header + rvdataTLV + TLVask
				
				self.sendSNAC(0x04, 0x06, data).addCallback(self._sendXstatusMessageRequest) # send request
					
    def sendXstatusMessageResponse(self, user, cookie):
	"""
	send x-status message response to user
        """
	log.msg("Sending x-status details response to %s" % user)
	# AIM messaging header
	header = cookie + struct.pack("!HB", 0x0002, len(user)) + user # cookie from request, channel 2, user UIN
	header = header + struct.pack('!H',0x3) # reason: channel-specific

	index = self.getSelfXstatusIndex()
	title, desc = self.getSelfXstatusDetails()

	# message content
	content = """\
<ret event='OnRemoteNotification'>\
<srv><id>cAwaySrv</id>\
<val srv_id='cAwaySrv'><Root>\
<CASXtraSetAwayMessage></CASXtraSetAwayMessage>\
<uin>%s</uin>\
<index>%s</index>\
<title>%s</title>\
<desc>%s</desc></Root></val></srv></ret>""" % (str(self.username), str(index), str(title), str(desc))
	query = '<NR><RES>%s</RES></NR>' % utils.getSafeXML(content)
	data = header + self.prepareExtendedDataBody(query) # data for response formed

	self.sendSNACnr(0x04, 0x0b, data) # send as Client Auto Response
	
    def sendStatusMessageRequest(self, user):
	"""
	send request for status message to user
        """
	if user in self.oscarcon.legacyList.usercaps:
		log.msg("Sending status details request to %s" % user)
		# AIM messaging header
		cookie = ''.join([chr(random.randrange(0, 127)) for i in range(8)]) # ICBM cookie
		header = cookie + struct.pack("!HB", 0x0002, len(user)) + user # channel 2, user UIN
		# request TLV
		extdataTLV = TLV(0x2711, self.prepareClientAutoResponseBody('\0')) # make TLV with empty body
		# Render Vous Data body
		rvdataTLV = struct.pack('!H',0x0000) # request
		rvdataTLV = rvdataTLV + cookie # ICBM cookie
		rvdataTLV = rvdataTLV + CAP_SERV_REL # ICQ Server Relaying
		# additional TLVs
		addTLV1 = TLV(0x0a, struct.pack('!H',1)) # Acktype: 1 - normal, 2 - ack
		addTLV2 = TLV(0x0f) # empty TLV
		# concat TLVs
		rvdataTLV = rvdataTLV + addTLV1 + addTLV2 + extdataTLV
		# make Render Vous Data TLV
		rvdataTLV = TLV(0x0005, rvdataTLV)
		# server Ack requested
		TLVask = TLV(3)
		# result data
		data = header + rvdataTLV + TLVask
				
		self.sendSNAC(0x04, 0x06, data).addCallback(self._sendStatusMessageRequest) # send request
		
    def _sendStatusMessageRequest(self, snac):
	"""
	callback for sending of status request
        """
	log.msg("Request for status details sent")

    def sendStatusMessageResponse(self, user, cookie):
	"""
	send status message response to user
        """
	log.msg("Sending status details response to %s" % user)
	# AIM messaging header
	header = cookie + struct.pack("!HB", 0x0002, len(user)) + user # cookie from request, channel 2, user UIN
	header = header + struct.pack('!H',0x3) # reason: channel-specific
	data = header + self.prepareClientAutoResponseBody(utils.utf8encode(self.oscarcon.savedFriendly))
	self.sendSNACnr(0x04, 0x0b, data) # send as Client Auto Response

    def packPluginTypeId(self):
    	"""
	pack typeid for plugin
        """
	dt =  struct.pack('<H',0x4f) # length
	dt += struct.pack('!LLLL', MSGTYPE_ID_XTRAZ_SCRIPT[0], MSGTYPE_ID_XTRAZ_SCRIPT[1], MSGTYPE_ID_XTRAZ_SCRIPT[2], MSGTYPE_ID_XTRAZ_SCRIPT[3]) # Message type id: xtraz script
	dt += struct.pack('<H',0x0008) # message subtype: Script Notify
	dt += struct.pack('<L',0x002a) # request type string
	dt += 'Script Plug-in: Remote Notification Arrive'
	dt += struct.pack('!LLLHB',0x00000100, 0x00000000, 0x00000000, 0x0000, 0x00) # unknown
	return dt

    def prepareClientAutoResponseBody(self, query):
	"""
	auto-away message
        """
	if query == None:
		query = ''
	# extended data body
	extended_data = struct.pack('<H',0x1b) # unknown (header #1 len?)
	extended_data = extended_data + struct.pack('!B',0x08) # protocol version
	extended_data = extended_data + CAP_EMPTY # Plugin Version
	extended_data = extended_data + struct.pack("!L", 0x3) # client features
	extended_data = extended_data + struct.pack('!L', 0x0004) # DC type: normal direct connection (without proxy/firewall)
	msgcookie = ''.join([chr(random.randrange(0, 127)) for i in range(2)]) # it non-clear way
	extended_data = extended_data + msgcookie # message cookie
	extended_data = extended_data + struct.pack('<H',0x0e) # unknown (header #2 len?)
	extended_data = extended_data + msgcookie # message cookie again
	extended_data = extended_data + struct.pack('!LLL', 0, 0, 0) # unknown
	extended_data = extended_data + struct.pack('!B', 0xe8) # msg type: auto-away message
	extended_data = extended_data + struct.pack('!B', 0x03) # msg flags: auto message
	extended_data = extended_data + struct.pack('<H', self.session.legacycon.bos.icqStatus) # status
	extended_data = extended_data + struct.pack('!H',0x0100) # priority
	extended_data = extended_data + struct.pack('<H',len(query)) + query # message
	return extended_data

    def prepareExtendedDataBody(self, query):
	"""
	prepare it
        """
	# extended data body
	extended_data = struct.pack('<H',0x1b) # unknown (header #1 len?)
	extended_data = extended_data + struct.pack('!B',0x08) # protocol version
	extended_data = extended_data + CAP_EMPTY # Plugin Version
	extended_data = extended_data + struct.pack("!L", 0x3) # client features
	extended_data = extended_data + struct.pack('!L', 0x0004) # DC type: normal direct connection (without proxy/firewall)
	msgcookie = ''.join([chr(random.randrange(0, 127)) for i in range(2)]) # it non-clear way
	extended_data = extended_data + msgcookie # message cookie
	extended_data = extended_data + struct.pack('<H',0x0e) # unknown (header #2 len?)
	extended_data = extended_data + msgcookie # message cookie again
	extended_data = extended_data + struct.pack('!LLL', 0, 0, 0) # unknown
	extended_data = extended_data + struct.pack('!B', 0x1a) # msg type: Plugin message described by text string
	extended_data = extended_data + struct.pack('!B', 0x00) # msg flags
	extended_data = extended_data + struct.pack('<H', self.session.legacycon.bos.icqStatus) # status
	extended_data = extended_data + struct.pack('!H',0x0100) # priority
	extended_data = extended_data + struct.pack('!HB',0x0100,0x00) # empty message
	extended_data = extended_data + self.packPluginTypeId()
	extended_data = extended_data + struct.pack('<LL', len(query)+4, len(query))
	extended_data = extended_data + query
	return extended_data

    def _sendXstatusMessageRequest(self, snac):
	"""
	callback for sending of x-status request
        """
	log.msg("Request for x-status details sent")
	
    def sendMessageType2(self, user, message):
	"""
	send UTF-8 message via serv_relay
	"""
	log.msg("Sending type-2 message to %s" % user) 
	# AIM messaging header
	cookie = ''.join([chr(random.randrange(0, 127)) for i in range(8)]) # ICBM cookie
	header = cookie + struct.pack("!HB", 0x0002, len(user)) + user # channel 2, user UIN
	header = str(header)
	extended_data = str(self.prepareMessageType2Body(message))
	
	foreground_color = 0x000000
	background_color = 0xffffff
	cap_len = len(MSGTYPE_TEXT_ID_UTF8MSGS)
	more = struct.pack("<LLL", foreground_color, background_color, cap_len)
	more = more + MSGTYPE_TEXT_ID_UTF8MSGS # UTF-8 cap
	
	extended_data = extended_data + more 
	# TLV
	extdataTLV = TLV(0x2711, extended_data)
	# Render Vous Data body
	rvdataTLV = struct.pack('!H',0x0000) # request
	rvdataTLV = rvdataTLV + cookie # ICBM cookie
	rvdataTLV = rvdataTLV + CAP_SERV_REL # ICQ Server Relaying
	# additional TLVs
	addTLV1 = TLV(0x0a, struct.pack('!H',1)) # Acktype: 1 - normal, 2 - ack
	addTLV2 = TLV(0x0f) # empty TLV
	# concat TLVs
	rvdataTLV = rvdataTLV + addTLV1 + addTLV2 + extdataTLV
	# make Render Vous Data TLV
	rvdataTLV = TLV(0x0005, rvdataTLV)
	# server Ack requested
	TLVask = TLV(3)
	# result data
	data = header + rvdataTLV + TLVask
	
	self.sendSNAC(0x04, 0x06, data).addCallback(self._sendMessageType2) # send message
	
    def sendMessageType2Confirmation(self, user, cookie=None):
	"""
	send confirmation for UTF-8 message
	"""
	log.msg("Sending confirmation for type-2 message to %s" % user) 
	# AIM messaging header
	if not cookie:
		cookie = ''.join([chr(random.randrange(0, 127)) for i in range(8)]) # ICBM cookie
	header = cookie + struct.pack("!HB", 0x0002, len(user)) + user # channel 2, user UIN
	header = str(header)
	extended_data = str(self.prepareMessageType2Body(None))
	# TLV
	extdataTLV = TLV(0x2711, extended_data)
	# Render Vous Data body
	rvdataTLV = struct.pack('!H',0x0000) # request
	rvdataTLV = rvdataTLV + cookie # ICBM cookie
	rvdataTLV = rvdataTLV + CAP_SERV_REL # ICQ Server Relaying
	# additional TLVs
	addTLV1 = TLV(0x0a, struct.pack('!H',1)) # Acktype: 1 - normal, 2 - ack
	addTLV2 = TLV(0x0f) # empty TLV
	# concat TLVs
	rvdataTLV = rvdataTLV + addTLV1 + addTLV2 + extdataTLV
	# make Render Vous Data TLV
	rvdataTLV = TLV(0x0005, rvdataTLV)
	# server Ack requested
	TLVask = TLV(3)
	# result data
	data = header + rvdataTLV + TLVask
	
	self.sendSNAC(0x04, 0x06, data).addCallback(self._sendMessageType2Confirmation) # send message
	
    def _sendMessageType2(self, snac):
	"""
	callback for sending of type-2 message
        """
	log.msg("Type-2 message sent")
	
    def _sendMessageType2Confirmation(self, snac):
	"""
	callback for sending of type-2 message confirmation
        """
	log.msg("Confirmation for type-2 message sent")
	
    def prepareMessageType2Body(self, query):
	"""
	plain text message
	"""
	if query == None:
		query = ''
	query = query.encode('utf-8') + '\x00'
	# extended data body
	extended_data = struct.pack('<H',0x1b) # unknown (header #1 len?)
	extended_data = extended_data + struct.pack('!B',0x08) # protocol version
	extended_data = extended_data + CAP_EMPTY # Plugin Version
	extended_data = extended_data + struct.pack("!L", 0x3) # client features
	extended_data = extended_data + struct.pack('!L', 0x0004) # DC type: normal direct connection (without proxy/firewall)
	msgcookie = ''.join([chr(random.randrange(0, 127)) for i in range(2)]) # it non-clear way
	extended_data = extended_data + msgcookie # message cookie
	extended_data = extended_data + struct.pack('<H',0x0e) # unknown (header #2 len?)
	extended_data = extended_data + msgcookie # message cookie again
	extended_data = extended_data + struct.pack('!LLL', 0, 0, 0) # unknown
	extended_data = extended_data + struct.pack('!B', 0x01) # msg type: plain text message
	extended_data = extended_data + struct.pack('!B', 0x00) # msg flags: none
	extended_data = extended_data + struct.pack('<H', self.session.legacycon.bos.icqStatus) # status
	extended_data = extended_data + struct.pack('!H',0x0100) # priority
	extended_data = extended_data + struct.pack('<H',len(query)) + query # message
	return extended_data
	
    def getSelfXstatusName(self):
	"""
	return name of x-status
        """
	if 'x-status name' in self.selfCustomStatus:
		return self.selfCustomStatus['x-status name']
	else:
		return ''

    def getSelfXstatusDetails(self):
	"""
	return title and desc of x-status
        """
	title = ''
	desc = ''
	if 'x-status title' in self.selfCustomStatus:
		title = self.selfCustomStatus['x-status title']
	if 'x-status desc' in self.selfCustomStatus:
		desc = self.selfCustomStatus['x-status desc']
	return title, desc
	
    def getSelfXstatusNumber(self):
	"""
	return number of x-status
        """
	if 'x-status number' in self.selfCustomStatus:
		return self.selfCustomStatus['x-status number']
	else:
		return -1
	
    def getSelfXstatusIndex(self):
	"""
	return index of x-status (ICQ5.1-like)
        """
	index = self.getSelfXstatusNumber() + 1
	if index > 1 and index < 32:
		return index
	else:
		return 0
	
    def getSelfXstatusMoodIndex(self):
	"""
	return index of x-status mood (ICQ6-like)
        """
	xstatus_key = ''
	mood_num = -1
	for key in X_STATUS_CAPS:
		if key in self.capabilities:
			xstatus_key = key
	if xstatus_key !='':
		if xstatus_key in X_STATUS_CAPS:
			xstatus_num = X_STATUS_CAPS[xstatus_key]
			if xstatus_num in X_STATUS_MOODS:
				mood_num = X_STATUS_MOODS[xstatus_num]
	return mood_num
	
    def getXstatusNumberByName(self, xstatus_name):
	"""
	return index of x-status (ICQ5.1-like)
        """
	if xstatus_name in X_STATUS_NAME:
		return X_STATUS_NAME.index(xstatus_name)
	else:
		return -1
	
    def removeSelfXstatusNoUpdate(self):
	"""
	remove x-status line from caps
        """
	for key in X_STATUS_CAPS:
		if key in self.capabilities:
			self.capabilities.remove(key)

    def removeSelfXstatus(self):
	"""
	notify server about changes in caps
        """
	if int(self.settingsOptionValue('xstatus_sending_mode')) in (1,3):
		self.removeSelfXstatusNoUpdate()
		self.setUserInfo()
	if int(self.settingsOptionValue('xstatus_sending_mode')) in (2,3):
		self.setExtendedStatusRequest(message='', setmsg=True)
	
    def updateSelfXstatus(self):
	"""
	update x-status
        """
	if 'x-status name' in self.selfCustomStatus: # self x-status exists
		if 'avail.message' in self.selfCustomStatus:
			availmsg = self.selfCustomStatus['avail.message']
		else:
			availmsg = None
		self.setSelfXstatusName(self.selfCustomStatus['x-status name'], availmsg)
	else: # no self x-status
		self.removeSelfXstatus() # tell to server about it
	log.msg('updateSelfXstatus: %s' % self.selfCustomStatus)
			
    def settingsOptionEnabled(self, option):
	"""
	check setting value
        """
	if option in self.selfSettings:
		if str(self.selfSettings[option]) == '1':
			return True
	return False
	
    def settingsOptionValue(self, option):
	"""
	return setting value
        """
	if option in self.selfSettings:
		return str(self.selfSettings[option])
	return str(0)
	
    def	setSelfXstatusName(self, xstatus_name, availmsg):
	"""
	set x-status name, notify server about change and update internal x-status number
        """
	if xstatus_name and xstatus_name != 'None':
		    if xstatus_name in X_STATUS_NAME:
			index_in_list = X_STATUS_NAME.index(xstatus_name)
			for key in X_STATUS_CAPS:
				if X_STATUS_CAPS[key] == index_in_list:
					mood_num = -1
					setmood = False
					for everymood in X_STATUS_MOODS:
						if X_STATUS_MOODS[everymood] == index_in_list:
							mood_num = everymood
							setmood = True
					self.selfCustomStatus['x-status number'] = index_in_list
					self.removeSelfXstatusNoUpdate()
					if int(self.settingsOptionValue('xstatus_sending_mode')) in (1,3):
	    					self.capabilities.append(key)
						self.setUserInfo()
					if int(self.settingsOptionValue('xstatus_sending_mode')) in (2,3):
						self.setExtendedStatusRequest(message=availmsg, mood=mood_num, setmood=setmood, setmsg=True)
	
    def setUserInfo(self):
        """
        send self info (capslist)
        """
	caps = ''
	for cap in self.capabilities:
		caps += cap
	TLVcaps = TLV(0x05, caps)
	data = TLVcaps
        self.sendSNAC(0x02, 0x04, data)

			 
    def setExtendedStatusRequest(self, message=None, mood=None, setmsg=False, setmood=False):
	"""
        send self status info in ICQ6 format (x-status mood + available message + online status)
        """
	moodinfo = ''
	msginfo = ''
	if setmood == True and mood:
		mood_num = int(mood)
		if mood_num > -1: # mood
			mood_str = 'icqmood' + str(mood_num)
			mood_prefix = struct.pack('!HH',0x0e,len(mood_str))
			moodinfo = mood_prefix + mood_str
	if setmsg == True and message != None: # message
		if len(message) > 240:
			message = message[:237] + '...'
		msginfo = struct.pack(
		"!HbbH",
		0x0002,         # H
		0x04,           # b
		len(message)+4,  # b
		len(message)     # H
		) + str(message) + struct.pack("H",0x0000)
	if len(moodinfo) > 0 or len (msginfo) > 0:
		msgmoodTLV = TLV(0x001d, msginfo + moodinfo) # available message TLV
	else:
		msgmoodTLV = ''
	status = struct.pack('>HH', self.statusindicators, self.icqStatus)
	onlinestatusTLV = TLV(0x0006, status) # status
	data = onlinestatusTLV + msgmoodTLV
	self.sendSNAC(0x01, 0x1e, data)

    def sendSMS(self, phone, message, senderName = "Auto"):
        """
        Sends an SMS message through the ICQ server.
        
        phone (str) - Internation phone number to send to, digits only
        message (str or unicode) - The message to send
        senderName (str or unicode) - The sender name
        """
        message = u"""<icq_sms_message>
                        <destination>%s</destination>
                        <text>%s</text>
                        <codepage>utf-8</codepage>
                        <senders_UIN>%s</senders_UIN>
                        <senders_name>%s</senders_name>
                        <delivery_receipt>Yes</delivery_receipt>
                        <time>%s</time>
                      </icq_sms_message>""" % (phone,
                                               message,
                                               self.username,
                                               senderName,
                                               time.strftime("%a, %d %b %Y %T %Z"))
 
        commandData = struct.pack('<H', 0x1482) # Subcommand code
        commandData += struct.pack('!HH16x', 0x1, 0x16) # Unknown fields
        commandData += TLV(0, message.encode('utf-8'))
        
        return self.sendOldICQCommand(0x7d0, commandData)

    def sendInvite(self, user, chatroom, wantAck = 0):
        """
        send a chat room invitation to a user (not an OSCARUser).
        if wantAck, we return a Deferred that gets a callback when the message is sent.
        """
        cookie = ''.join([chr(random.randrange(0, 127)) for i in range(8)]) # cookie
        intdata = '\x00\x00'+cookie+CAP_CHAT
        intdata = intdata + TLV(0x0a,'\x00\x01')
        intdata = intdata + TLV(0x0f)
        intdata = intdata + TLV(0x0d,'us-ascii')
        intdata = intdata + TLV(0x0c,'Please join me in this Chat.')
        intdata = intdata + TLV(0x2711,struct.pack('!HB',chatroom.exchange,len(chatroom.fullName))+chatroom.fullName+struct.pack('!H',chatroom.instance))
        data = cookie+'\x00\x02'+chr(len(user))+user+TLV(5,intdata)
        if wantAck:
            data = data + TLV(3)
            return self.sendSNAC(0x04, 0x06, data).addCallback(self._cbSendInviteAck, user, chatroom)
        self.sendSNACnr(0x04, 0x06, data)

    def _cbSendInviteAck(self, snac, user, chatroom):
        return user, chatroom

    def sendIconDirect(self, user, icon, timestamp = time.time(), wantAck = 0):
        """
        send a buddy icon directly to a user (not an OSCARUser).
        timestamp should be the timestamp on the icon, or will be "now"
        if wantAck, we return a Deferred that gets a callback when the message is sent.
        """
        cookie = ''.join([chr(random.randrange(0, 127)) for i in range(8)]) # cookie
        intdata = '\x00\x00'+cookie+CAP_ICON
        intdata = intdata + TLV(0x0a,'\x00\x01')
        intdata = intdata + TLV(0x0f)

        iconlen = len(icon)
        iconsum = getIconSum(icon)

        ICONIDENT = 'AVT1picture.id' # Do we need to come up with our own?
        intdata = intdata + TLV(0x2711,'\x00\x00'+struct.pack('!HII',iconsum,iconlen,timestamp)+icon+ICONIDENT)

        data = cookie+'\x00\x02'+chr(len(user))+user+TLV(5,intdata)
        if wantAck:
            data = data + TLV(3)
            return self.sendSNAC(0x04, 0x06, data).addCallback(self._cbSendIconNotify, user, icon)
        self.sendSNACnr(0x04, 0x06, data)

    def _cbSendIconNotify(self, snac, user, icon):
        log.msg("Received icon notification from %s" % (user))
        return user, icon

    def connectService(self, service, wantCallback = 0, extraData = ''):
        """
        connect to another service
        if wantCallback, we return a Deferred that gets called back when the service is online.
        if extraData, append that to our request.
        """
        if wantCallback:
            d = defer.Deferred()
            d.addErrback(self._ebDeferredConnectServiceError)
            self.sendSNAC(0x01,0x04,struct.pack('!H',service) + extraData).addCallback(self._cbConnectService, d)
            return d
        else:
            self.sendSNACnr(0x01,0x04,struct.pack('!H',service))

    def _ebDeferredConnectServiceError(self, error):
        log.msg('ERROR IN CONNECT SERVICE DEFERRED %s' % error)

    def _cbConnectService(self, snac, d):
        if snac:
            #d.arm()
            # CHECKME, something was happening here involving getting a snac packet
            # that didn't have [2:] in it...
            self.oscar_01_05(snac, d)
        else:
            self.connectionFailed()

    def createChat(self, shortName, exchange=4):
        """
        create a chat room
        """
        if self.services.has_key(SERVICE_CHATNAV):
            return self.services[SERVICE_CHATNAV].createChat(shortName,exchange)
        else:
            d = defer.Deferred()
            d.addErrback(self._ebDeferredCreateChatError)
            self.connectService(SERVICE_CHATNAV,1).addCallback(lambda s:s.createChat(shortName,exchange).chainDeferred(d))
            return d

    def _ebDeferredCreateChatError(self, error):
        log.msg('ERROR IN CREATE CHAT DEFERRED %s' % error)

    def joinChat(self, exchange, fullName, instance):
        """
        join a chat room
        """
        #d = defer.Deferred()
        return self.connectService(0x0e, 1, TLV(0x01, struct.pack('!HB',exchange, len(fullName)) + fullName +
                          struct.pack('!H', instance))).addCallback(self._cbJoinChat) #, d)
        #return d

    def _cbJoinChat(self, chat):
        del self.services[SERVICE_CHAT]
        return chat

    def warnUser(self, user, anon = 0):
        return self.sendSNAC(0x04, 0x08, '\x00'+chr(anon)+chr(len(user))+user).addCallback(self._cbWarnUser)

    def _cbWarnUser(self, snac):
        oldLevel, newLevel = struct.unpack('!2H', snac[5])
        return oldLevel, newLevel

    def getInfo(self, user):
        #if user.
        return self.sendSNAC(0x02, 0x05, '\x00\x01'+chr(len(user))+user).addCallback(self._cbGetInfo)

    def _cbGetInfo(self, snac):
        user, rest = self.parseUser(snac[5],1)
        tlvs = readTLVs(rest)
        return tlvs.get(0x02,None)

    def getProfile(self, user):
        #if user.
        return self.sendSNAC(0x02, 0x15, '\x00\x00\x00\x01'+chr(len(user))+user).addCallback(self._cbGetProfile).addErrback(self._cbGetProfileError)

    def _cbGetProfile(self, snac):
        try:
            user, rest = self.parseUser(snac[5],1)
            tlvs = readTLVs(rest)
        except (TypeError, struct.error):
            try:
                tlvs = self.parseProfile(snac[5])
            except (TypeError, struct.error):
                return [None, None]
        return tlvs.get(0x02,None)

    def _cbGetProfileError(self, result):
        return result

    def lookupEmail(self, email):
        #if email.
        return self.sendSNAC(0x0a, 0x02, email).addCallback(self._cbLookupEmail).addErrback(self._cbLookupEmailError)

    def _cbLookupEmail(self, snac):
        tlvs = readTLVs(snac[5])
        results = []
        data = snac[5]
        while data:
           tlv,data = readTLVs(data, count=1)
           results.append(tlv[0x01])

        return results

    def _cbLookupEmailError(self, result):
        return result

    def sendDirectorySearch(self, email=None, first=None, middle=None, last=None, maiden=None, nickname=None, address=None, city=None, state=None, zip=None, country=None, interest=None):
        """
        starts a directory search connection
        """
        #if self.services.has_key(SERVICE_DIRECTORY):
        #    if(email):
        #        return self.services[SERVICE_DIRECTORY].sendDirectorySearchByEmail(email)
        #    elif(interest):
        #        return self.services[SERVICE_DIRECTORY].sendDirectorySearchByInterest(interest)
        #    else:
        #        return self.services[SERVICE_DIRECTORY].sendDirectorySearchByNameAddr(first, middle, last, maiden, nickname, address, city, state, zip, country)
        #else:
        d = defer.Deferred()
        d.addErrback(self._ebDeferredSendDirectorySearchError)
        if(email):
            self.connectService(SERVICE_DIRECTORY,1).addCallback(lambda s:s.sendDirectorySearchByEmail(email).chainDeferred(d))
        elif(interest):
            self.connectService(SERVICE_DIRECTORY,1).addCallback(lambda s:s.sendDirectorySearchByInterest(interest).chainDeferred(d))
        else:
            self.connectService(SERVICE_DIRECTORY,1).addCallback(lambda s:s.sendDirectorySearchByNameAddr(first, middle, last, maiden, nickname, address, city, state, zip, country).chainDeferred(d))
        return d

    def _ebDeferredSendDirectorySearchError(self, error):
        log.msg('ERROR IN SEND DIRECTORY SEARCH %s' % error)

    def sendInterestsRequest(self):
        """
        retrieves list of directory interests
        """
        #if self.services.has_key(SERVICE_DIRECTORY):
        #    return self.services[SERVICE_DIRECTORY].sendInterestsRequest()
        #else:
        d = defer.Deferred()
        d.addErrback(self._ebDeferredSendInterestsRequestError)
        self.connectService(SERVICE_DIRECTORY,1).addCallback(lambda s:s.sendInterestsRequest().chainDeferred(d))
        return d

    def _ebDeferredSendInterestsRequestError(self, error):
        log.msg('ERROR IN SEND INTERESTS REQUEST %s' % error)

    def activateEmailNotification(self):
        """
        requests notification of email
        """
        if not self.services.has_key(SERVICE_EMAIL):
            self.connectService(SERVICE_EMAIL,1)

    def changePassword(self, oldpass, newpass):
        """
        changes a user's password
        """
        #if self.services.has_key(SERVICE_ADMIN):
        #    return self.services[SERVICE_ADMIN].changePassword(oldpass, newpass)
        #else:
        d = defer.Deferred()
        d.addErrback(self._ebDeferredChangePasswordError)
        self.connectService(SERVICE_ADMIN,1).addCallback(lambda s:s.changePassword(oldpass, newpass).chainDeferred(d))
        return d

    def _ebDeferredChangePasswordError(self, error):
        log.msg('ERROR IN CHANGE PASSWORD %s' % error)

    def changeEmail(self, email):
        """
        changes a user's registered email address
        """
        #if self.services.has_key(SERVICE_ADMIN):
        #    return self.services[SERVICE_ADMIN].setEmailAddress(email)
        #else:
        d = defer.Deferred()
        d.addErrback(self._ebDeferredChangeEmailError)
        self.connectService(SERVICE_ADMIN,1).addCallback(lambda s:s.setEmailAddress(email).chainDeferred(d))
        return d

    def _ebDeferredChangeEmailError(self, error):
        log.msg('ERROR IN CHANGE EMAIL %s' % error)

    def changeScreenNameFormat(self, formatted):
        """
        changes a user's screen name format
        note that only the spacing and capitalization can be changed
        """
        #if self.services.has_key(SERVICE_ADMIN):
        #    return self.services[SERVICE_ADMIN].formatScreenName(formatted)
        #else:
        d = defer.Deferred()
        d.addErrback(self._ebDeferredFormatSNError)
        self.connectService(SERVICE_ADMIN,1).addCallback(lambda s:s.formatScreenName(formatted).chainDeferred(d))
        return d

    def _ebDeferredFormatSNError(self, error):
        log.msg('ERROR IN FORMAT SCREEN NAME %s' % error)

    def getFormattedScreenName(self):
        """
        retrieves the user's formatted screen name
        """
        #if self.services.has_key(SERVICE_ADMIN):
        #    return self.services[SERVICE_ADMIN].requestFormattedScreenName()
        #else:
        d = defer.Deferred()
        d.addErrback(self._ebDeferredGetSNError)
        self.connectService(SERVICE_ADMIN,1).addCallback(lambda s:s.requestFormattedScreenName().chainDeferred(d))
        return d

    def _ebDeferredGetSNError(self, error):
        log.msg('ERROR IN SCREEN NAME RETRIEVAL %s' % error)

    def getEmailAddress(self):
        """
        retrieves the user's registered email address
        """
        #if self.services.has_key(SERVICE_ADMIN):
        #    return self.services[SERVICE_ADMIN].requestEmailAddress()
        #else:
        d = defer.Deferred()
        d.addErrback(self._ebDeferredGetEmailError)
        self.connectService(SERVICE_ADMIN,1).addCallback(lambda s:s.requestEmailAddress().chainDeferred(d))
        return d

    def _ebDeferredGetEmailError(self, error):
        log.msg('ERROR IN EMAIL ADDRESS RETRIEVAL %s' % error)

    def confirmAccount(self):
        """
        requests email to be sent to registered address for confirmation
        of account
        """
        #if self.services.has_key(SERVICE_ADMIN):
        #    return self.services[SERVICE_ADMIN].requestAccountConfirm()
        #else:
        d = defer.Deferred()
        d.addErrback(self._ebDeferredConfirmAccountError)
        self.connectService(SERVICE_ADMIN,1).addCallback(lambda s:s.requestAccountConfirm().chainDeferred(d))
        return d

    def _ebDeferredConfirmAccountError(self, error):
        log.msg('ERROR IN ACCOUNT CONFIRMATION RETRIEVAL %s' % error)

    def uploadBuddyIconToServer(self, iconData, iconLen):
        """
        uploads a buddy icon to the buddy icon server
        """
        d = defer.Deferred()
        d.addErrback(self._ebDeferredSendBuddyIconError)
        self.connectService(SERVICE_SSBI,1).addCallback(lambda s:s.uploadIcon(iconData, iconLen).chainDeferred(d))
        return d

    def _ebDeferredSendBuddyIconError(self, error):
        log.msg('ERROR IN SEND BUDDY ICON %s' % error)

    def retrieveBuddyIconFromServer(self, contact, hash, flags):
        """
        retrieves a buddy icon from the icon server
        """
        d = defer.Deferred()
        d.addErrback(self._ebDeferredRetrieveBuddyIconError)
        self.connectService(SERVICE_SSBI,1).addCallback(lambda s:s.retrieveAIMIcon(contact, hash, flags).chainDeferred(d))
        return d

    def _ebDeferredRetrieveBuddyIconError(self, error):
        log.msg('ERROR IN RETRIEVE BUDDY ICON %s' % error)

    def getMetaInfo(self, user, id):
        reqdata = struct.pack("<I",int(self.username))+'\xd0\x07'+ struct.pack("<H",id) +'\xb2\x04'+struct.pack("<I",int(user))
        data = struct.pack("<H",14)+reqdata
        tlvs = TLV(0x01, data)
        return self.sendSNACnr(0x15, 0x02, tlvs)

    def getShortInfo(self, user):
        #if user.
        reqdata = struct.pack("<I",int(self.username))+'\xd0\x07\x08\x00\xba\x04'+struct.pack("<I",int(user))
        data = struct.pack("<H",14)+reqdata
        tlvs = TLV(0x01, data)
        return self.sendSNAC(0x15, 0x02, tlvs).addCallback(self._cbGetShortInfo)

    def _cbGetShortInfo(self, snac):
        nick,first,last,email = self.parseBasicInfo(snac[5][16:])
        return nick,first,last,email

    def requestOffline(self):
        """
        request offline messages
        """
        reqdata = '\x08\x00'+struct.pack("<I",int(self.username))+'\x3c\x00\x02\x00'
        tlvs = TLV(0x01, reqdata)
        return self.sendSNACnr(0x15, 0x02, tlvs)
  
    #def _cbreqOffline(self, snac):
        #print "arg"

    def sendTypingNotification(self, user, type):
        #if user.
        return self.sendSNAC(0x04, 0x14, '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01'+chr(len(user))+user+type)

    def getAway(self, user):
        return self.sendSNAC(0x02, 0x05, '\x00\x03'+chr(len(user))+user).addCallback(self._cbGetAway)

    def _cbGetAway(self, snac):
        log.msg("_cbGetAway %r" % snac)
        try:
            tlvs = self.parseAway(snac[5])
        except (TypeError, struct.error):
            return [None, None]
        return [tlvs.get(0x03,None),tlvs.get(0x04,None)]

    #def acceptSendFileRequest(self,

# Methods to be overriden by the client
    def initDone(self):
        """
        called when we get the rate information, which means we should do other init. stuff.
        """
        log.msg('%s initDone' % self)
        pass

    def gotUserInfo(self, id, type, userinfo):
        """
        called when a user info packet is received
        """
        pass

    def gotAuthorizationResponse(self, uin, success):
        """
        called when a user sends an authorization response
        """
        pass

    def gotAuthorizationRequest(self, uin):
        """
        called when a user want's an authorization
        """
        pass

    def youWereAdded(self, uin):
        """
        called when a user added you to contact list
        """
        pass

    def buddyAdded(self, uin):
        """
        called when a buddy is added
        """
        pass

    def updateBuddy(self, user):
        """
        called when a buddy changes status, with the OSCARUser for that buddy.
        """
        log.msg('%s updateBuddy %s' % (self, user))
        pass

    def offlineBuddy(self, user):
        """
        called when a buddy goes offline
        """
        log.msg('%s offlineBuddy %s' % (self, user))
        pass

    def receiveMessage(self, user, multiparts, flags):
        """
        called when someone sends us a message
        """
        pass

    def receiveWarning(self, newLevel, user):
        """
        called when someone warns us.
        user is either None (if it was anonymous) or an OSCARUser
        """
        pass

    def receiveTypingNotify(self, type, user):
        """
        called when a typing notification occurs.
        type can be "begin", "idle", or "finish".
        user is an OSCARUser.
        """
        pass

    def errorMessage(self, message):
        """
        called when an error message should be signaled
        """
        pass

    def receiveChatInvite(self, user, message, exchange, fullName, instance, shortName, inviteTime):
        """
        called when someone invites us to a chat room
        """
        pass

    def chatReceiveMessage(self, chat, user, message):
        """
        called when someone in a chatroom sends us a message in the chat
        """
        pass

    def chatMemberJoined(self, chat, member):
        """
        called when a member joins the chat
        """
        pass

    def chatMemberLeft(self, chat, member):
        """
        called when a member leaves the chat
        """
        pass

    def chatInvitationAccepted(self, user):
        """
        called when a chat invitation we issued is accepted
        """
        pass

    def receiveSendFileRequest(self, user, file, description, cookie):
        """
        called when someone tries to send a file to us
        """
        pass

    def emailNotificationReceived(self, addr, url, unreadmsgs, hasunread):
        """
        called when the status of our email account changes
        """
        pass

    def receivedSelfInfo(self, user):
        """
        called when we receive information about ourself
        """
        pass

    def receivedIconUploadRequest(self, iconhash):
        """
        called when the server wants our buddy icon
        """
        pass

    def receivedIconDirect(self, user, icondata):
        """
        called when a user sends their buddy icon
        """
        pass


class OSCARService(SNACBased):
    def __init__(self, bos, cookie, d = None):
        SNACBased.__init__(self, cookie)
        self.bos = bos
        self.d = d

    def connectionLost(self, reason):
        for k,v in self.bos.services.items():
            if v == self:
                del self.bos.services[k]
                return

    def clientReady(self):
        SNACBased.clientReady(self)
        if self.d:
            self.d.callback(self)
            self.d = None


class ChatNavService(OSCARService):
    snacFamilies = {
        0x01:(4, 0x0110, 0x08e4),
        0x0d:(1, 0x0110, 0x08e4)
    }
    def oscar_01_07(self, snac):
        # rate info
        self.sendSNACnr(0x01, 0x08, '\000\001\000\002\000\003\000\004\000\005')
        self.sendSNACnr(0x0d, 0x02, '')

    def oscar_0D_09(self, snac):
        self.clientReady()

    def getChatInfo(self, exchange, name, instance):
        d = defer.Deferred()
        #d.addErrback(self._ebDeferredRequestSSIError)
        self.sendSNAC(0x0d,0x04,struct.pack('!HB',exchange,len(name)) + \
                      name + struct.pack('!HB',instance,2)). \
            addCallback(self._cbGetChatInfo, d)
        return d

    def _cbGetChatInfo(self, snac, d):
        data = snac[5][4:]
        exchange, length = struct.unpack('!HB',data[:3])
        fullName = data[3:3+length]
        instance = struct.unpack('!H',data[3+length:5+length])[0]
        tlvs = readTLVs(data[8+length:])
        shortName = tlvs[0x6a]
        inviteTime = struct.unpack('!L',tlvs[0xca])[0]
        info = (exchange,fullName,instance,shortName,inviteTime)
        d.callback(info)

    def createChat(self, shortName, exchange=4):
        #d = defer.Deferred()
        data = struct.pack('!H',exchange)
        # '\x00\x04'
        data = data + '\x06create\xff\xff\x01\x00\x03'
        data = data + TLV(0xd7, 'en')
        data = data + TLV(0xd6, 'us-ascii')
        data = data + TLV(0xd3, shortName)
        return self.sendSNAC(0x0d, 0x08, data).addCallback(self._cbCreateChat)
        #return d

    def _cbCreateChat(self, snac): #d):
        exchange, length = struct.unpack('!HB',snac[5][4:7])
        fullName = snac[5][7:7+length]
        instance = struct.unpack('!H',snac[5][7+length:9+length])[0]
        #d.callback((exchange, fullName, instance))
        return exchange, fullName, instance


class ChatService(OSCARService):
    snacFamilies = {
        0x01:(4, 0x0110, 0x08e4),
        0x0e:(1, 0x0110, 0x08e4)
    }
    def __init__(self,bos,cookie, d = None):
        OSCARService.__init__(self,bos,cookie,d)
        self.exchange = None
        self.fullName = None
        self.instance = None
        self.name = None
        self.members = None

    clientReady = SNACBased.clientReady # we'll do our own callback

    def oscar_01_07(self,snac):
        self.sendSNAC(0x01,0x08,"\000\001\000\002\000\003\000\004\000\005")
        self.clientReady()

    def oscar_0E_02(self, snac):
        data = snac[5]
        self.exchange, length = struct.unpack('!HB',data[:3])
        self.fullName = data[3:3+length]
        self.instance = struct.unpack('!H',data[3+length:5+length])[0]
        tlvs = readTLVs(data[8+length:])
        self.name = tlvs[0xd3]
        self.d.callback(self)

    def oscar_0E_03(self,snac):
        users=[]
        rest=snac[5]
        while rest:
            user, rest = self.bos.parseUser(rest, 1)
            users.append(user)
        if not self.fullName:
            self.members = users
        else:
            self.members.append(users[0])
            self.bos.chatMemberJoined(self,users[0])

    def oscar_0E_04(self,snac):
        user=self.bos.parseUser(snac[5])
        for u in self.members:
            if u.name == user.name: # same person!
                self.members.remove(u)
        self.bos.chatMemberLeft(self,user)

    def oscar_0E_06(self,snac):
        data = snac[5]
        user,rest=self.bos.parseUser(snac[5][14:],1)
        tlvs = readTLVs(rest[8:])
        message=tlvs[1]
        self.bos.chatReceiveMessage(self,user,message)

    def sendMessage(self,message):
        log.msg("Sending chat message... I hope.")
        tlvs=TLV(0x02,"us-ascii")+TLV(0x03,"en")+TLV(0x01,message)
        data = ''.join([chr(random.randrange(0, 127)) for i in range(8)]) # cookie
        data = data + "\x00\x03" # message channel 3
        data = data + TLV(1) # this is for a chat room
        data = data + TLV(6) # reflect message back to us
        data = data + TLV(5, tlvs) # our actual message data
        self.sendSNACnr(0x0e, 0x05, data)
        #self.sendSNAC(0x0e,0x05,
        #              "\x46\x30\x38\x30\x44\x00\x63\x00\x00\x03\x00\x01\x00\x00\x00\x06\x00\x00\x00\x05"+
        #              struct.pack("!H",len(tlvs))+
        #              tlvs)

    def leaveChat(self):
        self.disconnect()


class DirectoryService(OSCARService):
    snacFamilies = {
        0x01:(4, 0x0110, 0x08e4),
        0x0f:(1, 0x0110, 0x08e4)
    }

    def oscar_01_07(self,snac):
        self.sendSNAC(0x01,0x08,"\000\001\000\002\000\003\000\004\000\005")
        self.clientReady()

    def sendDirectorySearchByEmail(self, email):
        return self.sendSNAC(0x0f, 0x02, '\x00\x1c\x00\x08us-ascii\x00\x0a\x00\x02\x00\x01'+TLV(0x05, email)).addCallback(self._cbGetDirectoryInfo).addErrback(self._cbGetDirectoryError)

    def sendDirectorySearchByNameAddr(self, first=None, middle=None, last=None, maiden=None, nickname=None, address=None, city=None, state=None, zip=None, country=None):
        snacData = '\x00\x1c\x00\x08us-ascii\x00\x0a\x00\x02\x00\x00'
        if (first): snacData = snacData + TLV(0x01, first)
        if (last): snacData = snacData + TLV(0x02, last)
        if (middle): snacData = snacData + TLV(0x03, middle)
        if (maiden): snacData = snacData + TLV(0x04, maiden)
        if (country): snacData = snacData + TLV(0x06, country)
        if (state): snacData = snacData + TLV(0x07, state)
        if (city): snacData = snacData + TLV(0x08, city)
        if (nickname): snacData = snacData + TLV(0x0c, nickname)
        if (zip): snacData = snacData + TLV(0x0d, zip)
        if (address): snacData = snacData + TLV(0x21, address)
        return self.sendSNAC(0x0f, 0x02, snacData).addCallback(self._cbGetDirectoryInfo).addErrback(self._cbGetDirectoryError)

    def sendDirectorySearchByInterest(self, interest):
        return self.sendSNAC(0x0f, 0x02, '\x00\x1c\x00\x08us-ascii\x00\x0a\x00\x02\x00\x01'+TLV(0x0b, interest)).addCallback(self._cbGetDirectoryInfo).addErrback(self._cbGetDirectoryError)

    def _cbGetDirectoryInfo(self, snac):
        log.msg("Received directory info %s" % snac)
        results = []
        snacData = snac[5]
        status,foo,num = struct.unpack('!HHH', snacData[0:6])
        if status == 0x07:
            # We have an error, typically this seems to mean directory server is unavailable, for now, return empty results
            log.msg("We received an error, returning empty results")
            return results
        elif status == 0x05:
            # We're good
            pass
        else:
            # Uhm.. what?  For not, return empty results
            log.msg("Directory info request returned status %s" % str(hex(status)))
            return results
        numresults = int(num)
        log.msg("Got directory info, %d results" % (numresults))
        cnt = 1
        data = snacData[6:]
        while cnt <= numresults:
            log.msg("  Data %s" % (repr(data)))
            numpieces = int(struct.unpack('>H', data[0:2])[0])
            tlvs,data = readTLVs(data[2:], count=numpieces)
            log.msg("  Entry %s" % (repr(tlvs)))
            result = {}
            if tlvs.has_key(0x0001): result['first'] = tlvs[0x0001]
            if tlvs.has_key(0x0002): result['last'] = tlvs[0x0002]
            if tlvs.has_key(0x0003): result['middle'] = tlvs[0x0003]
            if tlvs.has_key(0x0004): result['maiden'] = tlvs[0x0004]
            if tlvs.has_key(0x0005): result['email'] = tlvs[0x0005]
            if tlvs.has_key(0x0006): result['country'] = tlvs[0x0006]
            if tlvs.has_key(0x0007): result['state'] = tlvs[0x0007]
            if tlvs.has_key(0x0008): result['city'] = tlvs[0x0008]
            if tlvs.has_key(0x0009): result['screenname'] = tlvs[0x0009]
            if tlvs.has_key(0x000b): result['interest'] = tlvs[0x000b]
            if tlvs.has_key(0x000c): result['nickname'] = tlvs[0x000c]
            if tlvs.has_key(0x000d): result['zip'] = tlvs[0x000d]
            if tlvs.has_key(0x001c): result['region'] = tlvs[0x001c]
            if tlvs.has_key(0x0021): result['address'] = tlvs[0x0021]
            results.append(result)
            cnt = cnt + 1

        self.disconnect()
        return results

    def _cbGetDirectoryError(self, error):
        log.msg("Got directory error %s" % error)
        return error

    def sendInterestsRequest(self):
        return self.sendSNAC(0x0f, 0x04, "").addCallback(self._cbGetInterests).addErrback(self._cbGetInterestsError)

    def _cbGetInterests(self, snac):
        log.msg("Got interests %s" % snac)
        pass

    def _cbGetInterestsError(self, error):
        log.msg("Got interests error %s" % error)
        pass

    def disconnect(self):
        """
        send the disconnect flap, and sever the connection
        """
        self.sendFLAP('', 0x04)
        self.transport.loseConnection()


class EmailService(OSCARService):
    snacFamilies = {
        0x01:(4, 0x0110, 0x08e4),
        0x18:(1, 0x0110, 0x08e4)
    }

    def oscar_01_07(self,snac):
        self.sendSNAC(0x01,0x08,"\000\001\000\002\000\003\000\004\000\005")
        cookie1 = "\xb3\x80\x9a\xd8\x0d\xba\x11\xd5\x9f\x8a\x00\x60\xb0\xee\x06\x31"
        cookie2 = "\x5d\x5e\x17\x08\x55\xaa\x11\xd3\xb1\x43\x00\x60\xb0\xfb\x1e\xcb"
        self.sendSNAC(0x18, 0x06, "\x00\x02"+cookie1+cookie2)
        self.sendEmailRequest()
        self.nummessages = 0
        self.clientReady()

    def oscar_18_07(self,snac):
        snacData = snac[5]
        cookie1 = snacData[8:16]
        cookie2 = snacData[16:24]
        cnt = int(struct.unpack('>H', snacData[24:26])[0])
        tlvs,foo = readTLVs(snacData[26:], count=cnt)
        #0x80 = number of unread messages
        #0x81 = have new messages
        #0x82 = domain
        #0x84 = flag
        #0x07 = url to access
        #0x09 = username
        #0x1b = something about gateway
        #0x1d = some odd string
        #0x05 = apparantly an alert title
        #0x0d = apparantly an alert url
        domain = tlvs[0x82]
        username = tlvs[0x09]
        url = tlvs[0x07]
        unreadnum = int(struct.unpack('>H', tlvs[0x80])[0])
        hasunread = int(struct.unpack('B', tlvs[0x81])[0])
        log.msg("received email notify: tlvs = %s" % (str(tlvs)))
        self.bos.emailNotificationReceived('@'.join([username,domain]),
              str(url), unreadnum, hasunread)

    def sendEmailRequest(self):
        log.msg("Activating email notifications")
        self.sendSNAC(0x18, 0x16, "\x02\x04\x00\x00\x00\x04\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00")

    def disconnect(self):
        """
        send the disconnect flap, and sever the connection
        """
        self.sendFLAP('', 0x04)
        self.transport.loseConnection()


class AdminService(OSCARService):
    snacFamilies = {
        0x01:(4, 0x0110, 0x08e4),
        0x07:(1, 0x0110, 0x08e4)
    }

    def oscar_01_07(self,snac):
        self.sendSNAC(0x01,0x08,"\000\001\000\002\000\003\000\004\000\005")
        self.clientReady()

    def requestFormattedScreenName(self):
        return self.sendSNAC(0x07, 0x02, TLV(0x01)).addCallback(self._cbInfoResponse).addErrback(self._cbInfoResponseError)

    def requestEmailAddress(self):
        return self.sendSNAC(0x07, 0x02, TLV(0x11)).addCallback(self._cbInfoResponse).addErrback(self._cbInfoResponseError)

    def requestRegistrationStatus(self):
        return self.sendSNAC(0x07, 0x02, TLV(0x13)).addCallback(self._cbInfoResponse).addErrback(self._cbInfoResponseError)

    def changePassword(self, oldpassword, newpassword):
        return self.sendSNAC(0x07, 0x04, TLV(0x02, newpassword)+TLV(0x12, oldpassword)).addCallback(self._cbInfoResponse).addErrback(self._cbInfoResponseError)

    def formatScreenName(self, fmtscreenname):
        """ Note that the new screen name must be the same as the official
        one with only changes to spacing and capitalization """
        return self.sendSNAC(0x07, 0x04, TLV(0x01, fmtscreenname)).addCallback(self._cbInfoResponse).addErrback(self._cbInfoResponseError)

    def setEmailAddress(self, email):
        return self.sendSNAC(0x07, 0x04, TLV(0x11, email)).addCallback(self._cbInfoResponse).addErrback(self._cbInfoResponseError)

    def _cbInfoResponse(self, snac):
        """ This is sent for both changes and requests """
        log.msg("Got info change %s" % (snac))
        snacData = snac[5]
        perms = int(struct.unpack(">H", snacData[0:2])[0])
        tlvcnt = int(struct.unpack(">H", snacData[2:4])[0])
        tlvs,foo = readTLVs(snacData[4:], count=tlvcnt)
        log.msg("TLVS are %s" % str(tlvs))
        sn = tlvs.get(0x01, None)
        url = tlvs.get(0x04, None)
        error = tlvs.get(0x08, None)
        email = tlvs.get(0x11, None)
        if not error:
            errorret = None
        elif error == '\x00\x01':
            errorret = (error, "Unable to format screen name because the requested screen name differs from the original.")
        elif error == '\x00\x06':
            #errorret = (error, "Unable to format screen name because the requested screen name ends in a space.")
            errorret = (error, "Unable to format screen name because the requested screen name is too long.")
        elif error == '\x00\x0b':
            #I get the above on a 'too long' screen name.. so what's this really?
            errorret = (error, "Unable to format screen name because the requested screen name is too long.")
        elif error == '\x00\x1d':
            errorret = (error, "Unable to change email address because there is already a request pending for this screen name.")
        elif error == '\x00\x21':
            errorret = (error, "Unable to change email address because the given address has too many screen names associated with it.")
        elif error == '\x00\x23':
            errorret = (error, "Unable to change email address because the given address is invalid.")
        else:
            errorret = (error, "Unknown error code %d" % int(error))
        self.disconnect()
        return (perms, sn, url, errorret, email)

    def _cbInfoResponseError(self, error):
        log.msg("GOT INFO CHANGE ERROR %s" % error)
        self.disconnect()
        pass

    def requestAccountConfirm(self):
        """ Causes an email message to be sent to the registered email
        address.  By following the instructions in the email, you can
        get the trial/unconfirmed flag removed from your account. """
        return self.sendSNAC(0x07, 0x06, "").addCallback(self._cbAccountConfirm).addErrback(self._cbAccountConfirmError)

    def _cbAccountConfirm(self, snac):
        log.msg("Got account confirmation %s" % snac)
        status = int(struct.unpack(">H", snac[5][0:2])[0])
        # Returns whether it failed or not
        self.disconnect()
        if (status == "\x00\x13"):
            return 1
        else:
            return 0

    def _cbAccountConfirmError(self, error):
        log.msg("GOT ACCOUNT CONFIRMATION ERROR %s" % error)
        self.disconnect()

    def disconnect(self):
        """
        send the disconnect flap, and sever the connection
        """
        self.sendFLAP('', 0x04)
        self.transport.loseConnection()



class SSBIService(OSCARService):
    #snacFamilies = {
    #    0x01:(3, 0x0010, 0x0629),
    #    0x10:(1, 0x0010, 0x0629)
    #}
    snacFamilies = {
        0x01:(4, 0x0110, 0x08e4),
        0x10:(1, 0x0110, 0x08e4)
    }

    def oscar_01_07(self,snac):
        self.sendSNAC(0x01,0x08,"\000\001\000\002\000\003\000\004\000\005")
        self.clientReady()

    def uploadIcon(self, iconData, iconLen):
        return self.sendSNAC(0x10, 0x02, struct.pack('!HH', 0x0001, iconLen)+iconData).addCallback(self._cbIconResponse).addErrback(self._cbIconResponseError)

    def _cbIconResponse(self, snac):
        log.msg("GOT ICON RESPONSE: %s" % str(snac))
        #\x05\x00\x00\x00\x00 - bad format?
        #\x04\x00\x00\x00\x00 - too large?
        #\x00\x00\x01\x01\x10 - ok, this is a hash, last one is length
        self.disconnect()

        # FIXME, This needs to be done like... correctly.  =D
        resultcode = snac[5][0]
        if resultcode == 0x04:
            return "Icon too large."
        if resultcode == 0x05:
            return "Icon not in accepted format."
        if resultcode == 0x01:
            # Success
            checksumlen = struct.unpack('!B', snac[5][4])[0]
            checksum = snac[5:5+checksumlen]
            return checksum
        return "Unknown result from buddy icon retrieval."

    def _cbIconResponseError(self, error):
        log.msg("GOT UPLOAD ICON ERROR %s" % error)
        self.disconnect()

    def retrieveAIMIcon(self, contact, iconhash, iconflags):
        log.msg("Requesting icon for %s with hash %s" % (contact, binascii.hexlify(iconhash)))
        return self.sendSNAC(0x10, 0x04, struct.pack('!B', len(contact))+contact+"\x01\x00\x01"+struct.pack('!B', iconflags)+struct.pack('!B', len(iconhash))+iconhash).addCallback(self._cbAIMIconRequest).addErrback(self._cbAIMIconRequestError)

    def _cbAIMIconRequest(self, snac):
        v = snac[5]
        scrnnamelen = int((struct.unpack('!B', v[0]))[0])
        scrnname = v[1:1+scrnnamelen]
        p = 1+scrnnamelen
        flags,iconcsumtype,iconcsumlen = struct.unpack('!HBB', v[p:p+4])
        iconcsumlen = int(iconcsumlen)
        p = p+4
        iconcsum = v[p:p+iconcsumlen]
        p = p+iconcsumlen
        iconlen = int((struct.unpack('!H', v[p:p+2]))[0])
        p = p + 2
        log.msg("Got Icon Request (AIM): %s, %s, %d" % (scrnname, binascii.hexlify(iconcsum), iconlen))
        if iconlen > 0 and iconlen != 90:
            icondata = v[p:p+iconlen]
        else:
            icondata = None
        self.disconnect()
        return scrnname,iconcsumtype,iconcsum,iconlen,icondata

    def _cbAIMIconRequestError(self, error):
        log.msg("GOT AIM ICON REQUEST ERROR %s" % error)
        self.disconnect()

    def disconnect(self):
        """
        send the disconnect flap, and sever the connection
        """
        self.sendFLAP('', 0x04)
        self.transport.loseConnection()



class OscarAuthenticator(OscarConnection):
    BOSClass = BOSConnection
    def __init__(self,username,password,deferred=None,icq=0):
        self.username=username
        self.password=password
        self.deferred=deferred
        self.icq=icq # icq mode is disabled
        #if icq and self.BOSClass==BOSConnection:
        #    self.BOSClass=ICQConnection

    def oscar_(self,flap):
        if config.usemd5auth:
            self.sendFLAP("\000\000\000\001", 0x01)
            self.sendFLAP(SNAC(0x17,0x06,0,
                               TLV(TLV_USERNAME,self.username)+
                               TLV(0x004B)))
            self.state="Key"
        else:
            # stupid max password length...
            encpass=encryptPasswordICQ(self.password[:8])
            #self.sendFLAP('\000\000\000\001'+
            #              TLV(0x01,self.username)+
            #              TLV(0x02,encpass)+
            #              TLV(0x03,'ICQ Inc. - Product of ICQ (TM).2001b.5.18.1.3659.85')+
            #              TLV(0x16,"\x01\x0a")+
            #              TLV(0x17,"\x00\x05")+
            #              TLV(0x18,"\x00\x12")+
            #              TLV(0x19,"\000\001")+
            #              TLV(0x1a,"\x0eK")+
            #              TLV(0x14,"\x00\x00\x00U")+
            #              TLV(0x0f,"en")+
            #              TLV(0x0e,"us"),0x01)

            #self.sendFLAP('\000\000\000\001'+
            #              TLV(0x01,self.username)+
            #              TLV(0x02,encpass)+
            #              TLV(0x03,'ICQ Inc. - Product of ICQ (TM).2003a.5.45.1.3777.85')+
            #              TLV(0x16,"\x01\x0a")+
            #              TLV(TLV_CLIENTMAJOR,"\x00\x05")+
            #              TLV(TLV_CLIENTMINOR,"\x00\x2d")+
            #              TLV(0x19,"\000\001")+
            #              TLV(TLV_CLIENTSUB,"\x0e\xc1")+
            #              TLV(0x14,"\x00\x00\x00\x55")+
            #              TLV(0x0f,"en")+
            #              TLV(0x0e,"us"),0x01)
	    self.sendFLAP('\000\000\000\001'+
		TLV(TLV_USERNAME,self.username)+
		TLV(TLV_ROASTPASSARRAY,encpass)+
		TLV(TLV_CLIENTNAME,'ICQBasic')+
		TLV(TLV_CLIENTID,"\x01\x0a")+
		TLV(TLV_CLIENTMAJOR,"\x00\x14")+
		TLV(TLV_CLIENTMINOR,"\x00\x22")+
		TLV(TLV_CLIENTLESSER,"\x00\x01")+
		TLV(TLV_CLIENTSUB,"\x06\x66")+
		TLV(TLV_CLIENTDISTNUM,"\x00\x00\x06\x66")+
		TLV(TLV_LANG,"en")+
		TLV(TLV_COUNTRY,"us"),0x01)
	    self.state="Cookie"

    def oscar_Key(self,data):
        snac=readSNAC(data[1])
        if not snac:
            log.msg("Illegal SNAC data received in oscar_Key: %s" % data)
            return
        len=ord(snac[5][0]) * 256 + ord(snac[5][1])
        key=snac[5][2:2+len]
        encpass=encryptPasswordMD5(self.password[:8],key)
        self.sendFLAP(SNAC(0x17,0x02,0,
		TLV(TLV_USERNAME,self.username)+
		TLV(TLV_PASSWORD,encpass)+
		TLV(0x004C)+
		TLV(TLV_CLIENTNAME,'ICQBasic')+
		TLV(TLV_CLIENTID,"\x01\x0a")+
		TLV(TLV_CLIENTMAJOR,"\x00\x14")+
		TLV(TLV_CLIENTMINOR,"\x00\x22")+
		TLV(TLV_CLIENTLESSER,"\x00\x01")+
		TLV(TLV_CLIENTSUB,"\x06\x66")+
		TLV(TLV_CLIENTDISTNUM,"\x00\x00\x06\x66")+
		TLV(TLV_LANG,"en")+
		TLV(TLV_COUNTRY,"us")))
        return "Cookie"

    def oscar_Cookie(self,data):
        snac=readSNAC(data[1])
        if not snac:
            log.msg("Illegal SNAC data received in oscar_Cookie: %s" % data)
            return
        if self.icq:
            i=snac[5].find("\000")
            snac[5]=snac[5][i:]
        tlvs=readTLVs(snac[5])
        log.msg(tlvs)
	self.parseAnnounceAboutClientFromServer(tlvs)
        if tlvs.has_key(6):
            self.cookie=tlvs[6]
            server,port=string.split(tlvs[5],":")
            d = self.connectToBOS(server, int(port))
            d.addErrback(lambda x: log.msg("Connection Failed! Reason: %s" % x))
            if self.deferred:
                d.chainDeferred(self.deferred)
            self.disconnect()
        elif tlvs.has_key(8):
            errorcode=tlvs[8]
            if tlvs.has_key(4):
                errorurl=tlvs[4]
            else:
                errorurl=None
            if errorcode=='\x00\x02':
                error="The instant messenger server is temporarily unavailable"
            elif errorcode=='\x00\x05':
                error="Incorrect username or password."
            elif errorcode=='\x00\x11':
                error="Your account is currently suspended."
            elif errorcode=='\x00\x14':
                error="The instant messenger server is temporarily unavailable"
            elif errorcode=='\x00\x18':
                error="You have been connecting and disconnecting too frequently. Wait ten minutes and try again. If you continue to try, you will need to wait even longer."
            elif errorcode=='\x00\x1c':
                error="The client version you are using is too old.  Please contact the maintainer of this software if you see this message so that the problem can be resolved."
            else: error=repr(errorcode)
            self.error(error,errorurl)
        else:
            log.msg('hmm, weird tlvs for %s cookie packet' % str(self))
            log.msg(tlvs)
            log.msg('snac')
            log.msg(str(snac))
        return "None"

    def oscar_None(self,data): pass

    def connectToBOS(self, server, port):
        c = protocol.ClientCreator(reactor, self.BOSClass, self.username, self.cookie)
        return c.connectTCP(server, int(port))

    def error(self,error,url):
        log.msg("ERROR! %s %s" % (error,url))
        if self.deferred: self.deferred.errback((error,url))
        self.transport.loseConnection()
	
    def parseAnnounceAboutClientFromServer(self, tlvs):
	if tlvs.has_key(65):
		latestb_url = tlvs[65]
		log.msg('Latest official client (beta). URL: %s' % latestb_url)
	if tlvs.has_key(66):
		latestb_info = tlvs[66]
		log.msg('Latest official client (beta). Info: %s' % latestb_info)
	if tlvs.has_key(64):
		latestb_build = struct.unpack('!L',tlvs[64])
		log.msg('Latest official client (beta). Build: %s' % latestb_build)
	if tlvs.has_key(67):
		latestb_name = tlvs[67]
		log.msg('Latest official client (beta). Name: %s' % latestb_name)
	if tlvs.has_key(69):
		latestr_url = tlvs[69]
		log.msg('Latest official client (release). URL: %s' % latestr_url)
	if tlvs.has_key(70):
		latestr_info = tlvs[70]
		log.msg('Latest official client (release). Info: %s' % latestr_info)
	if tlvs.has_key(68):
		latestr_build = struct.unpack('!L',tlvs[68])
		log.msg('Latest official client (release). Build: %s' % latestr_build)
	if tlvs.has_key(71):
		latestr_name = tlvs[71]
		log.msg('Latest official client (release). Name: %s' % latestr_name)

FLAP_CHANNEL_NEW_CONNECTION = 0x01
FLAP_CHANNEL_DATA = 0x02
FLAP_CHANNEL_ERROR = 0x03
FLAP_CHANNEL_CLOSE_CONNECTION = 0x04

SERVICE_ADMIN = 0x07
SERVICE_CHATNAV = 0x0d
SERVICE_CHAT = 0x0e
SERVICE_DIRECTORY = 0x0f
SERVICE_SSBI = 0x10
SERVICE_EMAIL = 0x18
serviceClasses = {
    SERVICE_ADMIN:AdminService,
    SERVICE_CHATNAV:ChatNavService,
    SERVICE_CHAT:ChatService,
    SERVICE_DIRECTORY:DirectoryService,
    SERVICE_SSBI:SSBIService,
    SERVICE_EMAIL:EmailService
}
TLV_USERNAME = 0x0001
TLV_ROASTPASSARRAY = 0x0002
TLV_CLIENTNAME = 0x0003
TLV_COUNTRY = 0x000E
TLV_LANG = 0x000F
TLV_CLIENTDISTNUM = 0x0014
TLV_CLIENTID = 0x0016
TLV_CLIENTMAJOR = 0x0017
TLV_CLIENTMINOR = 0x0018
TLV_CLIENTLESSER = 0x0019
TLV_CLIENTSUB = 0x001A
TLV_PASSWORD = 0x0025
TLV_USESSI = 0x004A

###
# Capabilities
###

# Supports avatars/buddy icons
CAP_ICON = '\x09\x46\x13\x46\x4C\x7F\x11\xD1\x82\x22\x44\x45\x53\x54\x00\x00'
# User is using iChat
CAP_ICHAT = '\x09\x46\x00\x00\x4C\x7F\x11\xD1\x82\x22\x44\x45\x53\x54\x00\x00'
# ... and has audio-video support
CAP_ICHATAV = '\x09\x46\x01\x05\x4C\x7F\x11\xD1\x82\x22\x44\x45\x45\x53\x54\x00'
# Supports voice chat
CAP_VOICE = '\x09\x46\x13\x41\x4C\x7F\x11\xD1\x82\x22\x44\x45\x53\x54\x00\x00'
# Supports direct image/direct im
CAP_IMAGE = '\x09\x46\x13\x45\x4C\x7F\x11\xD1\x82\x22\x44\x45\x53\x54\x00\x00'
# Supports chat
CAP_CHAT = '\x74\x8F\x24\x20\x62\x87\x11\xD1\x82\x22\x44\x45\x53\x54\x00\x00'
# Supports file transfers (can accept files)
CAP_GET_FILE = '\x09\x46\x13\x48\x4C\x7F\x11\xD1\x82\x22\x44\x45\x53\x54\x00\x00'
# Supports file transfers (can send files)
CAP_SEND_FILE = '\x09\x46\x13\x43\x4C\x7F\x11\xD1\x82\x22\x44\x45\x53\x54\x00\x00'
# Supports games
CAP_GAMES = '\x09\x46\x13\x4A\x4C\x7F\x11\xD1\x82\x22\x44\x45\x53\x54\x00\x00'
# Supports buddy list transfer
CAP_SEND_LIST = '\x09\x46\x13\x4B\x4C\x7F\x11\xD1\x82\x22\x44\x45\x53\x54\x00\x00'
# Supports channel 2 extended
CAP_SERV_REL = '\x09\x46\x13\x49\x4C\x7F\x11\xD1\x82\x22\x44\x45\x53\x54\x00\x00'
# Allow communication between ICQ and AIM
CAP_CROSS_CHAT = '\x09\x46\x13\x4D\x4C\x7F\x11\xD1\x82\x22\x44\x45\x53\x54\x00\x00'
# Supports UTF-8 encoded messages, only used with ICQ
CAP_UTF = '\x09\x46\x13\x4E\x4C\x7F\x11\xD1\x82\x22\x44\x45\x53\x54\x00\x00'
# Supports RTF messages
CAP_RTF = '\x97\xB1\x27\x51\x24\x3C\x43\x34\xAD\x22\xD6\xAB\xF7\x3F\x14\x92'
# Is Apple iChat (probably indicates that it supports iChat features)
CAP_ICHAT = '\x09\x46\x00\x00\x4c\x7f\x11\xd1\x82\x22\x44\x45\x53\x54\x00\x00'
# Supports some sort of secure instant messaging. (not trillian)
CAP_SECUREIM = '\x09\x46\x00\x01\x4c\x7f\x11\xd1\x82\x22\x44\x45\x53\x54\x00\x00'
# Supports video chat? (other caps seem to indicate this as well)
CAP_VIDEO = '\x09\x46\x01\x00\x4c\x7f\x11\xd1\x82\x22\x44\x45\x53\x54\x00\x00'
# "Live Video" support in Windows AIM 5.5.3501 and newer
CAP_LIVE_VIDEO = '\x09\x46\x01\x01\x4c\x7f\x11\xd1\x82\x22\x44\x45\x53\x54\x00\x00'
# "Camera" support in Windows AIM 5.5.3501 and newer
CAP_CAMERA = '\x09\x46\x01\x02\x4c\x7f\x11\xd1\x82\x22\x44\x45\x53\x54\x00\x00'
# Not really sure about this one.  In an email from 26 Sep 2003,
# Matthew Sachs suggested that, "this * is probably the capability
# for the SMS features."
CAP_SMS = '\x09\x46\x01\xff\x4c\x7f\x11\xd1\x82\x22\x44\x45\x53\x54\x00\x00'
# In Windows AIM 5.5.3501 and newer
CAP_GENERICUNKNOWN1 = '\x09\x46\x01\x03\x4c\x7f\x11\xd1\x82\x22\x44\x45\x53\x54\x00\x00'
# Total unknowns
CAP_GENERICUNKNOWN2 = '\x09\x46\xf0\x03\x4c\x7f\x11\xd1\x82\x22\x44\x45\x53\x54\x00\x00'
CAP_GENERICUNKNOWN3 = '\x09\x46\xf0\x04\x4c\x7f\x11\xd1\x82\x22\x44\x45\x53\x54\x00\x00'
CAP_GENERICUNKNOWN4 = '\x09\x46\xf0\x05\x4c\x7f\x11\xd1\x82\x22\x44\x45\x53\x54\x00\x00'
CAP_GENERICUNKNOWN5 = '\x97\xb1\x27\x51\x24\x3c\x43\x34\xad\x22\xd6\xab\xf7\x3f\x14\x09'
# Is a Hiptop device?
CAP_HIPTOP = '\x09\x46\x13\x23\x4c\x7f\x11\xd1\x82\x22\x44\x45\x53\x54\x00\x00'
# Supports ICQ direct connections
CAP_ICQ_DIRECT = '\x09\x46\x13\x44\x4c\x7f\x11\xd1\x82\x22\x44\x45\x53\x54\x00\x00'
# Supports some sort of add-ins/extras?  This seems different than ICQ Xtraz.
CAP_ADDINS = '\x09\x46\x13\x47\x4c\x7f\x11\xd1\x82\x22\x44\x45\x53\x54\x00\x00'
# Another games related one.
CAP_GAMES2 = '\x09\x46\x13\x4a\x4c\x7f\x11\xd1\x22\x82\x44\x45\x53\x54\x00\x00'
# Supports old style ICQ utf-8.
CAP_ICQUTF8OLD = '\x2e\x7a\x64\x75\xfa\xdf\x4d\xc8\x88\x6f\xea\x35\x95\xfd\xb6\xdf'
# Supports ICQ2GO extensions
CAP_ICQ2GO = '\x56\x3f\xc8\x09\x0b\x6f\x41\xbd\x9f\x79\x42\x26\x09\xdf\xa2\xf3'
# No idea
CAP_APINFO = '\xaa\x4a\x32\xb5\xf8\x84\x48\xc6\xa3\xd7\x8c\x50\x97\x19\xfd\x5b'
# Supports Trillian style encrypted messages
CAP_TRILLIANCRYPT = '\xf2\xe7\xc7\xf4\xfe\xad\x4d\xfb\xb2\x35\x36\x79\x8b\xdf\x00\x00'
# Unknown ICQ5 capabilities, probably related to Xtras
CAP_ICQ5UNKNOWN1 = '\x09\x46\x13\x4c\x4c\x7f\x11\xd1\x82\x22\x44\x45\x53\x54\x00\x00'
CAP_ICQ5UNKNOWN2 = '\xb9\x97\x08\xb5\x3a\x92\x42\x02\xb0\x69\xf1\xe7\x57\xbb\x2e\x17'
# Supports ICQ 5 video chat
CAP_ICQVIDEO = '\x17\x8c\x2d\x9b\xda\xa5\x45\xbb\x8d\xdb\xf3\xbd\xbd\x53\xa1\x0a'
# Supports ICQ 5 Xtraz (includes multi-user chat)
CAP_ICQXTRAZ = '\x1a\x09\x3c\x6c\xd7\xfd\x4e\xc5\x9d\x51\xa6\x47\x4e\x34\xf5\xa0'
# Supports ICQ 5 voice chat (also push to talk gets listed as supported?)
CAP_ICQVOICE = '\x67\x36\x15\x15\x61\x2d\x4c\x07\x8f\x3d\xbd\xe6\x40\x8e\xa0\x41'
# Causes a push to talk icon to be displayed, why is this different?
CAP_ICQPUSHTOTALK = '\xe3\x62\xc1\xe9\x12\x1a\x4b\x94\xa6\x26\x7a\x74\xde\x24\x27\x0d'
# Empty capability ... ?
CAP_EMPTY = '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'


# Mappings of capabilities back to identifier strings.
CAPS = dict( [
    (CAP_ICON, 'icon'),
    (CAP_VOICE, 'voice'),
    (CAP_IMAGE, 'image'),
    (CAP_CHAT, 'chat'),
    (CAP_GET_FILE, 'getfile'),
    (CAP_SEND_FILE, 'sendfile'),
    (CAP_SEND_LIST, 'sendlist'),
    (CAP_GAMES, 'games'),
    (CAP_SERV_REL, 'serv_rel'),
    (CAP_CROSS_CHAT, 'cross_chat'),
    (CAP_UTF, 'unicode'),
    (CAP_RTF, 'rtf'),
    (CAP_ICHAT, 'ichat'),
    (CAP_SECUREIM, 'secureim'),
    (CAP_VIDEO, 'video'),
    (CAP_LIVE_VIDEO, 'live_video'),
    (CAP_CAMERA, 'camera'),
    (CAP_GENERICUNKNOWN1, 'genericunknown1'),
    (CAP_GENERICUNKNOWN2, 'genericunknown2'),
    (CAP_GENERICUNKNOWN3, 'genericunknown3'),
    (CAP_GENERICUNKNOWN4, 'genericunknown4'),
    (CAP_GENERICUNKNOWN5, 'genericunknown5'),
    (CAP_ICHATAV, 'ichatav'),
    (CAP_SMS, 'sms'),
    (CAP_HIPTOP, 'hiptop'),
    (CAP_ICQ_DIRECT, 'icq_direct'),
    (CAP_ADDINS, 'addins'),
    (CAP_GAMES2, 'games2'),
    (CAP_ICQUTF8OLD, 'icqutf8old'),
    (CAP_ICQ2GO, 'icq2go'),
    (CAP_APINFO, 'apinfo'),
    (CAP_TRILLIANCRYPT, 'trilliancrypt'),
    (CAP_ICQ5UNKNOWN1, 'icq5unknown1'),
    (CAP_ICQ5UNKNOWN2, 'icq5unknown2'),
    (CAP_ICQVIDEO, 'icqvideochat'),
    (CAP_ICQVOICE, 'icqvoicechat'),
    (CAP_ICQXTRAZ, 'icqxtraz'),
    (CAP_ICQPUSHTOTALK, 'icqpushtotalk'),
    (CAP_EMPTY, 'empty')
    ] )

# 24 statuses - ICQ 5.1
# 5 statuses - China localization "Netvigator"
# 3 statuses - German localization "ProSieben"
# 3 statuses - Russian localization "Rambler"
X_STATUS_CAPS = dict( [
	('\x01\xd8\xd7\xee\xac\x3b\x49\x2a\xa5\x8d\xd3\xd8\x77\xe6\x6b\x92',0),
	('\x5a\x58\x1e\xa1\xe5\x80\x43\x0c\xa0\x6f\x61\x22\x98\xb7\xe4\xc7',1),
	('\x83\xc9\xb7\x8e\x77\xe7\x43\x78\xb2\xc5\xfb\x6c\xfc\xc3\x5b\xec',2),
	('\xe6\x01\xe4\x1c\x33\x73\x4b\xd1\xbc\x06\x81\x1d\x6c\x32\x3d\x81',3),
	('\x8c\x50\xdb\xae\x81\xed\x47\x86\xac\xca\x16\xcc\x32\x13\xc7\xb7',4),
	('\x3f\xb0\xbd\x36\xaf\x3b\x4a\x60\x9e\xef\xcf\x19\x0f\x6a\x5a\x7f',5),
	('\xf8\xe8\xd7\xb2\x82\xc4\x41\x42\x90\xf8\x10\xc6\xce\x0a\x89\xa6',6),
	('\x80\x53\x7d\xe2\xa4\x67\x4a\x76\xb3\x54\x6d\xfd\x07\x5f\x5e\xc6',7),
	('\xf1\x8a\xb5\x2e\xdc\x57\x49\x1d\x99\xdc\x64\x44\x50\x24\x57\xaf',8),
	('\x1b\x78\xae\x31\xfa\x0b\x4d\x38\x93\xd1\x99\x7e\xee\xaf\xb2\x18',9),
	('\x61\xbe\xe0\xdd\x8b\xdd\x47\x5d\x8d\xee\x5f\x4b\xaa\xcf\x19\xa7',10),
	('\x48\x8e\x14\x89\x8a\xca\x4a\x08\x82\xaa\x77\xce\x7a\x16\x52\x08',11),
	('\x10\x7a\x9a\x18\x12\x32\x4d\xa4\xb6\xcd\x08\x79\xdb\x78\x0f\x09',12),
	('\x6f\x49\x30\x98\x4f\x7c\x4a\xff\xa2\x76\x34\xa0\x3b\xce\xae\xa7',13),
	('\x12\x92\xe5\x50\x1b\x64\x4f\x66\xb2\x06\xb2\x9a\xf3\x78\xe4\x8d',14),
	('\xd4\xa6\x11\xd0\x8f\x01\x4e\xc0\x92\x23\xc5\xb6\xbe\xc6\xcc\xf0',15),
	('\x60\x9d\x52\xf8\xa2\x9a\x49\xa6\xb2\xa0\x25\x24\xc5\xe9\xd2\x60',16),
	('\x63\x62\x73\x37\xa0\x3f\x49\xff\x80\xe5\xf7\x09\xcd\xe0\xa4\xee',17),
	('\x1f\x7a\x40\x71\xbf\x3b\x4e\x60\xbc\x32\x4c\x57\x87\xb0\x4c\xf1',18),
	('\x78\x5e\x8c\x48\x40\xd3\x4c\x65\x88\x6f\x04\xcf\x3f\x3f\x43\xdf',19),
	('\xa6\xed\x55\x7e\x6b\xf7\x44\xd4\xa5\xd4\xd2\xe7\xd9\x5c\xe8\x1f',20),
	('\x12\xd0\x7e\x3e\xf8\x85\x48\x9e\x8e\x97\xa7\x2a\x65\x51\xe5\x8d',21),
	('\xba\x74\xdb\x3e\x9e\x24\x43\x4b\x87\xb6\x2f\x6b\x8d\xfe\xe5\x0f',22),
	('\x63\x4f\x6b\xd8\xad\xd2\x4a\xa1\xaa\xb9\x11\x5b\xc2\x6d\x05\xa1',23),
	('\x2c\xe0\xe4\xe5\x7c\x64\x43\x70\x9c\x3a\x7a\x1c\xe8\x78\xa7\xdc',24),
	('\x10\x11\x17\xc9\xa3\xb0\x40\xf9\x81\xac\x49\xe1\x59\xfb\xd5\xd4',25),
	('\x16\x0c\x60\xbb\xdd\x44\x43\xf3\x91\x40\x05\x0f\x00\xe6\xc0\x09',26),
	('\x64\x43\xc6\xaf\x22\x60\x45\x17\xb5\x8c\xd7\xdf\x8e\x29\x03\x52',27),
	('\x16\xf5\xb7\x6f\xa9\xd2\x40\x35\x8c\xc5\xc0\x84\x70\x3c\x98\xfa',28),
	('\x63\x14\x36\xff\x3f\x8a\x40\xd0\xa5\xcb\x7b\x66\xe0\x51\xb3\x64',29),
	('\xb7\x08\x67\xf5\x38\x25\x43\x27\xa1\xff\xcf\x4c\xc1\x93\x97\x97',30),
	('\xdd\xcf\x0e\xa9\x71\x95\x40\x48\xa9\xc6\x41\x32\x06\xd6\xf2\x80',31),
	('\xd4\xe2\xb0\xba\x33\x4e\x4f\xa5\x98\xd0\x11\x7d\xbf\x4d\x3c\xc8',32),
	('\xcd\x56\x43\xa2\xc9\x4c\x47\x24\xb5\x2c\xdc\x01\x24\xa1\xd0\xcd',33),
	('\x00\x72\xd9\x08\x4a\xd1\x43\xdd\x91\x99\x6f\x02\x69\x66\x02\x6f',34)
	])
	
# 24 moods - ICQ 6
X_STATUS_MOODS = dict([
	(23,0),
	(1,1),
	(2,2),
	(3,3),
	(4,4),
	(5,5),
	(6,6),
	(7,7),
	(8,8),
	(9,9),
	(10,10),
	(11,11),
	(12,12),
	(13,13),
	(14,14),
	(15,15),
	(16,16),
	(0,17),
	(17,18),
	(18,19),
	(19,20),
	(20,21),
	(21,22),
	(22,23)
	])
	
# names for x-statuses and moods
X_STATUS_NAME = [	
	'xstatus_angry',
	'xstatus_taking_a_bath',
	'xstatus_tired',
	'xstatus_party',
	'xstatus_drinking_beer',
	'xstatus_thinking',
	'xstatus_eating',
	'xstatus_watching_tv',
	'xstatus_meeting',
	'xstatus_coffee',
	'xstatus_listening_to_music',
	'xstatus_business',
	'xstatus_shooting',
	'xstatus_having_fun',
	'xstatus_on_the_phone',
	'xstatus_gaming',
	'xstatus_studying',
	'xstatus_shopping',
	'xstatus_feeling_sick',
	'xstatus_sleeping',
	'xstatus_surfing',
	'xstatus_browsing',
	'xstatus_working',
	'xstatus_typing',
	'xstatus_cn1',
	'xstatus_cn2',
	'xstatus_cn3',
	'xstatus_cn4',
	'xstatus_cn5',
	'xstatus_de1',
	'xstatus_de2',
	'xstatus_de3',
	'xstatus_ru1',
	'xstatus_ru2',
	'xstatus_ru3'
	]

###
# Status indicators
###
# Web status icons should be updated to show status
STATUS_WEBAWARE = 0x0001
# IP address should be provided to requestors
STATUS_SHOWIP = 0x0002
# Indicate that it is the user's birthday
STATUS_BIRTHDAY = 0x0008
# "User active webfront flag"... no idea
STATUS_WEBFRONT = 0x0020
# Client does not support direct connections
STATUS_DCDISABLED = 0x0100
# Client will do direct connections upon authorization
STATUS_DCAUTH = 0x1000
# Client will only do direct connections with contact users
STATUS_DCCONT = 0x2000

###
# Typing notification status codes
###
MTN_FINISH = '\x00\x00'
MTN_IDLE = '\x00\x01'
MTN_BEGIN = '\x00\x02'

# Motd types list
MOTDS = dict( [
    (0x01, "Mandatory upgrade needed notice"),
    (0x02, "Advisable upgrade notice"),
    (0x03, "AIM/ICQ service system announcements"),
    (0x04, "Standard notice"),
    (0x06, "Some news from AOL service") ] )

###
# SSI Types
###
AIM_SSI_TYPE_BUDDY = 0x0000
AIM_SSI_TYPE_GROUP = 0x0001
AIM_SSI_TYPE_PERMIT = 0x0002
AIM_SSI_TYPE_DENY = 0x0003
AIM_SSI_TYPE_PDINFO = 0x0004
AIM_SSI_TYPE_PRESENCEPREFS = 0x0005
AIM_SSI_TYPE_ICQSHORTCUT = 0x0009 # Not sure if this is true
AIM_SSI_TYPE_IGNORE = 0x000e
AIM_SSI_TYPE_LASTUPDATE = 0x000f
AIM_SSI_TYPE_SMS = 0x0010
AIM_SSI_TYPE_IMPORTTIME = 0x0013
AIM_SSI_TYPE_ICONINFO = 0x0014
AIM_SSI_TYPE_PHANTOMBUDDY = 0x0019
AIM_SSI_TYPE_UNKNOWN0 = 0x001b
AIM_SSI_TYPE_LOCALBUDDYNAME = 0x0131

###
# Permission Types
###
AIM_SSI_PERMDENY_PERMIT_ALL = 0x01
AIM_SSI_PERMDENY_DENY_ALL = 0x02
AIM_SSI_PERMDENY_PERMIT_SOME = 0x03
AIM_SSI_PERMDENY_DENY_SOME = 0x04
AIM_SSI_PERMDENY_PERMIT_BUDDIES = 0x05

###
# Visibility Masks
###
AIM_SSI_VISIBILITY_ALL = '\xff\xff\xff\xff'
AIM_SSI_VISIBILITY_NOTAIM = '\x00\x00\x00\x04'

###
# Capabilities as text
###
MSGTYPE_TEXT_ID_UTF8MSGS = '{0946134E-4C7F-11D1-8222-444553540000}'

###
# Xtraz stuff
###
MSGTYPE_ID_XTRAZ_SCRIPT = 0x3b60b3ef, 0xd82a6c45, 0xa4e09c5a, 0x5e67e865
MSGSUBTYPE_SCRIPT_NOTIFY = 0x0008
MSGACTION_REQUEST_TYPE_STRING = 0x002a
