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

import time
from twisted.python.failure import Failure
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.words.xish.domish import escapeToXml
from droned.entity import Entity
from droned.context import EntityContext
from droned.errors import ServiceNotAvailable
import services

from kitt.interfaces import IConversationContext, IDroneModelConversation,\
    IDroneModelChatRoom, implements

class Conversation(Entity):
    """model of a conversation"""
    implements(IDroneModelConversation)
    jabber = property(lambda s: services.getService('jabber'))
    jabber_config = property(lambda s: s.jabber.SERVICECONFIG)
    deferredAnswer = None
    expectedAnswers = ()
    askingQuestion = property(lambda s: s.deferredAnswer is not None)
    groupChat = False
    authorized = property(lambda s: \
            s._authorized or s.buddy == s.jabber_config.DEPUTY)
    _authorized = False
    idleTime = property(lambda s: time.time() - s.lastMessageReceived)
    responsive = property(lambda s: \
            s.idleTime < s.jabber_config.CONVERSATION_RESPONSE_PERIOD)
    online = True #TODO: need to safely track this state in Jabber service
    buddy = property(lambda s: s._buddy)
    buddyName = property(lambda s: s._buddyName)
    serializable = True

    def __init__(self, buddy):
        self._buddy = buddy
        self._buddyName = buddy.split('@')[0]
        self.notificationQueue = []
        self.lastMessageReceived = 0.0
        self.context = ConversationContext(self)

    def __getstate__(self):
        return {
            'buddy' : self.buddy,
            'authorized' : self.authorized,
            'subscriptions' : list(self.context.get('subscriptions',[]))
        }

    @staticmethod
    def construct(state):
        conversation = Conversation(state['buddy'])
        conversation.context['subscriptions'] = set( state['subscriptions'] )
        if state.get('authorized'):
            conversation.grantAuthorization(notify=False)
        for name in state['subscriptions']:
            Event(name).subscribe(conversation.notify)
        return conversation

    @staticmethod
    def byName(name):
        """Convenience method for looking up Conversation objects 
           by short or long names
        """
        for conversation in Conversation.objects:
            if conversation.buddy == name: #full jid
                return conversation
            elif conversation.buddyName == name: #short username
                return conversation

    def say(self, message, **options):
        "Send a message to the remote party"
        options['groupChat'] = self.groupChat
        self.jabber.sendMessage(self.buddy, message, **options)

    def hear(self, message):
        "Receive a message from the remote party"
        self.lastMessageReceived = time.time()

        for answer in self.expectedAnswers:
            if message == answer:
                d = self.deferredAnswer
                del self.expectedAnswers
            #Clear this before the callback in case it asks another question 
                del self.deferredAnswer
                d.callback(answer)
                return
        try:
            dispatch(self, message)
        except NoMatch:
            self.say("Sorry I don't know what you mean by that. Say <b>?</b> for help.")
        except:
            self.say(Failure().getTraceback(), useHTML=False)

    def ask(self, question, answers):
        """Sends a message and returns a Deferred that fires whenever one 
           of the given answers is received
        """
        if self.askingQuestion:
            raise AlreadyAskingQuestion(
                self.context['question'], 
                self.expectedAnswers
            )
        self.say(question)
        self.context['question'] = question
        self.context['expectedAnswers'] = answers
        self.deferredAnswer = Deferred()
        self.expectedAnswers = answers
        return self.deferredAnswer

    def nevermind(self):
        """forget the context of the conversation"""
        if self.askingQuestion:
            if 'question' in self.context:
                del self.context['question']
            if 'expectedAnswers' in self.context:
                del self.context['expectedAnswers']
            if hasattr(self, 'deferredAnswer'):
            # Probably best to just leave the deferred hanging
            #if not self.deferredAnswer.called: 
            #  self.deferredAnswer.callback(None)
                del self.deferredAnswer
            if hasattr(self, 'expectedAnswers'):
                del self.expectedAnswers

    def grantAuthorization(self, notify=True):
        """method to allow this conversation extra priviledges"""
        self._authorized = True
        self.context['authorized'] = True
        if not notify: return
        self.say("You have been granted authorization by the environment administrator.")

    def revokeAuthorization(self, notify=True):
        """method to deny this conversation extra priviledges"""
        self._authorized = False
        self.context['authorized'] = False
        self.nevermind()
        if not notify: return
        self.say("Your authorization has been revoked by the environment administrator.")

    def notify(self, event):
        """Tells the remote party that an event occurred"""
        self.notificationQueue.append(event)
        if len(self.notificationQueue) == 1:
            reactor.callLater(1, self.sendNotifications)

    def sendNotifications(self):
        """Formats and sends notification to the remote party"""
        message = ""
        for event in self.notificationQueue:
            params = ', '.join("%s=%s" % item for item in event.params.items())
            params = escapeToXml(params)
            message += "[<b>%s</b> occurred (%s)]<br/>" % (event.name, params)
        self.notificationQueue = []
        preStyle = '<font color="gray"><i>'
        postStyle = '</i></font>'
        self.say(preStyle + message + postStyle)


class ConversationContext(EntityContext):
    implements(IConversationContext)
    entityAttr = 'conversation'
    specialKeys = ['conversation', 'buddy', 'agent', 'issue', 'sop']

    def get_conversation(self):
        return self.conversation

    def get_buddy(self):
        return self.conversation.buddy

    def get_agent(self):
        if SupportAgent.exists(self.conversation.buddy):
            return SupportAgent(self.conversation.buddy)

    def get_issue(self):
        agent = self['agent']
        if agent:
            return agent.currentIssue

    def get_sop(self):
        agent = self['agent']
        if agent:
            return agent.sop


class ChatRoom(Entity):
    """models the actions needed to interact in a chatroom"""
    implements(IDroneModelChatRoom)
    jabber = property(lambda s: services.getService('jabber'))
    jabber_config = property(lambda s: s.jabber.SERVICECONFIG)
    room = property(lambda s: s._room)
    jid = property(lambda s: '%s@%s' % \
            (s.room, s.jabber_config.JABBER_CHAT_SERVICE))
    nick = property(lambda s: s.jabber_config.JABBER_CHAT_NICK)

    def __init__(self, room):
        self._room = room
        self.conversation = Conversation(self.jid)
        self.conversation.groupChat = True

    def join(self):
        """join the chat room"""
        self.jabber.joinChatRoom(self.room)

    def leave(self):
        """leave the chat room"""
        self.jabber.leaveChatRoom(self.jid)

    def hear(self, message):
        """Only pay attention to messages that start with my chat nick"""
        if message.lower().split()[0] == self.nick:
            message = message[len(self.nick):].strip()
            self.conversation.hear(message)


class AlreadyAskingQuestion(Exception):
    def __init__(self, question, answers):
        self.question = question
        self.answers = answers


#Avoid import circularities
from droned.models.event import Event
from droned.models.team import SupportAgent
from droned.responders import dispatch, NoMatch
