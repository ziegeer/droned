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

from twisted.internet import protocol, reactor
from droned.errors import DroneCommandFailed
from droned.logging import logWithContext
import re

#if the app is fully managed by droned this will let us find it.
MANAGED_PID = re.compile('Daemon Pid: ?(?P<pid>\d+)')

###############################################################################
# Thoughts:
#
# This is a twisted application protocol base class that has been tailored to
# work with drone.application, droned.services.application and
# the DroneD server.  This protocol is consumed by drone.clients.command which
# is a ClientCreator extenstion that wraps reactor.spawnProcess.  This protocol
# isn't very useful by itself, but it does demonstrate how to create
# 'application model plugin protocols'.  This is one of the most important
# design blocks that makes DroneD generic enough to fit your needs, but verbose
# enough to get some real work done.
###############################################################################

class ApplicationProtocol(protocol.ProcessProtocol):
    """This is the protocol base class for application model derived plugins

       AppProtocols are tied to application models 'drone.models.application',
       the application model will pass the AppProtocol to the command processor
       'drone.clients.__init__.command'.  The AppProtocol is responsible for
       running the command to completion and firing the err/callbacks.  On 
       invocation of the callbacks a dictionary should be passed, format
       below.  On invocation of the errbacks a Failure() should be passed.
       The AppProtocol 'MUST' accept 'deferredResult' as the last '*arg' to
       the constructor, this is not optional and undefined behaviour will occur
       if you miss this.  The deferredResult is used for err/callbacks.

      
       !!!you should return the following data in your callbacks 
       callback dict: {'code' : "The Exit Code", 'pid' : "Process ID", ...}
       errback DroneCommandFailed() 
    """
    #just b/c I am a swell guy and you may need it
    reactor = property(lambda s: reactor)

    def __init__(self, *args, **kwargs):
        self.deferredResult = args[-1] #deferred result is always the last arg
        self.debug = False

        #capture application output as it would appear on a terminal
        self.OUTPUT = ''
        #capture STDERR
        self.STDERR = ''
        #capture STDOUT
        self.STDOUT = ''
        self.PID = 0

        #for debugging the protocol
        if 'debug' in kwargs and kwargs['debug'] == True:
            self.debug = True

        #for logging
        if 'logger' in kwargs:
            self.log = kwargs['logger']
        else:
            self.log = logWithContext(type='console')


    def logger(self, message):
        """Log to the designated logger"""
        if hasattr(self.log, '__call__'):
            self.log(message.strip())


    def connectionMade(self):
        """Process is running, we close STDIN by default"""
        self.transport.closeStdin() # close stdin


    def outReceived(self, data):
        """STDOUT Formatted for our logs"""
        data = str(data)
        if not self.PID:
            match = MANAGED_PID.search(data)
            if match:
                self.PID = int(match.groupdict().get('pid', 0))
        self.OUTPUT += data
        self.STDOUT += data
        self.logger(data)


    def errReceived(self, data):
        """STDERR Formatted for our logs"""
        self.OUTPUT += str(data)
        self.STDERR += str(data)
        self.logger(data)


    def inConnectionLost(self):
        """inConnectionLost! stdin is closed! (we probably did it)"""
        pass


    def outConnectionLost(self):
        """outConnectionLost! The child closed their stdout!"""
        pass 


    def errConnectionLost(self):
        """errConnectionLost! The child closed their stderr."""
        pass


    def runAppCallbacks(self, reason):
        """Trigger our callbacks to run now, you should add your own callback hooks
           in your own protocol imlementation to inorder to inject your application
           process identification.
        """
        if not self.deferredResult.called:
            #give the caller some context to work with
            result = {
                'description': 'Application Exited',
                'code': reason.value.exitCode,
                'pid': self.PID,
                'stdout': self.STDOUT,
                'stderr': self.STDERR,
                'screen': self.OUTPUT,
                'error': False,
            }
            if result['code'] == 0:
                self.deferredResult.callback(result)
            else:
                result['description'] = reason.getErrorMessage()
                result['error'] = reason
                self.deferredResult.errback(DroneCommandFailed(result))

        #should not get here
        return


    def processExited(self, reason):
        """"processExited, status %d" % (reason.value.exitCode,)"""
        return self.runAppCallbacks(reason)


    def processEnded(self, reason):
        """"processEnded, status %d" % (reason.value.exitCode,)"""
        return self.runAppCallbacks(reason)


__all__ = ['ApplicationProtocol']
