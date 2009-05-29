# -*- coding: utf-8 -*-
# Licensed for distribution under the GPL version 2, check COPYING for details

from twisted.application import service
from twisted.words.protocols.jabber import sasl, xmlstream, component, jstrports
from twisted.words.protocols.jabber.jid import internJID

def componentFactory(jid, password):
    """
    XML stream factory with SASL support
    """
    a = ConnectComponentAuthenticator(jid, password)
    return xmlstream.XmlStreamFactory(a)

class ConnectComponentAuthenticator(xmlstream.ConnectAuthenticator):
    """
    ConnectComponentAuthenticator with SASL support
    """
    namespace = component.NS_COMPONENT_ACCEPT

    def __init__(self, jid, password):
        xmlstream.ConnectAuthenticator.__init__(self, jid.host)
	self.jid = jid
        self.password = password

    def associateWithStream(self, xs):
        xmlstream.ConnectAuthenticator.associateWithStream(self, xs)
        xs.initializers = [sasl.SASLInitiatingInitializer(xs)]

class ServiceManager(component.ServiceManager):
    """
    Service manager with SASL support (most taken from Twisted)
    """

    def __init__(self, jid, password):
        service.MultiService.__init__(self)

        # Setup defaults
        self.jabberId = jid
        self.xmlstream = None

        # Internal buffer of packets
        self._packetQueue = []

        # Setup the xmlstream factory
        self._xsFactory = componentFactory(self.jabberId, password)

        # Register some lambda functions to keep the self.xmlstream var up to
        # date
        self._xsFactory.addBootstrap(xmlstream.STREAM_CONNECTED_EVENT,
                                     self._connected)
        self._xsFactory.addBootstrap(xmlstream.STREAM_AUTHD_EVENT, self._authd)
        self._xsFactory.addBootstrap(xmlstream.STREAM_END_EVENT,
                                     self._disconnected)

        # Map addBootstrap and removeBootstrap to the underlying factory -- is
        # this right? I have no clue...but it'll work for now, until i can
        # think about it more.
        self.addBootstrap = self._xsFactory.addBootstrap
        self.removeBootstrap = self._xsFactory.removeBootstrap

def buildServiceManager(host, username, password, strport):
    """
    Constructs a ServiceManager
    """

    jid = internJID(username+'@'+host)
    svc = ServiceManager(jid, password)
    client_svc = jstrports.client(strport, svc.getFactory())
    client_svc.setServiceParent(svc)
    return svc
