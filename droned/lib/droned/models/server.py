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
import time
from twisted.python.failure import Failure
from twisted.internet import task, defer
from twisted.internet.error import ConnectError, DNSLookupError
from droned.entity import Entity
from droned.logging import log
import config
import copyright

from kitt.interfaces import implements, IDroneModelServer

class Server(Entity):
    implements(IDroneModelServer)
    connectFailure = None
    appinstances = property( lambda self: (i for i in AppInstance.objects if \
            i.server is self) )
    apps = property( lambda self: (a for a in App.objects if self in a.shouldRunOn) )
    scabs = property( lambda self: (s for s in Scab.objects if s.server is self) )
    unreachable = property( lambda self: self.connectFailure is not None )
#FIXME this doesn't seem right we should remove it
    installedApps = property( lambda self: set(av.app for av in self.installed) )
    debug = False
    serializable = True
    listed = False
    logs = {}

    def __init__(self, hostname):
        self.hostname = hostname
        self.installed = {}
        self.droned = DroneD(self)
        self.manager = ServerManager(self)

    def __getstate__(self):
        installed = {}
        for appversion,configs in self.installed.items():
            av = (appversion.app.name, appversion.version)
            installed[av] = []
            for configpkg in configs:
                cp = (configpkg.name, configpkg.version)
                installed[av].append(cp)

        return {
            'hostname' : self.hostname,
            'connectFailure' : self.connectFailure,
            'debug' : self.debug,
            'installed' : installed,
        }

    @staticmethod
    def construct(state):
        server = Server( state['hostname'] )
        if state['connectFailure'] != server.connectFailure:
            server.connectFailure = state['connectFailure']
        if state['debug'] != server.debug:
            server.debug = state['debug']
        if 'installed' in state:
            for av,configs in state['installed'].items():
                app, version = App(av[0]), av[1]
                av = AppVersion(app,version)
                server.installed[av] = set( ConfigPackage(*cp) for cp in configs )
        return server

    @staticmethod
    def byName(name):
      if Server.exists(name):
          return Server(name)
      for server in Server.objects:
          if server.hostname.startswith(name):
              return server

    def startPolling(self):
        self.droned.startPolling()

    def stopPolling(self): 
        self.droned.stopPolling()


from droned.errors import DroneCommandFailed
from kitt.decorators import * #we are using a lot of decorators here
from kitt.keyring import RSAKeyRing
from droned.models.action import AdminAction, Action
import fcntl
import random
import struct
import gc #to list all models
import os

class DroneServer(Entity):
    """This model controls the routing of commands from the various services."""
    keyRing = RSAKeyRing('%s' % (config.DRONED_KEY_DIR,))
    lock = defer.DeferredLock()

    def __init__(self):
        self._primes = set()
        self.builtins = {
            'help': self.help_action,
            'ping': self.ping_action,
            'list': self.list_action,
            'shell': self.shell_action,
            'reload': self.reload_action,
            'tasks': self.tasks_action,
            'cancel': self.cancel_action,
        }
        #self register this server hostname
        if not Server.exists(config.HOSTNAME):
            server = Server(config.HOSTNAME)
            server.listed = True
        else:
            server = Server(config.HOSTNAME)
        self.server = server

    def _license(self, argstr):
        return "\n" + copyright.copyright_notice
    _license.__doc__ = copyright.copyright

    def _version(self, argstr):
        """Shows the server version"""
        return "DroneD/%s" % (copyright.version,)

    @synchronizedDeferred(lock)
    @deferredAsThread #will catch exceptions
    def getprime(self):
        pfh = open(config.DRONED_PRIMES)
        psize = os.stat(config.DRONED_PRIMES)[6]
        if (psize % 4) != 0 or psize < 4000:
            pfh.close()
            raise AssertionError("primes file is corrupt/too small")
        try: fcntl.fcntl(pfh.fileno(), fcntl.F_SETFD, fcntl.FD_CLOEXEC)
        except: pass
        result = 0
        while True:
            try:
                r = random.randint(0,(psize - 4) / 4) * 4
                pfh.seek(r)
                p = pfh.read(4)
                prime = struct.unpack("!L",p)[0]
                #makes a blocking call from this thread to the reactor
                #this is done for thread safety
                sync = synchronizedInThread()
                trp = sync(self._trackPrime)
                result = trp(prime) 
                break
            except AssertionError: continue
        pfh.close()
        return result


    def _trackPrime(self, prime):
        """Tracks the prime numbers"""
        assert prime not in self._primes
        self._primes.add(prime)
        return prime


    @synchronizedDeferred(lock)
    def validateMessage(self, magicNumber):
        """Is the message meant for me"""
        for prime in self._primes:
            if (magicNumber % prime) == 0:
                #release the prime to prevent replay attacks
                self._primes.discard(prime)
                return True
        return False


    @synchronizedDeferred(lock)
    def releasePrime(self, prime):
        """release the prime"""
        self._primes.discard(prime)


    def get_action(self, action):
        """route commands to perform actions"""
        if action == 'license':
            return self._license
        elif action == 'version':
            return self._version
        foo = self.builtins.get(action, False)
        if foo and hasattr(foo, '__call__'):
            return foo
        #look for AdminActions
        for admin in AdminAction.objects:
            if action != admin.action: continue
            return admin
        raise AssertionError("No such action ... try 'help'")


    def tasks_action(self, argstr):
        """Usage: tasks - displays tasks and status"""
        results = ['',"completed/succeeded\t'task'\n"]
        for action in Action.objects:
            r = """\t%s/%s\t'%s'""" % \
                    (action.completed, action.succeeded, action.description)
            results.append(r)
        results.append('')
        return (0, '\n'.join(results))

