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

from droned.responders import responder


def _description(scab):
  return "%s on %s [%d]" % (scab.app.name, scab.server.hostname, scab.pid)


@responder(pattern="^accept-all-apps$", form="accept-all-apps", help="Accept all AppManager anomalies (for new envs)")
def accept_all_apps(conversation):
  count = 0
  for issue in list(Issue.objects):
    if issue.resolved: continue
    if issue.sopTitle == 'AppManager Anomaly':
      app = issue.context['app']
      server = issue.context['server']
      app.runsOn(server)
      count += 1

  conversation.say("Accepted %d AppManager anomalies" % count)


@responder(pattern="^crashed$", form="crashed", help="List all known instances in a 'crashed' state")
def crashed(conversation):
  instances = [ai.description for ai in AppInstance.objects if ai.crashed]
  if instances:
    conversation.say('\n' + '\n'.join(instances), useHTML=False)
  else:
    conversation.say("There are currently no crashed instances.")


@responder(pattern="^unreachable$", form="unreachable", help="List all known servers in an 'unreachable' state")
def unreachable(conversation):
  servers = [server.hostname for server in Server.objects if server.unreachable]
  if servers:
    conversation.say('\n' + '\n'.join(servers), useHTML=False)
  else:
    conversation.say("There are currently no unreachable servers.")


# Avoid import circularities
from droned.models.issue import Issue
from droned.models.app import AppInstance
from droned.models.server import Server
