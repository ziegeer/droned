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

from twisted.internet import reactor
from droned.models.server import Server
from droned.models.droneserver import DroneD
from droned.models.app import App, AppVersion, AppInstance
from droned.models.action import Action
from droned.models.issue import Issue
from droned.models.conversation import Conversation, ChatRoom
from droned.models.team import Team, SupportAgent
from droned.entity import Entity
from droned.logging import log
import config

try: all #python2.4 test
except NameError:
    from kitt.util import all

class Environment(Entity):
    name = property(lambda self: config.ROMEO_ENV_NAME)
    environment = property(lambda self: config.ROMEO_ENV_OBJECT)
    servers = property(lambda self: (server for server in Server.objects if not server.unreachable))
    badServers = property(lambda self: (server for server in Server.objects if server.unreachable))
    droneds = property(lambda self: (server.droned for server in self.servers))
    apps = property(lambda self: (app for app in App.objects if app.shouldRunOn) )
    appversions = property(lambda self: (av for av in AppVersion.objects if av.app.shouldRunOn) )
    appinstances = property(lambda self: AppInstance.objects)
    ready = property(lambda self: all(not server.droned.stale for server in self.servers))
    readyServers = property(lambda self: (server for server in self.servers if not server.droned.stale))
    unlistedServers = property(lambda self: (server for server in Server.objects if not server.listed))
    currentRelease = None
    polling = False
    managing = False
    serializable = True

    def __getstate__(self):
        state = {}
        if self.currentRelease:
            r = self.currentRelease
            state['currentRelease'] = (r.name, r.version, r.timestamp)
        return state

    @staticmethod
    def construct(state):
        global environment, env
        environment = env = Environment()
        if state.get('currentRelease'):
            (name,version,timestamp) = state['currentRelease']
            env.currentRelease = Release(name, version)
            env.currentRelease.timestamp = timestamp
            env.currentRelease.download()
        return env

    def _hostname_generator(self):
        apps = set()
        for app in self.environment.search('SHORTNAME'):
            apps.add(app)

        def add_apps_to_server(server_model, server_romeo):
            """add apps to server"""
            for app in apps:
                if not server_romeo.isRelated(app): continue
                log('%s should run %s' % (server_model.hostname, app.VALUE))
                application = App(app.VALUE)
                application.runsOn(server_model)

        value = self.environment.get('HOSTNAME')
        if isinstance(value, list):
            for s in value:
                server = Server(s.VALUE)
                add_apps_to_server(server, s)
                yield server
        else:
            server = Server(value.VALUE)
            add_apps_to_server(server, value)
            yield server

    def loadServers(self):
        """Load all servers that are part of my environment"""
        delay = 0.0
        for server in self._hostname_generator():
            server.listed = True
            if self.polling:
                reactor.callLater(delay, server.startPolling)
                delay += config.SERVER_POLL_OFFSET

    def startPolling(self):
        """start polling other DroneD's"""
        self.polling = True
        delay = 0.0
        for server in self.servers:
            reactor.callLater(delay, server.startPolling)
            delay += config.SERVER_POLL_OFFSET

    def stopPolling(self):
        """stop polling other DroneD's"""
        self.polling = False
        for server in self.servers:
            server.stopPolling()

    def startManaging(self):
        """start managing other DroneD's"""
        self.managing = True
        for server in self.servers:
            if server.unreachable:
                continue
            server.startManaging()

    def stopManaging(self):
        """stop managing other DroneD's"""
        self.managing = False
        for server in self.servers:
            server.stopManaging()

    def ignoreServers(self, *hostnames):
        """ignore another DroneD

           @param hostnames (iterable of droned.models.server.Server())
        """
        for hostname in hostnames:
            if Server.exists(hostname):
                Server(hostname).connectFailure = 'ignored'
                Server(hostname).stopPolling()


env = environment = Environment()
