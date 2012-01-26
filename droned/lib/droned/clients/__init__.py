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
import sys
from twisted.python.failure import Failure
from twisted.internet import defer
from twisted.internet.protocol import ClientCreator
from droned.errors import DroneCommandFailed

###############################################################################
# This should count as fair use. it is based on 
#    twisted.internet.protocol._InstanceFactory
#
# <fairUse>
###############################################################################
class _InstanceFactory(object):
    """Only used by MyClientCreator."""

    def __init__(self, reactor, instance, deferred):
        self.reactor = reactor
        self.instance = instance
        self.deferred = deferred

    def __repr__(self):
        return "<ClientCreator factory: %r>" % (self.instance, )

    def buildProtocol(self, addr):
        self.reactor.callLater(0, self.deferred.callback, self.instance)
        del self.deferred
        return self.instance
###############################################################################
# </fairUse>
###############################################################################


class MyClientCreator(ClientCreator):
    """Client Interface to create an application"""

    def spawn(self, executable, args=(), env={}, path=None, usePTY=0,
              childFDS={0:'w',1:'r',2:'r'}):
        """Adding application clientCreator to ClientCreator"""
        #make sure to take care of the environment
        _env = os.environ.copy()
        _env.update(env)
        env = _env.copy()
        
        d = defer.Deferred()
        f = _InstanceFactory(self.reactor, self.protocolClass(*self.args,
                             **self.kwargs), d)

        self.reactor.spawnProcess(f.buildProtocol(None), executable, args=args,
                     env=env, path=path, usePTY=usePTY)
        return d #return our deferred


def command(executable, args, env, path, usePTY, childFD, protocol,
            *proto_args, **proto_kwargs):
    """command(host, port, protocol, *proto_args, **proto_kwargs)
       Initiate a process connection to the given application with args using 
       the given protocol class. *proto_args and **proto_kwargs are passed to 
       the protocol constructor, and the last positional argument will be a 
       Deferred for the result of the task. The protocol constructor must take 
       at least this one argument.
    """

    deferredResult = defer.Deferred()

    proto_args += (deferredResult,)
    if 'timeout' in proto_kwargs:
        timeout = proto_kwargs.pop('timeout')
    else:
        timeout = None
    
    #for convience
    argfix = proto_kwargs.pop('fixargs', True)

    #setup the command line to re-enter this file and daemonize
    if proto_kwargs.get('daemonize', False):
        from droned.management import dmx
        from droned.logging import log
        log('DroneD is daemonizing "%s" on your behalf' % (executable,))
        #massage the commandline args
        if path:
            env['DRONED_PATH'] = path
        #the path to the dmx utility
        path = os.path.sep.join(
            os.path.abspath(
                os.path.dirname(dmx.__file__)
            ).split(os.path.sep)[:-1]
        )
        #arguments to dmx
        args = ('dmx', executable) + args
        #switch out the executable for the same one that launched DroneD
        executable = sys.executable

    #laziness hack
    def _fix_args(cmd, a):
        """I fix your commandline args b/c you are probably lazy like me"""
        first = cmd.split(os.path.sep)[-1]
        if not len(a):
            a = (first,)
            return a
        if first != a[0]:
            a = (first,) + tuple(a)
        return a

    if argfix:
        newargs = []
        #sanitize arguments, b/c devs do silly things ... including myself
        for i in list(_fix_args(executable, args)):
            newargs += filter(lambda b: b, i.split(' ')) #FIXME lambda in filter
        args = tuple(newargs)

    from twisted.internet import reactor
    #setup the client application to run
    app = MyClientCreator(reactor, protocol, *proto_args, **proto_kwargs)
    deferredSpawn = app.spawn(executable, args, env, path, usePTY, childFD)

    #If the spawn fails the protocol task fails
    deferredSpawn.addErrback(lambda failure: deferredResult.called or
        deferredResult.errback(failure)
    )

    from kitt.decorators import debugCall
    if 'debug' in proto_kwargs and proto_kwargs['debug'] == True:
        deferredResult.errback = debugCall( deferredResult.errback )
        deferredResult.callback = debugCall( deferredResult.callback )

    if timeout:
        reactor.callLater(timeout, cancelTask, deferredResult)

    #Inject the executable and args into the results in the callback chain
    def injectInfo(outcome):
        try:
            if isinstance(outcome, dict):
                outcome['executable'] = executable
                outcome['args'] = args
            elif isinstance(outcome, Failure):
                if not outcome.check(DroneCommandFailed):
                    outcome = {
                        'error' : outcome,
                        'executable' : executable,
                        'args' : args,
                    }
        except: pass #some process failures don't have resultContext
        return outcome

    if 'debug' in proto_kwargs and proto_kwargs['debug'] == True:
        injectInfo = debugCall( injectInfo )

    deferredResult.addBoth(injectInfo)

    return deferredResult



def connect(host, port, protocol, *proto_args, **proto_kwargs):
    """connect(host, port, protocol, *proto_args, **proto_kwargs)
       Initiate a TCP connection to the given host and port using the given 
       protocol class. *proto_args and **proto_kwargs are passed to the protocol
       constructor, and the last positional argument will be a Deferred for the
       result of the task. The protocol constructor must take at least this one
       argument.
    """
    deferredResult = defer.Deferred()

    proto_args += (deferredResult,)

    if 'timeout' in proto_kwargs:
        timeout = proto_kwargs.pop('timeout')
    else:
        timeout = None

    from twisted.internet import reactor
    connector = ClientCreator(reactor, protocol, *proto_args, **proto_kwargs)
    deferredConnect = connector.connectTCP(host, port)

    from kitt.decorators import debugCall
    if 'debug' in proto_kwargs and proto_kwargs['debug'] == True:
        deferredResult.errback = debugCall( deferredResult.errback )
        deferredResult.callback = debugCall( deferredResult.callback )

    #If the connection fails the protocol task fails
    deferredConnect.addErrback(lambda failure: deferredResult.called or 
                               deferredResult.errback(failure))

    if timeout:
        reactor.callLater(timeout, cancelTask, deferredResult)


    #Inject the server name and port into the results in the callback chain
    def injectServer(outcome):
        if isinstance(outcome, dict):
            outcome['server'] = proto_kwargs.get('hostname',host)
            outcome['port'] = port
        elif isinstance(outcome, Failure) and outcome.check(DroneCommandFailed):
            outcome.value.resultContext['server'] = proto_kwargs.get('hostname',
                                                                     host)
            outcome.value.resultContext['port'] = port
        return outcome


    if 'debug' in proto_kwargs and proto_kwargs['debug'] == True:
        injectServer = debugCall( injectServer )

    deferredResult.addBoth(injectServer)

    return deferredResult


def cancelTask(deferredResult):
    """As suggested this cancels our task"""
    if not deferredResult.called:
        defer.timeout(deferredResult)

#exported interfaces
__all__ = ['connect', 'command', 'cancelTask']
