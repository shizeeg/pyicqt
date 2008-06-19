# Copyright 2005-2006 Daniel Henninger <jadestorm@nc.rr.com>
# Licensed for distribution under the GPL version 2, check COPYING for details
# Some of this code is directly lifted from Twisted's jabber.component code.

# Most of this is taken directly from a patch by Tofu, available at:
# http://twistedmatrix.com/bugs/issue1046
# This will go away when Twisted has real SASL support.  (yay!)
# Kinda hacky at the moment.  Fair warning.

# This does -not- work with > Twisted 2.2.0.

TLS_XMLNS = 'urn:ietf:params:xml:ns:xmpp-tls'
SASL_XMLNS = 'urn:ietf:params:xml:ns:xmpp-sasl'
BIND_XMLNS = 'urn:ietf:params:xml:ns:xmpp-bind'
SESSION_XMLNS = 'urn:ietf:params:xml:ns:xmpp-session'
STREAMS_XMLNS  = 'urn:ietf:params:xml:ns:xmpp-streams'

import random, time, os, md5, binascii
try:
	from OpenSSL import SSL
except ImportError:
	SSL = None

from twisted.words.xish.domish import Element, elementStream
from twisted.words.protocols.jabber import component, jstrports, client, xmlstream
from twisted.application import service

class SASLXmlStream(xmlstream.XmlStream):
    def _reset(self):
        self.stream = elementStream()
        self.stream.DocumentStartEvent = self.onDocumentStart
        self.stream.ElementEvent = self.onElement
        self.stream.DocumentEndEvent = self.onDocumentEnd

    def onDocumentStart(self, rootelem):
        if rootelem.hasAttribute("version"):
            self.version = rootelem["version"] # Extract version

        xmlstream.XmlStream.onDocumentStart(self, rootelem)

class SASLXmlStreamFactory(xmlstream.XmlStreamFactory):
    def buildProtocol(self, _):
        self.resetDelay()
        # Create the stream and register all the bootstrap observers
        xs = SASLXmlStream(self.authenticator)
        xs.factory = self
        for event, fn in self.bootstraps: xs.addObserver(event, fn)
        return xs

def SASLcomponentFactory(componentid, username, password):
	a = ConnectSASLComponentAuthenticator(componentid, username, password)
	return SASLXmlStreamFactory(a)

class SASLConnectAuthenticator(xmlstream.Authenticator):
    def connectionMade(self):
        # Generate stream header
        if self.version != 0.0:
            sh = "<stream:stream xmlns='%s' xmlns:stream='http://etherx.jabber.org/streams' version='%s' to='%s'>" % \
                 (self.namespace, self.version, self.streamHost.encode('utf-8'))
        else:
            sh = "<stream:stream xmlns='%s' xmlns:stream='http://etherx.jabber.org/streams' to='%s'>" % \
                 (self.namespace, self.streamHost)
        self.xmlstream.send(sh)

class SASLConnectComponentAuthenticator(SASLConnectAuthenticator):
    """ Authenticator to permit an XmlStream to authenticate against a Jabber
    Server as a Component (where the Authenticator is initiating the stream).

    This implements the basic component authentication. Unfortunately this
    protocol is not formally described anywhere. Fortunately, all the Jabber
    servers I know of use this mechanism in exactly the same way.

    """
    namespace = 'jabber:component:accept'

    def __init__(self, componentjid, username, password):
        """
        @type componentjid: C{str}
        @param componentjid: Jabber ID that this component wishes to bind to.

        @type username: C{str}
        @param username: Username that this component uses to authenticate.

        @type password: C{str}
        @param password: Password/secret this component uses to authenticate.
        """
        SASLConnectAuthenticator.__init__(self, componentjid)
        self.username = username
        self.password = password

    def streamStarted(self, rootelem):
        # Create handshake
        hs = Element(("jabber:component:accept", "handshake"))
        hs.addContent(xmlstream.hashPassword(self.xmlstream.sid, self.password))

        # Setup observer to watch for handshake result
        self.xmlstream.addOnetimeObserver("/handshake", self._handshakeEvent)
        self.xmlstream.send(hs)

    def _handshakeEvent(self, elem):
        self.xmlstream.dispatch(self.xmlstream, xmlstream.STREAM_AUTHD_EVENT)

