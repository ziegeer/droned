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

from twisted.internet import task
from droned.models.conversation import Conversation, ChatRoom
from droned.models.environment import env
from droned.models.event import Event
from droned.models.team import Team
from droned.models.server import Server
from droned.errors import ServiceNotAvailable
import services
import config

try:
   jabber = services.getService('jabber')
   jconfig = jabber.SERVICECONFIG
except ServiceNotAvailable:
   jabber = None
   jconfig = None

def notify_online(event):
    ready = env.ready
    for agent in Team('support').agents:
        agent.tell("%s droned reporting for duty." % config.ROMEO_ENV_NAME)
        if not ready:
            agent.tell("The environment is still being scanned, please wait...")

    def check():
        if env.ready:
            for agent in Team('support').agents:
                agent.tell("The environment is fully scanned and ready.")
            if checker.running:
                checker.stop()

    checker = task.LoopingCall(check)
    checker.start(1.0)


def remove_conversation_subscriptions(event):
    for conversation in Conversation.objects:
        for event in Event.objects:
            event.unsubscribe(conversation.notify)


def joinEnvironmentalChatRoom(event):
    """determine if we should join a chatroom"""
    chat = ChatRoom(config.ROMEO_ENV_NAME)
    #make sure the drone can be managed by the room
    username = config.ROMEO_ENV_NAME
    jbserver = jconfig.JABBER_CHAT_SERVICE
    jid = "%(username)s@%(jbserver)s" % locals()
    Team('support').addMember(jid)
    #get the conversation context set to some sane defaults
    conversation = Conversation(jid)
    #grant the room access to the server
    if jconfig.JABBER_TRUST_ROOM:
        conversation.grantAuthorization(notify=False)
    #be vain assume all conversations revolve around ourself
    context = {
        'server': Server(config.HOSTNAME),
        'subject': Server(config.HOSTNAME),
    }
    conversation.context.update(context)
    #finally join the room
    chat.join()

if jconfig and jconfig.JABBER_JOIN_CHATROOM:
   Event('jabber-online').subscribe(joinEnvironmentalChatRoom)
Event('jabber-online').subscribe(notify_online)
Event('jabber-offline').subscribe(remove_conversation_subscriptions)