#TODO test
    def cancel_action(self, argstr):
        """Usage: cancel 'task' - cancels all tasks matching the description"""
        cancelled = 0
        plural = 's'
        for action in Action.objects:
            if action.completed: continue
            if action.description == argstr:
                try:
                    action.deferred.cancel()
                    cancelled += 1
                except: pass
        if cancelled == 1: plural = ''
        return (0, 'cancelled %d task%s' % (cancelled, plural))


    def reload_action(self, argstr):
        """Usage: reload - reload droned rsa keys"""
        self._keyRing.reloadKeys()


    def ping_action(self, argstr):
        """Usage: ping"""
        return (42, 'PONG')


    def help_action(self, argstr):
        """Usage: help <action>"""
        if not argstr:
            l = self.builtins.keys() + [ str(i.action) for i in \
                   AdminAction.objects ] + ['license', 'version']
            return '\n'.join(sorted(l))
        try: return self.get_action(argstr).__doc__
        except: return 'Unknown action'


    def list_action(self, argstr):
        """Lists all known model instances and their classes"""
        r = ''
        for obj in gc.get_objects():
            if not isinstance(obj, Entity): continue
            if not obj.__class__.isValid(obj): continue
            #avoid hidden objects
            if obj.__class__.__name__.startswith('_'): continue
            #avoid romeo key value objects
            r += '%s\t%s\n' % (obj.__class__.__name__,str(obj))
        return r


    #this was tried natively once before w/o success
    @deferredAsThread
    def shell_action(server, *cmd):
        """Usage: shell <cmd>\nReturns: <exitcode> <stdout>"""
        readfd,writefd = os.pipe()
        pid = os.fork()
        if pid == 0:
            devnull = open('/dev/null','r')
            os.dup2(devnull.fileno(),0)
            os.dup2(writefd,1)
            os.dup2(writefd,2)
            os.execvp('/bin/sh',['/bin/sh','-c'] + list(cmd))
            os._exit(255)
        else:
            os.close(writefd)
            fh = os.fdopen(readfd)
            output = fh.read()
            status = os.waitpid(pid,0)
        return (status[1] >> 8,output)


    def formatResults(self, response):
        """format results of actions"""
        #handle the NoneType case
        if not response:
            return { 'code' : 0, 'description' : 'None' }
        Msg = {
            'code' : -4,
            'description' : 'could not format result ' + str(response)
        }
        #fix errback results
        if isinstance(response, Failure):
            #see if this is a known droned command failure
            if response.check(DroneCommandFailed):
                response = response.value.resultContext
            else:
                response = {
                    'description' : response.getErrorMessage(),
                    'code' : 1,
                    'stacktrace' : response.getTraceback(),
                    'error' : True,
                }
        #should not have to check like this, but some old code does this wrong
        elif isinstance(response, DroneCommandFailed):
            response = response.resultContext
        if isinstance(response, dict):
            if 'description' not in response and 'error' in response and \
                    isinstance(response['error'], Failure):
                response['description'] = response['error'].getErrorMessage()
                response['stacktrace'] = response['error'].getTraceback()
                server_log(response['stacktrace']) #log to the console log 
            Msg.update(response)
        elif isinstance(response, basestring):
            Msg = { 'code' : 0 , 'description' : response }
        elif isinstance(response, tuple):
            code, message = response[0:2]
            if not isinstance(code, int): code = -2
            Msg = { 'code' : code, 'description' : message }
        return Msg


# These come after our class definitions to avoid circular import dependencies
from droned.models.app import App, AppVersion, AppInstance
from droned.models.droneserver import DroneD
from droned.management.server import ServerManager
#exportable interface of the server
drone = DroneServer = DroneServer()