class ConnectSASLComponentAuthenticator(SASLConnectComponentAuthenticator):
	"""
	Wrapper for Twisted's component authenticator that handles SASL
	"""
	namespace = "http://jabberd.jabberstudio.org/ns/component/1.0"
	version = '1.0'
	INVALID_USER_EVENT    = "//event/client/basicauth/invaliduser"
	AUTH_FAILED_EVENT     = "//event/client/basicauth/authfailed"
	REGISTER_FAILED_EVENT = "//event/client/basicauth/registerfailed"

	def __init__(self, componentjid, username, password):
		"""
		@type componentjid: C{str}
		@param componentjid: Jabber ID that this component wishes to bind to.

		@type username: C{str}
		@param username: Username this component uses to authenticate.

		@type password: C{str}
		@param password: Password/secret this component uses to authenticate.
		"""
		SASLConnectAuthenticator.__init__(self, componentjid)
		self.jid = componentjid
		self.username = username
		self.password = password
		self.success = 0
		self.tls = 0

	def streamStarted(self, rootelem):
		if self.version != 0.0 and rootelem.hasAttribute('version'):
			major,minor = self.version.split('.')
			smajor,sminor = self.xmlstream.version.split('.')
			if int(smajor) >= int(major):
				# check features
				self.xmlstream.addOnetimeObserver("/features",self._featureParse)
			elif int(smajor) < int(major):
				self.sendError('unsupported-version')
		else:
			# Hrm, no chance of SASL
			self.sendHandshake()

	def sendError(self, error, text = None):
		# TODO - make this an domish element?
		sh = "<stream:error>"
		# TODO - check for valid error types
		sh = sh + "<%s xmlns='%s' />" % (error, STREAMS_XMLNS)
		if text:
			sh = sh + "<text>"+text+"</text>"
		sh = sh + "</stream:error>"    
		self.xmlstream.send(sh)

	def _featureParse(self, f):
		self.bind = 0
		self.session = 0
		# TODO - check for tls
		if self.success == 1:
			for f in f.elements():
				if f.name == "bind":
					self.bind = 1
				if f.name == "session":
					self.session = 1

			if self.bind:
				iq = client.IQ(self.xmlstream, "set")
				iq.addElement((BIND_XMLNS, "bind"))

				iq.bind.addElement("resource", content = self.jid)
				iq.addCallback(self._bindResultEvent)
				iq.send()
		else:
			if f.starttls:
				if SSL:
					# look for required
					#starttls = Element((TLS_XMLNS,"starttls"),TLS_XMLNS)
					starttls = Element((None,"starttls"))
					# why? --- should not be here!!!!!
					starttls['xmlns'] = TLS_XMLNS
					self.xmlstream.addOnetimeObserver("/proceed",self._proceed)
					self.xmlstream.addOnetimeObserver("/failue",self._tlsError)
					self.xmlstream.send(starttls)
				else:
					self.xmlstream.dispatch(f, self.AUTH_FAILED_EVENT)
			else:
				# Look for SASL
				m = f.mechanisms

				if m.uri == SASL_XMLNS:
					ms = 'DIGEST-MD5'
					for mech in m.elements():
						ms = str(mech)
						if ms == 'DIGEST-MD5':
							break
						if ms == 'PLAIN':
							break
					#auth = Element((SASL_XMLNS,"auth"),SASL_XMLNS,{'mechanism' : ms})
					auth = Element((None,"auth"),attribs = {'mechanism' : ms})
					# why?
					auth['xmlns'] = SASL_XMLNS
					# auth['mechanism'] = ms
					if ms == 'DIGEST-MD5':
						self.xmlstream.addOnetimeObserver("/challenge",self._saslStep1)
					if ms == 'PLAIN':
						# TODO add authzid
						auth_str = ""
						auth_str = auth_str + "\000"
						auth_str = auth_str + self.username.encode('utf-8')
						auth_str = auth_str + "\000"
						auth_str = auth_str + self.password.encode('utf-8')
						auth.addContent(binascii.b2a_base64(auth_str))
						self.xmlstream.addOnetimeObserver("/success",self._saslSuccess)

					self.xmlstream.addObserver("/failure",self._saslError)
					self.xmlstream.send(auth)
				else:
					self.xmlstream.dispatch(f, self.AUTH_FAILED_EVENT)
	
	# BIND stuff
	def _bindResultEvent(self, iq):
		if iq["type"] == "result":
			self.bind = 1
			if self.session == 1:
				iq = client.IQ(self.xmlstream, "set")
				iq.addElement((SESSION_XMLNS, "session"),content = self.jid)

				iq.addCallback(self._sessionResultEvent)
				iq.send()
				return

		else:
			self.bind = 0
			# TODO - make a BIND_FAILED_EVENT?
			self.xmlstream.dispatch(self.xmlstream, xmlstream.AUTH_FAILED_EVENT)            

		if self.bind == 1 and self.session == 1:                        
			self.xmlstream.dispatch(self.xmlstream, xmlstream.STREAM_AUTHD_EVENT)            
		else:
			self.xmlstream.dispatch(iq, self.AUTH_FAILED_EVENT)


	# SASL stuff (should this be moved?)
	def _saslError(self, error):
		self.xmlstream.dispatch(error, self.AUTH_FAILED_EVENT)

	def _saslStep1(self, challenge):
		c = str(challenge)

		dc = binascii.a2b_base64(c)
		ra = self._parse(dc)
		self.realm = ra['realm']
		self.nonce = ra['nonce']
		self.nc=0
		self.charset = ra['charset']
		self.algorithm = ra['algorithm']
		#response = Element((SASL_XMLNS,"response"))
		response = Element((None,"response"))
		# why?
		response['xmlns'] = SASL_XMLNS
		r = self._response(self.charset,self.realm,self.nonce)

		response.addContent(r)
		self.xmlstream.removeObserver("/challenge",self._saslStep1)
		self.xmlstream.addOnetimeObserver("/challenge",self._saslStep2)
		self.xmlstream.send(response)

	def _saslStep2(self, challenge):
		cs = binascii.a2b_base64(str(challenge))
		ca = self._parse(cs)

		if self.rauth == ca['rspauth']:
			#response = Element((SASL_XMLNS,"response"))
			response = Element((None,"response"))
			# why?
			response['xmlns'] = SASL_XMLNS

			self.xmlstream.removeObserver("/challenge",self._saslStep2)
			self.xmlstream.addOnetimeObserver("/success",self._saslSuccess)
			self.xmlstream.send(response)
		else:
			self.xmlstream.dispatch(challenge, self.AUTH_FAILED_EVENT)

	def _saslSuccess(self, s):
		self.success = 1
		self.xmlstream._reset()
		self.connectionMade()
		self.xmlstream.dispatch(self.xmlstream, xmlstream.STREAM_AUTHD_EVENT)            

	# TLS stuff  - maybe put this in its own class?
	def _proceed(self, p):
		from twisted.internet import ssl
		# Reconnect using SSL
		ctx = ssl.ClientContextFactory()
		self.xmlstream.transport.startTLS(ctx)
		self.xmlstream._reset()
		# Generate stream header
		if self.version != 0.0:
			sh = "<stream:stream xmlns='%s' xmlns:stream='http://etherx.jabber.org/streams' version='%s' to='%s'>" % \
				(self.namespace,self.version, self.streamHost.encode('utf-8'))
		else:
			sh = "<stream:stream xmlns='%s' xmlns:stream='http://etherx.jabber.org/streams' to='%s'>" % \
				(self.namespace, self.streamHost.encode('utf-8'))
		self.xmlstream.send(sh)
		self.tls = 1

	def _tlsError(self, e):
		self.xmlstream.dispatch(e, self.AUTH_FAILED_EVENT)

	# SASL stuff - maybe put this in its own class?
	def _response(self, charset, realm, nonce):
		rs = ''
		try:
			#username=self.jid.encode(charset)
			username=self.username.encode(charset)
		except UnicodeError:
			# TODO - add error checking 
			raise
		rs = rs + 'username="%s"' % username
		rs = rs + ',realm="%s"' % realm
		cnonce = self._gen_nonce()
		rs = rs + ',cnonce="%s"' % cnonce
		rs = rs + ',nonce="%s"' % nonce

		self.nc+=1
		nc="%08x" % self.nc
		rs = rs + ',nc=%s' % nc
		rs = rs + ',qop=auth'

		rs = rs + ',digest-uri="xmpp/'+self.jid.encode(charset)+'"'

		uh = "%s:%s:%s" % (username,realm,self.password.encode(charset))
		huh = md5.new(uh).digest()
		# TODO - add authzid
		a1 = "%s:%s:%s" % (huh,nonce,cnonce)
		a2="AUTHENTICATE:xmpp/"+self.jid.encode(charset)

		a3=":xmpp/"+self.jid.encode(charset)

		resp1 = "%s:%s:%s:%s:%s:%s" % (binascii.b2a_hex(md5.new(a1).digest()),
			nonce,
			nc,
			cnonce,
			"auth",
			binascii.b2a_hex(md5.new(a2).digest()))

		resp2 = "%s:%s:%s:%s:%s:%s" % (binascii.b2a_hex(md5.new(a1).digest()),
			nonce,nc,cnonce,
			"auth",binascii.b2a_hex(md5.new(a3).digest()))

		kda1 = md5.new(resp1).digest()
		kda2 = md5.new(resp2).digest()

		response = binascii.b2a_hex(kda1) 

		rs = rs + ',response="%s"' % response
		rs = rs + ',charset=%s' % charset

		self.rauth = binascii.b2a_hex(kda2)

		return  binascii.b2a_base64(rs)

	def _parse(self, rcs):
		r = rcs.split(',')
		h = {}
		for i in r:
			(k,v) = i.split('=')
			v = v.replace("'","")
			v = v.replace('"','')
			if h.has_key(k):
				# return an error
				return 0
			h[k] = v
		return h

	def _gen_nonce(self):
		return md5.new("%s:%s:%s" % (str(random.random()) , str(time.gmtime()),str(os.getpid()))).hexdigest()

	def sendHandshake(self):
		# Create handshake
		hs = Element(("jabber:component:accept", "handshake"))
		hs.addContent(xmlstream.hashPassword(self.xmlstream.sid, self.password))

		# Setup observer to watch for handshake result
		self.xmlstream.addOnetimeObserver("/handshake", self._handshakeEvent)
		self.xmlstream.send(hs)

	def _handshakeEvent(self, elem):
		self.xmlstream.dispatch(self.xmlstream, xmlstream.STREAM_AUTHD_EVENT)

