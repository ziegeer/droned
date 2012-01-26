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

import sys
import time
from twisted.internet.task import LoopingCall
from twisted.internet.error import ConnectError, DNSLookupError
from twisted.internet.defer import TimeoutError, deferredGenerator, \
        waitForDeferred, maybeDeferred
from twisted.python.failure import Failure
from droned.entity import Entity
from droned.logging import debug
import config

class DroneD(Entity):
  _lastPolled = 0.0
  _pollInterval = config.DRONED_POLL_INTERVAL
  age = property( lambda self: time.time() - self._lastPolled )
  stale = property( lambda self: self.age > (2 * self._pollInterval) )
  polling = property( lambda self: self.pollTask.running )
  debug = property( lambda self: self.server.debug )
  currentFailure = None
  serializable = True

  def __init__(self, server):
    self.server = server
    self.port = config.DRONED_PORT
    #if this is a remote server use the blaster protocol
    if self.server.hostname != config.HOSTNAME:
        self.sendCommand = DroneBlaster([self.server.hostname])
    self.sendQuery = GremlinClient(self.server.hostname, self.port)
    self.pollTask = LoopingCall(self.poll)
    self.apps = frozenset()

  @deferredGenerator
  def sendCommand(self, command, keyObj, **kwargs):
      """default method is a short circuit to the server's action handler"""
      result = None
      try:
          services = sys.modules.get('services')
          drone = services.drone.drone
          args = command.split()
          action = drone.get_action(args.pop(0))
          if args:
              args = ' '.join(args)
          else:
              args = ''
          d = maybeDeferred(action, args)
          d.addBoth(drone.formatResults)
          wfd = waitForDeferred(d)
          yield wfd
          result = {self.server: wfd.getResult()}
      except:
          result = Failure()
      yield result

  def __getstate__(self):
    return {
      'server': self.server.hostname,
      'port': self.port,
      'apps': [app.name for app in self.apps],
      'currentFailure': self.currentFailure, #custom exceptions with entity refs?
    }

  def startPolling(self):
    if not self.polling:
      self.pollTask.start(self._pollInterval)

  def stopPolling(self):
    if self.polling:
      self.pollTask.stop()

  def poll(self, **options):
    return self.sendQuery(**options)

  @staticmethod
  def construct(state):
    server = Server(state['server'])
    droned = server.droned
    droned.port = state['port']
    droned.apps = frozenset(App(name) for name in state.get('apps',[]))
    droned.currentFailure = state['currentFailure']
    return droned

# Do these last to avoid circular import dependencies
from droned.models.server import Server
from droned.clients.blaster import DroneBlaster
from droned.clients.gremlin import GremlinClient
