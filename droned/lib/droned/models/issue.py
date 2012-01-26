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
from twisted.internet.defer import Deferred
from droned.entity import Entity
from droned.context import EntityContext


class Issue(Entity):
  idCounter = 0
  resolved = property( lambda self: self.deferred.called )
  resolution = None
  assignedTo = None
  #serializable = True (not sure about this yet)

  def __init__(self, description):
    self.description = description
    self.context = IssueContext(self)
    self.deferred = Deferred()

    # Get the next unique Issue ID
    while Issue.byID( Issue.idCounter ):
      Issue.idCounter += 1
    self.id = Issue.idCounter
    Issue.idCounter += 1 #avoids duplicate id's caused by issues that go away quickly

  def __getstate__(self):
    return {
      'description' : self.description,
      'context' : self.context.data
    }

  @staticmethod
  def construct(state):
    return Issue( state['description'] ).withContext( state['context'] )

  @staticmethod
  def byID(id):
    for issue in Issue.objects:
      if hasattr(issue,'id'): # self won't have an id during __init__
        if issue.id == id:
          return issue

  def withContext(self, context):
    self.context.update(context)
    return self

  def whenResolved(self, callback):
    self.deferred.addCallback(callback)
    return self

  def resolve(self, resolution=None):
    if self.resolved:
      return
    else:
      Issue.delete(self)
      self.resolution = resolution
      self.deferred.callback(self)

  def assign(self, who):
    if isinstance(who, str):
      if Team.exists(who):
        who = Team(who)
      elif Conversation.byName(who): #byName handles short usernames as well as full JIDs
        who = SupportAgent( Conversation.byName(who).buddy )
      else:
        raise ValueError("I don't know any teams or people named \"%s\"" % who)

    if not isinstance(who, (Team,SupportAgent)):
      raise TypeError("You can only assign issues to Teams or SupportAgents")

    self.assignedTo = who

    if isinstance(who, SupportAgent) and who.available:
      who.engage(self)


class IssueContext(EntityContext):
  entityAttr = 'issue'
  specialKeys = ['issue', 'assignedTo', 'agent', 'conversation', 'sop']

  def get_issue(self):
    return self.issue

  def get_assignedTo(self):
    return self.issue.assignedTo

  def get_agent(self):
    for agent in SupportAgent.objects:
      if agent.currentIssue is self.issue:
        return agent

  def get_conversation(self):
    if isinstance(self.issue.assignedTo, SupportAgent):
      return self.issue.assignedTo.conversation
    else:
      return None

  def get_sop(self):
    agent = self.issue.assignedTo
    if agent:
      return agent.sop


# Avoid import circularities
from droned.models.team import Team, SupportAgent
from droned.models.conversation import Conversation
