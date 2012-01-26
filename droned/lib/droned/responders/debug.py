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

from droned.models.server import Server
from droned.models.droneserver import DroneD
from droned.models.app import App, AppVersion, AppInstance
from droned.responders import responder


@responder(pattern="delete (?P<hostname>.+)", form="delete <hostname>", help="Remove a server from the model")
def delete(conversation, hostname):
  server = Server(hostname)

  DroneD.delete(server.droned)

  for app in list(server.apps):
    app.shouldRunOn.discard(server)

  for appinstance in list(server.appinstances):
    AppInstance.delete(appinstance)

  for appversion in list(AppVersion.objects):
    appversion.services.applicableServers.discard(server)

  for scab in list(server.scabs):
    Scab.delete(scab)

  Server.delete(server)

  conversation.say("All serializable references to %s have been deleted" % hostname)

  if server.listed:
    conversation.say("However this server is listed in my server list, you must remove it manually before restarting gov.")
