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

from twisted.internet.task import LoopingCall
from twisted.internet.defer import Deferred
from droned.logging import logWithContext
import config

log = logWithContext(type='action')


class ServerManager(object):
    runningCommands = 0

    def __init__(self, server):
        self.server = server
        self.queuedCommands = []
        self.queueRunner = LoopingCall(self._runQueued)


    def run(self, command, **kwargs):
        if config.DO_NOTHING_MODE:
            command = 'ping'
        deferredResult = Deferred()
        self.queuedCommands.append( (command,kwargs,deferredResult) )

        if len(self.queuedCommands) == 1:
            if self.queueRunner.running:
                self.queueRunner.stop() # stop & start causes immediate execution

        if not self.queueRunner.running:
            self.queueRunner.start(config.SERVER_MANAGEMENT_INTERVAL)

        return deferredResult


    def _runQueued(self):
        if not self.queuedCommands:
            self.queueRunner.stop()
        elif self.runningCommands < config.MAX_CONCURRENT_COMMANDS:
            (command,kwargs,deferredResult) = self.queuedCommands.pop(0)
            self.__class__.runningCommands += 1
            deferredResult.addBoth(self._commandCompleted)
            self.dronedCommand(command, **kwargs).chainDeferred( deferredResult )
            if not self.queuedCommands:
                self.queueRunner.stop()


    def _commandCompleted(self, outcome):
        self.__class__.runningCommands -= 1
        return outcome


    def dronedCommand(self, command, **kwargs):
        log('%s [droned command]: %s' % (self.server.hostname, command))
        return self.server.droned.sendCommand(
            command, 
            config.DRONED_MASTER_KEY,
            **kwargs
        )