class SASLServiceManager(component.ServiceManager):
	"""
	Wrapper around Twisted's ServiceManager that supports SASL.
	"""
	def __init__(self, jid, username, password):
		service.MultiService.__init__(self)

		# Setup defaults
		self.jabberId = jid
		self.xmlstream = None

		# Internal buffer of packets
		self._packetQueue = []

		# Setup the xmlstream factory
		self._xsFactory = SASLcomponentFactory(self.jabberId, username, password)

		# Register some lambda functions to keep the self.xmlstream var up to date
		self._xsFactory.addBootstrap(xmlstream.STREAM_CONNECTED_EVENT, self._connected)
		self._xsFactory.addBootstrap(xmlstream.STREAM_AUTHD_EVENT, self._authd)
		self._xsFactory.addBootstrap(xmlstream.STREAM_END_EVENT, self._disconnected)

		# Map addBootstrap and removeBootstrap to the underlying factory -- is this
		# right? I have no clue...but it'll work for now, until i can think about it
		# more.
		self.addBootstrap = self._xsFactory.addBootstrap
		self.removeBootstrap = self._xsFactory.removeBootstrap


def buildServiceManager(jid, username, password, strport):
	"""
	Constructs a pre-built C{SASLServiceManager}, using the specified strport string.    
	"""
	svc = SASLServiceManager(jid, username, password)
	client_svc = jstrports.client(strport, svc.getFactory())
	client_svc.setServiceParent(svc)
	return svc
