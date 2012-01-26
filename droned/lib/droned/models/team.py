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

import os
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.task import LoopingCall
from droned.entity import Entity
from droned.logging import log
from droned.errors import ServiceNotAvailable
import services

#TODO bring inline with style guide
#FIXME some of this doesn't make sense

try: any #python2.4 test
except NameError:
    from kitt.util import any

class Team(Entity):
  jabber_service = property(lambda s: services.getService('jabber'))
  jabber_config = property(lambda s: s.jabber_service.SERVICECONFIG)
  availableAgents = property(lambda s: (agent for agent in s.agents if agent.available))
  available = property(lambda self: any(self.availableAgents))
  busy = property(lambda s: not s.available)
  rosterPath = property(lambda s: '%s/%s' % (s.jabber_config.JABBER_TEAM_ROSTER, s.name))
  pendingIssues = property(lambda s: \
        (i for i in Issue.objects if not i.resolved and i.assignedTo == s))

  def __init__(self, name):
    self.name = name
    self.agents = set()
    self.worker = LoopingCall(self.workNextIssue)
    self.worker.start(5)
    self.loadRoster()

  def __getstate__(self):
    return {
      'name' : self.name,
      'members' : set(agent.jid for agent in self.agents),
    }

  @staticmethod
  def construct(state):
    team = Team(state['name'])
    team.agents = set( SupportAgent(jid) for jid in state['members'] )
    return team

  def loadRoster(self):
    if not os.path.exists(self.rosterPath):
      log('no roster exists for the %s team, so it has no members!' % self.name, warning=True)
      return
    for line in open(self.rosterPath):
      line = line.strip()
      if not line or line.startswith('#'): continue
      jid = line
      agent = SupportAgent(jid)
      self.agents.add(agent)

  def saveRoster(self):
    jids = [agent.jid for agent in self.agents]
    content = '\n'.join(jids) + '\n'
    def blockingWrite():
      roster = open(self.rosterPath, 'w')
      roster.write(content)
      roster.close()
    reactor.callInThread(blockingWrite)

  def addMember(self, jid):
    self.agents.add( SupportAgent(jid) )
    self.saveRoster()

  def removeMember(self, jid):
    self.agents.discard( SupportAgent(jid) )
    self.saveRoster()

  def workNextIssue(self):
    while any(self.availableAgents) and any(self.pendingIssues):
      issue = self.pendingIssues.next()
      agent = self.availableAgents.next()
      agent.engage(issue)
      issue.whenResolved(lambda result: self.workNextIssue() or result)

  def notify(self, message):
    for agent in self.agents:
      agent.tell("<b>%s team notification:</b> %s" % (self.name, message))


class SupportAgent(Entity):
  ready = True
  sop = None
  currentIssue = None
  issues = property(lambda self: (i for i in Issue.objects if not i.resolved and i.assignedTo == self))
  online = property(lambda self: self.conversation.online)
  available = property(lambda self: self.online and self.ready and self.currentIssue is None and not self.conversation.askingQuestion)
  busy = property(lambda self: not self.available)
  teams = property(lambda self: (team for team in Team.objects if self in team.agents))
  name = property(lambda self: self.conversation.buddyName)
  responsive = property(lambda self: self.conversation.responsive)

  def __init__(self, jid):
    self.jid = jid
    self.conversation = Conversation(jid)

  def __getstate__(self):
    return {
      'jid' : self.jid,
      'ready' : self.ready
    }

  @staticmethod
  def construct(state):
    agent = SupportAgent( state['jid'] )
    agent.ready = state['ready']
    return agent

  def tell(self, message, **kwargs):
    self.conversation.say(message, **kwargs)

  def ask(self, question, answers, **kwargs):
    return self.conversation.ask(question, answers, **kwargs)

  def engage(self, issue):
    assert self.available
    self.currentIssue = issue
    issue.assignedTo = self
    issue.whenResolved(self.issueResolved)

  def issueResolved(self, issue):
    if issue != self.currentIssue: #got resolved by someone else
      return

    log("Agent %s resolved issue \"%s\" resolution=%s" % (self.name, issue.description, issue.resolution), type='issues')
    self.currentIssue = None
    self.sop = None

    if self.available and any(self.issues):
      self.engage( self.issues.next() )

    return issue


# Temporary Compatibility hack
TeamMember = SupportAgent


# Avoid import circularities
from droned.models.conversation import Conversation
from droned.models.issue import Issue
