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

from zope.interface import Interface, Attribute

class IDroneModelConversation(Interface):
    """I provide a Model to Track Jabber Conversations"""
    buddy = Attribute("C{str} JID")
    buddyName = Attribute("C{str} Shortname of the JID")
    deferredAnswer = Attribute("L{twisted.internet.defer.Deferred}")
    expectedAnswers = Attribute("C{tuple} of C{str}")
    askingQuestion = Attribute("C{bool}")
    groupChat = Attribute("C{bool}")
    authorized = Attribute("C{bool}")
    idleTime = Attribute("C{float}")
    responsive = Attribute("C{bool}")
    online = Attribute("C{bool}")
    context = Attribute("L{IConversationContext}")

    def say(message, **options):
        """say something to a remote party

           @param message C{str}
        """

    def hear(message):
        """hear a particular message from a remote party

           @param message C{str}
        """

    def ask(question, answers):
        """Sends a message and returns a Deferred that fires 
           whenever one of the given answers is received.

           @param question C{str}
           @param answers C{tuple} containing at least one C{str}

           @return L{twisted.internet.defer.Deferred}
        """

    def nevermind():
        """forget the context of the conversation"""

    def grantAuthorization(self, notify):
        """method to allow this conversation extra priviledges.

           @param notify C{bool} whether to notify the asking party
        """

    def revokeAuthorization(self, notify):
        """method to deny this conversation extra priviledges.

           @param notify C{bool} whether to notify the asking party
        """

    def sendNotifications(self):
        """Formats and sends notification to the remote party"""


class IDroneModelChatRoom(Interface):
    """I provide a model of chatroom actions."""
    room = Attribute("C{str}")
    jid = Attribute("C{str}")
    nick = Attribute("C{str}")
    conversation = Attribute("L{IDroneModelConversation} provider")

    def join():
        """join the chatroom"""

    def leave():
        """leave the chat room"""

    def hear():
        """Only pay attention to messages that start with my chat nick"""

#FIXME this may change
class IDroneModelTeam(Interface):
    """I model a jabber team."""
    availableAgents = Attribute("C{generator}")
    available = Attribute("C{bool}")
    busy = Attribute("C{bool}")
    rosterPath = Attribute("C{str}")
    pendingIssues = Attribute("C{generator}")
    agents = Attribute("C{set}")
    name = Attribute("C{str}")

    def loadRoster():
        """load the jabber roster from disk"""

    def saveRoster():
        """commit the jabber roster to disk"""

    def addMember(jid):
        """add a JID to the roster.

           @param jid C{str}
        """

    def removeMember(jid):
        """remove a JID to the roster.

           @param jid C{str}
        """

    def workNextIssue():
        """FIXME"""

    def notify(message):
        """sent a message to all the team members

           @param message C{str}
        """
#TODO droned.models.team.SupportAgent


__all__ = [
    'IDroneModelChatRoom',
    'IDroneModelConversation'
]
