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
from droned.models.team import Team, SupportAgent
from droned.models.issue import Issue
from droned.responders import responder


@responder(pattern="^teams$", form="teams", help="List known Teams")
def teams(conversation):
  teamlist = '\n'.join("%s (%d members)" % (team.name, len(team.agents)) for team in Team.objects)
  conversation.say('\n' + teamlist, useHTML=False)


@responder(pattern="^members\s+(?P<name>\S+)", form="members <team>", help="List members of a team")
def members(conversation, name):
  if not Team.exists(name):
    conversation.say("No team named \"%s\" exists." % name)
  else:
    team = Team(name)
    if team.agents:
      members = ','.join(agent.jid for agent in team.agents)
      heading = "%s members:\n" % name
      conversation.say(heading + members, useHTML=False)
    else:
      conversation.say("That team has no members.")


@responder(pattern="^join\s+(?P<name>\S+)", form="join <team>", help="Tell droned you want to join a team")
def join(conversation, name):
  if not Team.exists(name):
    conversation.say("No team named \"%s\" exists." % name)
  else:
    team = Team(name)
    team.addMember( conversation.buddy )
    conversation.say("You are now on the %s team." % name)


@responder(pattern="^leave\s+(?P<name>\S+)", form="leave <team>", help="Tell droned you want to leave a team")
def leave(conversation, name):
  if not Team.exists(name):
    conversation.say("No team named \"%s\" exists." % name)
  else:
    team = Team(name)
    team.removeMember( conversation.buddy )
    conversation.say("You are no longer on the %s team." % name)


@responder(pattern="^(i'?m |i am )?busy$", form="busy", help="Tell droned to not bug you with support issues")
def busy(conversation):
  agent = SupportAgent( conversation.buddy )
  agent.ready = False
  conversation.say("Ok I won't bug you with support issues.")


@responder(pattern="^(i'?m |i am )?free$", form="free", help="Tell droned to bug you with support issues again")
def free(conversation):
  agent = SupportAgent( conversation.buddy )
  agent.ready = True
  conversation.say("Ok, I will bug you with support issues.")


@responder(pattern="^announce (?P<message>.+)$", form="announce <message>", help="Send a message to your team mates")
def announce(conversation, message):
  agent = SupportAgent( conversation.buddy )
  message = "<b>Announcement from %s</b> ::: %s" % (agent.name, message)
  told = 0
  for team in agent.teams:
    for otherAgent in team.agents:
      if otherAgent is agent: continue
      otherAgent.tell(message)
      told += 1
  if told:
    agent.tell('Your announcement has been sent to your %d team mates' % told)
  else:
    agent.tell('You do not have any team mates.')


@responder(pattern="^issues$", form='issues', help='List all open issues')
def issues(conversation):
  issues = sorted([i for i in Issue.objects if not i.resolved], key=lambda i: i.id)
  summaries = []
  for issue in issues:
    summary = "%d: %s" % (issue.id, issue.description)
    if issue.context['agent']:
      summary += " (%s is troubleshooting)" % issue.context['agent'].name
    elif isinstance(issue.context['assignedTo'], SupportAgent):
      summary += " (assigned to %s)" % issue.context['assignedTo'].name
    elif issue.context['assignedTo'] is None:
      summary += " (unassigned)"
    summaries.append(summary)

  heading = 'There are %d open issues\n' % len(issues)
  listing = '\n'.join(summaries)
  conversation.say(heading + listing, useHTML=False)


@responder(pattern="^grab (?P<id>\d+)$", form="grab <issue>", help="Troubleshoot a particular issue")
def grab(conversation, id):
  id = int(id)
  issue = Issue.byID(id)

  if not issue:
    conversation.say("There is no issue with the ID %d" % id)
  elif not issue.hasSOP:
    conversation.say("Unfortunately that issue doesn't have an SOP associated with it. "
                     "All I can do is describe the problem to you and wait for you to "
                     "<b>resolve<b> it manually")
    conversation.say(issue.description)
    contextSummary = '\n'.join("%s: %s" % info for info in issue.context.data.items())
    conversation.say(contextSummary, useHTML=False)
  else:
    existingAgent = issue.context['agent']

    if existingAgent:
      if existingAgent.conversation is conversation:
        conversation.say("You are already troubleshooting this issue!")
        return
      existingAgent.conversation.say("<b>%s has taken over this issue.</b>" % conversation.buddyName)
      existingAgent.currentIssue = None
      existingAgent.conversation.nevermind()

    conversation.say("Ok, I am assigning issue #%d to you." % id)
    agent = SupportAgent(conversation.buddy)
    #Make sure the agent is available first
    agent.ready = True
    agent.currentIssue = None
    agent.conversation.nevermind()

    agent.engage(issue)


@responder(pattern='^resolve (?P<id>\d+) (?P<resolution>.+)$', form='resolve <issue> <resolution>',
 help='Manually resolve a particular issue')
def resolve(conversation, id, resolution):
  id = int(id)
  issue = Issue.byID(id)

  if not issue:
    conversation.say("There is no issue with the ID %d" % id)
  elif issue.hasSOP:
    conversation.say("You cannot manually resolve an issue that has an SOP associated with it. "
                     "Instead you should <b>grab</b> the issue and go through the SOP.")
  else:
    conversation.say("Ok, I am resolving issue #%d" % id)
    issue.resolve(resolution)
