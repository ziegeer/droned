###############################################################################
#   Copyright 2006 to the present, Orbitz Worldwide, LLC.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
###############################################################################

from kitt.interfaces import implements, IDroneDService
__doc__ = """The Jabber Service provides an interface to control DroneD through
the Jabber Protocol.  This service is implemented as a class using the 
IDroneDService interface"""

from twisted.python.failure import Failure
from twisted.application.internet import TCPClient
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.words.protocols.jabber.client import XMPPClientFactory
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.sasl import SASLAuthError
from twisted.words.protocols.jabber.xmlstream import *
from twisted.words.xish.domish import Element, elementStream
from droned.logging import logWithContext, err

import config
import os

from kitt.util import dictwrapper

# Hack to make SSL work, required for most jabber servers
from OpenSSL.SSL import SSLv23_METHOD
from twisted.internet.ssl import CertificateOptions
CertificateOptions.method = SSLv23_METHOD


#python2.4 hack 'http://docs.python.org/library/functions.html#all'
try: any
except NameError:
    from kitt.util import any

class JabberClient(object):
    implements(IDroneDService) #requirement
    xmlstream = None
    connected = property( lambda self: self.xmlstream is not None )

    parentService = None #interface required attribute
    service = None #interface required attribute
    SERVICENAME = 'jabber' #interface required attribute

    #this should be overrode in romeo
    SERVICECONFIG = dictwrapper({
        'JABBER_CHAT_NICK': config.HOSTNAME,
        'JABBER_USERNAME': 'droned',
        'JABBER_PASSWORD': 'secret',
        'JABBER_SERVER': 'jabber.example.net',
        'JABBER_CHAT_SERVICE': 'conference.jabber.example.net',
        'JABBER_PORT': 5222,
        'JABBER_RESOURCE': config.HOSTNAME,
        'JABBER_BROADCAST_INTERVAL': 300, 
        'JABBER_VALIDATE_XML': True,
        'JABBER_TRUST_ROOM': False,
        'DEPUTY': 'admin@jabber.example.net',
        'JABBER_TEAM_ROSTER': '/var/lib/droned/teams',
        'CONVERSATION_RESPONSE_PERIOD': 180,
        'JABBER_JOIN_CHATROOM': False,
        'JABBER_TEAM_ROSTER': os.path.join(config.DRONED_HOMEDIR, 'teams'),
    }) #interface required attribute

    def running(self):
        """interface requirement"""
        return bool(self.service) and self.service.running

    def install(self, _parentService):
        """interface requirement"""
        self.parentService = _parentService
        user = self.SERVICECONFIG.JABBER_USERNAME
        server = self.SERVICECONFIG.JABBER_SERVER
        resource = self.SERVICECONFIG.JABBER_RESOURCE
        self.jid = JID("%(user)s@%(server)s/%(resource)s" % locals())
        self.broadcastTask = LoopingCall(self.broadcastPresence)
        self.sendQueue = []
        self.authenticated = False
        #load all jabber responders, after configuration
        import droned.responders
        droned.responders.loadAll()

    def start(self):
        """interface requirement"""
        if self.running(): return
        self.factory = XMPPClientFactory(self.jid, self.SERVICECONFIG.JABBER_PASSWORD)
        self.factory.addBootstrap(STREAM_CONNECTED_EVENT, self.connectionMade)
        self.factory.addBootstrap(STREAM_END_EVENT, self.connectionLost)
        self.factory.addBootstrap(STREAM_AUTHD_EVENT, self.connectionAuthenticated)
        self.factory.addBootstrap(STREAM_ERROR_EVENT, self.receivedError)
        self.factory.addBootstrap(INIT_FAILED_EVENT, self.initFailed)
        self.service = TCPClient(
            self.SERVICECONFIG.JABBER_SERVER,
            self.SERVICECONFIG.JABBER_PORT,
            self.factory
        )
        self.service.setServiceParent(self.parentService)
        #build/rebuild jabber teams 
        for name in os.listdir(self.SERVICECONFIG.JABBER_TEAM_ROSTER):
            f = (self.SERVICECONFIG.JABBER_TEAM_ROSTER,name)
            if os.path.isfile('%s/%s' % f):
                Team(name) #preload team rosters

    def stop(self):
        """interface requirement"""
        if self.service:
            self.factory.stopTrying()
            self.factory.stopFactory()
            self.service.disownServiceParent()
            self.service.stopService()
            self.service = None

    def connectionMade(self, xmlstream):
        log('connection made')
        self.xmlstream = xmlstream

    def connectionLost(self, xmlstream):
        log('connection lost')
        self.authenticated = False
        if self.broadcastTask.running:
            self.broadcastTask.stop()
        if self.connected:
            Event('jabber-offline').fire()
        self.xmlstream = None

    def connectionAuthenticated(self, xmlstream):
        log('connection authenticated')
        self.authenticated = True
        if not self.broadcastTask.running:
            self.broadcastTask.start(self.SERVICECONFIG.JABBER_BROADCAST_INTERVAL)
  
        xmlstream.addObserver('/message', self.receivedMessage)
        xmlstream.addObserver('/presence', self.receivedPresence)
        xmlstream.addObserver('/iq', self.receivedIQ)
        xmlstream.addObserver('/error', self.receivedError)
        Event('jabber-online').fire()
        while self.sendQueue:
            self.xmlstream.send( self.sendQueue.pop(0) )

    def broadcastPresence(self):
        presence = Element( ('jabber:client','presence') )
        #log('sending presence broadcast')
        self.xmlstream.send(presence)

    def sendMessage(self, to, body, useHTML=True, groupChat=False):
        message = Element( ('jabber:client','message') )
        message['to'] = to
        message['type'] = (groupChat and 'groupchat') or 'chat'
        message.addElement('body', None, body)
        if useHTML:
            html = message.addElement('html', 'http://jabber.org/protocol/xhtml-im')
            htmlBody = html.addElement('body', 'http://www.w3.org/1999/xhtml')
            htmlBody.addRawXml( unicode(body) )
            if self.SERVICECONFIG.JABBER_VALIDATE_XML:
                validateXml( html.toXml() )
        #safeXml = filter(lambda char: ord(char) < 128, message.toXml())
        #log('sending message: %s' % safeXml)
        log('sending message to %s: %s' % (to, body))
        if self.authenticated:
            self.xmlstream.send(message)
        else:
            log("not connected, queueing message", warning=True)
            self.sendQueue.append(message)

    def requestAuthorization(self, to):
        request = Element( (None,'iq') )
        request['type'] = 'set'
        request['id'] = 'auth-request:%s' % to
        query = Element( (None,'query') )
        query['xmlns'] = 'jabber:iq:roster'
        item = Element( (None,'item') )
        item['jid'] = to
        item['name'] = to.split('@')[0]
        query.addChild(item)
        request.addChild(query)
        log('sending auth request: %s' % request.toXml())
        self.xmlstream.send(request)

    def joinChatRoom(self, room):
        presence = Element( (None,'presence') )
        presence['from'] = self.jid.userhost()
        jid = '%s@%s/%s' % (room,self.SERVICECONFIG.JABBER_CHAT_SERVICE,self.SERVICECONFIG.JABBER_CHAT_NICK)
        presence['to'] = jid
        x = Element( ('http://jabber.org/protocol/muc','x') )
        history = Element( (None,'history') )
        history['maxchars'] = '0'
        x.addChild(history)
        presence.addChild(x)
        log('sending join: %s' % presence.toXml())
        self.xmlstream.send(presence)

    def leaveChatRoom(self, jid):
        if '/' not in jid:
            jid += '/' + self.SERVICECONFIG.JABBER_CHAT_NICK
        presence = Element( (None,'presence') )
        presence['from'] = self.jid.userhost()
        presence['to'] = jid
        presence['type'] = 'unavailable'
        log('sending leave: %s' % presence.toXml())
        self.xmlstream.send(presence)

    def receivedMessage(self, e):
        # Extract the body of the message
        try:
            message = str([c for c in e.children if c.name == 'body'][0])
        except:
            log('discarding invalid message (has no body!): %s' % e.toXml())
            return
        # Discard delayed messages
        delays = [ x for x in e.children if x.name == 'delay' ]
        stamps = [ x for x in e.children \
               if x.name == 'x' and \
               x.compareAttribute('xmlns','jabber:x:delay') and \
               x.hasAttribute('stamp') ]
        #stampstring = str( stamps[0].getAttribute('stamp') )
        #timestamp = time.mktime( time.strptime(stampstring, "%Y%m%dT%H:%M:%S") )
        if delays or stamps:
            log('discarding delayed message: %s' % e.toXml())
            return

        # Route message to the right Conversation or ChatRoom entity
        if e.getAttribute('type') == 'chat':
            buddy = str( e['from'].split('/')[0] )
            if not Conversation.exists(buddy):
                self.requestAuthorization(buddy)
            log('received message from %s: %s' % (buddy.split('@')[0], message))
            Conversation(buddy).hear(message)
        elif e.getAttribute('type') == 'groupchat':
            room = e['from'].split('@')[0]
            log('received message [chatroom=%s]: %s' % (room, message))
            ChatRoom(room).hear(message)
        else:
            log('received message of unknown type: %s' % e.toXml(), error=True)

    def receivedPresence(self, e):
        log('received presence: %s' % e.toXml())
        if e.getAttribute('type') == 'subscribe':
            log('received authorization request from %s' % e['from'])
            response = Element( ('','presence') )
            response['to'] = e['from']
            response['type'] = 'subscribed'
            log('sending auth response: %s' % response.toXml())
            self.xmlstream.send(response)
            buddy = str(e['from'])
            if not Conversation.exists(buddy):
                self.requestAuthorization(buddy)
        elif e.getAttribute('type') == 'unavailable':
            #fix for openfire jabber server randomly kicking clients out and prevent kicks
            CHAT = '@%s/%s' % (self.SERVICECONFIG.JABBER_CHAT_SERVICE,self.SERVICECONFIG.JABBER_CHAT_NICK)
            if e['to'] == self.jid.full() and e['from'].endswith(CHAT) and \
                    "status code='307'" in e.toXml():
                try:
                    log('%s has kicked me' % (e['from'],))
                    self.joinChatRoom(e['from'].split(CHAT)[0])
                    log('successfully rejoined room')
                except:
                    err('Failed to recover from /kick')
            #elif any(1 for c in e.children if c.name == 'x'):
            #TODO detect buddies that go offline
            #    if we have a Conversation then unsubscribe .notify from all events

    def receivedIQ(self, e):
        log('received iq: %s' % e.toXml())

    def receivedError(self, f):
        log('received error: %s' % str(f))

    def initFailed(self, failure):
        log('Failed to initialize jabber connection:\n%s' % failure.getTraceback())
        self.stop()
        if failure.check(SASLAuthError):
            log('Will attempt to reconnect in 15 seconds...')
            reactor.callLater(15, self.start)
#setup logging after class definition
log = logWithContext(type=JabberClient.SERVICENAME)

def validateXml(xml):
    stream = elementStream()
    stream.DocumentStartEvent = lambda e: None
    stream.ElementEvent = lambda e: None
    stream.DocumentEndEvent = lambda: None
    stream.parse(xml) #will throw a ParserError if xml is not well-formed


# Avoid import circularity
from droned.models.conversation import Conversation, ChatRoom
from droned.models.event import Event
from droned.models.team import Team
