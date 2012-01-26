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

#make version tracking easy
from twisted.python.versions import Version, IncomparableVersions

from twisted.internet import defer, task, reactor
from twisted.python.failure import Failure
from droned.errors import DroneCommandFailed
from droned.logging import err, log
from droned.entity import Entity
from kitt.proc import LiveProcess, InvalidProcess, RemoteProcess, NullProcess
from kitt.decorators import debugCall
import config
import time

#interface contracts that are used heavily in this package
from kitt.interfaces import implements, components, implementer, \
        IDroneModelAppProcess, IDroneModelApp, IDroneModelAppVersion, \
        IDroneModelAppInstance, IKittProcess, IKittRemoteProcess, \
        IKittNullProcess, IDroneModelServer

class AppProcess(Entity):
    """Track Processes that are associated with an AppInstance"""
    implements(IDroneModelAppProcess)
    created = property(lambda s: s._created)
    managed = property(lambda s: AppProcess.isValid(s) and \
            isinstance(s.appinstance, AppInstance) and \
            s.appinstance.__class__.isValid(s.appinstance))
    serializable = True
    localInstall = property(lambda s: bool(s.server.hostname == \
            config.HOSTNAME))

    pid = property(lambda s: s._pid)
    valid = property(lambda s: AppProcess.isValid(s) and s.running)

    def __getattribute__(self, name):
        """Overrode to fulfill our interface obligations"""
        if name in ('running','ppid','memory','fd_count','stats','threads',\
                'exe','environ','cmdline','inode'):
            try: return self.process.__getattribute__(name)
            except:
               delattr(self, '_process')
               #try one more time, just because we should
               return self.process.__getattribute__(name)
               #treat any failure like we are no longer running
        return object.__getattribute__(self, name)

    def __init__(self, server, pid):
        self._pid = pid
        self.server = IDroneModelServer(server)
        self._created = time.time()
        #don't set self._process
        try:
            try: #re-constructing, can cause problems with this
                if IKittNullProcess.providedBy(self.process.process):
                    raise InvalidProcess("Invalid PID (%s)" % pid)
            except AttributeError:
                if isinstance(self.process, NullProcess):
                    raise InvalidProcess("Invalid PID (%s)" % pid)
                raise #re-raise do avoid ending up in a pickle, literally
        except InvalidProcess:
            AppProcess.delete(self) #make sure we are invalid
            raise InvalidProcess("Invalid PID (%s)" % pid)
        except IOError: #linux and solaris kitt.proc.LiveProcess use files
            AppProcess.delete(self) #make sure we are invalid
            raise InvalidProcess("Invalid PID (%s)" % pid)
        except:
            err('wtf happened here .. seriously i do not know!!!')
            AppProcess.delete(self) #make sure we are invalid
            raise

    @property
    def process(self):
        """@return L{IKittProcess} provider"""
        #work around constructor and allow a process to appear to die
        if not hasattr(self, '_process'):
            #adapt this model to a IKittProcess
            self._process = IKittProcess(self)
        elif self._process.pid != self.pid or not self._process.running:
            AppProcess.delete(self) #take ourself out of serialization loop
            self._process = IKittNullProcess(self) #continue to work for any other refs
        return self._process

    @staticmethod
    def construct(state):
        server = Server(state.pop('server'))
        ap = None
        try:
            ap = AppProcess(server, state['pid'])
        except: return None
        if ap.localInstall and ap.inode != state['inode']: 
            AppProcess.delete(ap)
            return None
        ap._created = state.pop('created')
        #we know this is going throw an adapter
        if IKittRemoteProcess.providedBy(ap.process.process):
            #remaining attributes go into the remote process
            ap.updateProcess(state) #this is only useful to remote processes
        return ap

    def __getstate__(self):
        #save enough state so that remote processes are useful
        #account for scabs and appinstances
        data = {
            'created': self.created,
            'managed': self.managed,
            'server': self.server.hostname, #even scabs have this attr  
            'pid': self.pid,
            'inode': self.inode, #used to determine if the pid is valid
            'running': self.running,
            'memory': self.memory,
            'ppid': self.ppid,
            'fd_count': self.fd_count,
            'stats': self.stats,
            'threads': self.threads,
            'exe': self.exe,
            'cmdline': self.cmdline
        }
        #return managed process
        return data

    @property
    def children(self):
        """emits a generator of our child process objects

           this is only really useful for scab detection
           this only works if the child pid has been contained
           in another AppProcess Instance. Of course it could
           also be useful in bizarre situations with apps that
           have a parent supervisor and child worker.
        """
        for process in AppProcess.objects:
            if IKittNullProcess.providedBy(process.process): continue
            if not self.pid: break
            if process == self: continue
            if process.server.hostname != self.server.hostname: continue
            if process.ppid == self.pid and AppProcess.isValid(process):
                yield process

    @property
    def appinstance(self):
        """matches this AppProcess to an AppInstance

           @return L{IDroneModelAppInstance} provider or None
        """
        try: return IDroneModelAppInstance(self)
        except: return None


class App(Entity):
    """track applications"""
    implements(IDroneModelApp)
    managedOn = property( lambda self: set(server for server in \
            Server.objects if not server.unreachable and self in \
            server.droned.apps) )
    configuredOn = property( lambda self: set(i.server for i in \
            self.appinstances) )
    appversions  = property( lambda self: (av for av in \
            AppVersion.objects if av.app is self) )
    appinstances = property( lambda self: (ai for ai in \
            AppInstance.objects if ai.app is self) )
    localappinstances = property( lambda self: (i for i in self.appinstances \
            if i.server.hostname == config.HOSTNAME) )
    runningInstances = property( lambda self: (i for i in self.appinstances \
            if i.running) )
    localrunningInstances = property( lambda self: (i for i in \
            self.runningInstances if i.server.hostname == config.HOSTNAME) )
    #rxContext = RxAppContextDescriptor()
    serializable = True

    @property
    def latestVersion(self):
        latest = None
        for av in self.appversions:
            if not latest:
                latest = av
            if av > latest:
                latest = av
        return latest

    def __init__(self, name):
        self.name = name
        self.shouldRunOn = set()

    def __getstate__(self):
        return {
            'name' : self.name,
            'shouldRunOn' : [server.hostname for server in self.shouldRunOn]
        }

    @staticmethod
    def construct(state):
        app = App(state['name'])
        app.shouldRunOn = set( Server(hostname) for hostname in \
                state['shouldRunOn'] )
        return app

    def runsOn(self, server):
        if server not in self.shouldRunOn:
            self.shouldRunOn.add(server)
            Event('app-servers-change').fire(app=self, server=server, 
                change='added'
            )

    def doesNotRunOn(self, server):
        if server in self.shouldRunOn:
            self.shouldRunOn.remove(server)
            Event('app-servers-change').fire(app=self, server=server, 
                change='removed'
            )


class AppVersion(Entity):
    """Track application versions"""
    implements(IDroneModelAppVersion)
    description = property( lambda self: "%s %s" % \
            (self.app.name, self.version_string) )
    serializable = True

    def __getattribute__(self, name):
        """Overrode to fulfill Interface Obligations"""
        if name in ('package','major','minor','micro','prerelease','base',\
                'short'):
            return self.version.__getattribute__(name)
        return object.__getattribute__(self, name)

    def __init__(self, *args, **kwargs):
        self.version = Version(*args, **kwargs)
        self.app = IDroneModelApp(self.version)

    @property
    def version_string(self):
        """makes a nice version string that we can use for reconstruction"""
        result = '.'.join([
            str(self.major),
            str(self.minor),
            str(self.micro),
        ])
        if self.prerelease:
            result += '.%s' % str(self.prerelease)
        return result

    def __getstate__(self):
        return {
            'app' : self.package,
            'version' : self.version_string, #for proper serialization
        }

    def __cmp__(self, other):
        """overrode for easy comparison of AppVersion to AppVersion and Version
           to AppVersion.

           @raise IncomparableVersions:  when the package names of the versions
               differ.
           @param other L{twisted.python.versions.Version}, 
               L{IDroneModelAppVersion}, or object
           @return C{int} of value -1, 0, or 1
        """
        try:
            if IDroneModelAppVersion.providedBy(other):
                return self.version.__cmp__(other.version)
        except IncomparableVersions: raise
        except: pass
        if isinstance(other, Version):
            return self.version.__cmp__(other)
        return object.__cmp__(self, other)

    @staticmethod
    def makeAppVersion(name, version):
        """Similar to ``makeArgs``

           @return L{IDroneModelAppVersion} provider
        """
        args, kwargs = AppVersion.makeArgs(name, version)
        return AppVersion(*args, **kwargs)

    @staticmethod
    def makeVersion(name, version):
        """Similar to ``makeArgs``

           @return L{twisted.python.versions.Version}
        """
        args, kwargs = AppVersion.makeArgs(name, version)
        return Version(*args, **kwargs)

    @staticmethod
    def versionExists(name, version):
        """check if this L{IDroneModelAppVersion} provider exists"""
        args, kwargs = AppVersion.makeArgs(name, version)
        return AppVersion.exists(*args, **kwargs)

    @staticmethod
    def makeArgs(name, version):
        """goes through great lengths to make args for use
           by a constructor for class types -
               L{IDroneModelAppVersion} providers or 
               L{twisted.python.versions.Version}.

           @raises TypeError - if version is not convertable

           @param name C{str}
           @param version C{str}, C{list}, C{tuple}, or 
               L{twisted.python.versions.Version}

           @return ((name, major, minor, micro), {'prerelease': prerelease})
        """
        default = [0,0,0,0] #last number denotes pre-release
        if isinstance(version, Version):
            if version.package == name:
                return (
                    (name, version.major, version.minor, version.micro),
                    {'prerelease': version.prerelease}
                )
            else: version = []
        if isinstance(version, str):
            version = version.split('.')
        elif isinstance(version, tuple):
            version = list(version)
        elif isinstance(version, type(None)):
            version = []
        else:
            raise TypeError('Unacceptable version input %s' % type(version))
        version = version + default #pad the length for comparisons
        v = [ i[0] for i in zip(version, default) ]
        kwargs = {'prerelease': None}
        try: #don't try too hard to get this right
            if len(v) == 4 and v[3]:
                kwargs['prerelease'] = int(v[3])
        except: pass
        return (tuple((name,) + tuple([int(i) for i in v[0:3]])), kwargs)

    @staticmethod
    def construct(state):
        name = state['app']
        appversion = AppVersion.makeAppVersion(name, state['version'])
        return appversion


class AppInstance(Entity):
    """Track application instances"""
    implements(IDroneModelAppInstance)
    crashed = property(lambda s: s.shouldBeRunning and not s.running)
    startupInstallInfo = {}
    runningConfigs = set()
    serializable = True
    state = property(lambda s: (s.crashed and 'crashed') or \
            (s.running and 'up') or 'not running')
    description = property(lambda self: "%s %s [%s] on %s" % \
            (self.app.name, self.version, self.label, self.server.hostname))
    localInstall = property(lambda s: bool(s.server.hostname == \
            config.HOSTNAME))
#FIXME broken
    cpu = property(lambda s: 0.0)
    #immutable objects passed to the constructor
    label = property(lambda s: s._label, lambda x: None, lambda y: None,
            'instance label')
    app = property(lambda s: s._app, lambda x: None, lambda y: None,
            'L{IDroneModelApp} provider')
    server = property(lambda s: s._server, lambda x: None, lambda y: None,
            'L{IDroneModelServer} provider')

    def __getattribute__(self, name):
        """Overrode to fulfill our interface obligations"""
        if name in ('running','ppid','memory','fd_count','stats','threads',\
                'exe','environ','cmdline'):
            return self.process.__getattribute__(name)
        return object.__getattribute__(self, name)

    def __init__(self, server, app, label):
        try:
            if not IDroneModelServer.providedBy(server):
                e = '%s is not a L{IDroneModelServer} provider' % str(server)
                raise AssertionError(e)
            if not IDroneModelApp.providedBy(app):
                e = '%s is not a L{IDroneModelAppVersion} provider' % \
                        str(appversion)
                raise AssertionError(e)
        except AssertionError:
            AppInstance.delete(self)
            raise

        #internal information
        self.shouldBeRunning = False

        #model information
        self._label = label
        self._app = IDroneModelApp(app)
        self._server = IDroneModelServer(server)

        #serializable information
        self.info = {}
        #volitile data, unserializable
        self.context = {} 

    @property
    def children(self):
        """allow us to track an AppInstance's child processes"""
        if IDroneModelAppProcess.providedBy(self.process):
            return self.process.children #generator
        return ( i for i in [] ) #empty generator

    @property
    def process(self):
        """The process object contained by this application instance

           @raise InvalidProcess
           @return (instance of AppProcess)
        """
        if not hasattr(self, '_process'):
            #try to grab a live process, on exception grab a NullProcess
            try: self._process = IDroneModelAppProcess(self)
            except: self._process = IKittNullProcess(self) #should be a NullProcess
        elif IDroneModelAppProcess.providedBy(self._process) and not \
                AppProcess.isValid(self._process):
            self._process = IKittNullProcess(self)
        return self._process

    def __getstate__(self):
        state = {
          'server': self.server.hostname,
          'app': self.app.name,
          'pid': self.pid,
          'inode': self.inode,
          'version': self.version, #for proper serialization
          'label': self.label,
          'shouldBeRunning': self.shouldBeRunning,
          'enabled': self.enabled,
          'running': self.running,
          'info': {}, #other information storage
        }
       
        for attr, val in self.info.items():
            if attr in ('pid','inode','enabled'): continue
            state['info'][attr] = val
        return state

    @staticmethod
    def construct(state):
        server = Server(state['server'])
        #we need to format the version correctly
        appname = state['app']
        version = AppVersion.makeAppVersion(appname, state['version'])
        appinstance = AppInstance(server, App(appname), state['label'])
        appinstance.appversion = version
        appinstance.inode = state.get('inode',0)
        appinstance.pid = state.get('pid',0)
        appinstance.enabled = state.get('enabled', False)
        appinstance.shouldBeRunning = state.get('shouldBeRunning', False)
        x = appinstance.running #preload the process information
        #attempt to get our instance into the last known state
        appinstance.updateInfo(state['info'])
        return appinstance

    def updateInfo(self, info):
        """Called by app managers after a start/stop condition"""
        result = info
        if isinstance(info, Failure):
            info = info.check(DroneCommandFailed)
            if info: info = info.resultContext
        if not isinstance(info, dict):
            return result
        self.info.update(dict(**info))
        return result

    @defer.deferredGenerator
    def start(self):
        """convenient start method for an Application Instance"""
        result = None
        app = self.app.name
        label = self.label
        d = self.server.manager.run("%(app)s start %(label)s" % locals())
        wfd = defer.waitForDeferred(d)
        yield wfd
        result = wfd.getResult().values()[0]
        self.shouldBeRunning = True
        if self.server.hostname != config.HOSTNAME:
            self.updateInfo(result)
        if not self.running:
            result = Failure(DroneCommandFailed(result))
        yield result

    @defer.deferredGenerator
    def stop(self):
        """convenient stop method for an Application Instance"""
        result = None
        app = self.app.name
        label = self.label
        d = self.server.manager.run("%(app)s stop %(label)s" % locals())
        wfd = defer.waitForDeferred(d)
        yield wfd
        result = wfd.getResult().values()[0]
        self.shouldBeRunning = False
        if self.server.hostname != config.HOSTNAME:
            self.updateInfo(result)
        if self.running:
            result = Failure(DroneCommandFailed(result))
        yield result

    @defer.deferredGenerator
    def restart(self):
        """convenient restart method for an Application Instance"""
        result = None
        try:
            if self.running:
                d = self.stop()
                wfd = defer.waitForDeferred(d)
                yield wfd
                wfd.getResult()
            d = self.start()
            wfd = defer.waitForDeferred(d)
            yield wfd
            result = wfd.getResult()
        except:
            result = Failure()
            log('Unhandled exception\n' + result.getTraceback())
        yield result

    ###########################################################################
    # getting and setting of attr's ``pid``, ``inode``, ``version``, and 
    # ``appversion`` are done below here.
    ###########################################################################
    def _getpid(self):
        pid = int(self.info.get('pid',0))
        if hasattr(self, '_process') and (self.process.pid != pid):
            delattr(self, '_process') #force rescan for process
        return pid
    def _getinode(self):
        inode = int(self.info.get('inode',0))
        if hasattr(self, '_process') and (self.process.inode != inode):
            delattr(self, '_process') #force rescan for process
        return inode
    def _setpid(self, pid):
        self.info['pid'] = int(pid)
    def _setinode(self, inode):
        self.info['inode'] = int(inode)
    def _getversion(self):
        if not hasattr(self, '_version'):
            self._version = AppVersion.makeAppVersion(self.app.name,None)
        return self.appversion.version_string
    def _getappversion(self):
        if not hasattr(self, '_version'):
            self._version = AppVersion.makeAppVersion(self.app.name,None)
        return IDroneModelAppVersion(self._version)
#FIXME should fire Event on Version change
    def _setversion(self, version):
        """sets the self.appversion and self.version"""
        checkVersion = hasattr(self, '_version') #could be reconstructing
        if checkVersion:
            checkVersion = self._getappversion()
        if IDroneModelAppVersion.providedBy(version):
            self._version = IDroneModelAppVersion(version)
        else:
            self._version = IDroneModelAppVersion(
                AppVersion.makeAppVersion(self.app.name, version)
            )
        if checkVersion:
            data = {
                'instance': self,
                'version': self._version,
                'previous': checkVersion
            }
            if checkVersion < self._version:
                if checkVersion.major < self._version.major:
                    Event('new-major-release').fire(**data)
                else:
                    Event('new-release-version').fire(**data)
                return #done
            Event('release-change').fire(**data)
    def _getenabled(self):
        return self.info.get('enabled', False)
    def _setenabled(self, enabled):
        enabled = bool(enabled)
        status = self._getenabled()
        self.info['enabled'] = enabled
        if (enabled != status) and enabled:
            Event('instance-enabled').fire(instance=self)
        elif (enabled != status) and not enabled:
            Event('instance-disabled').fire(instance=self)
    #dynamically changing properties that are special to the system
    pid = property(_getpid, _setpid, lambda x: None, 'process id')
    inode = property(_getinode, _setinode, lambda x: None, 'process inode')
    version = property(_getversion, _setversion, lambda x: None,
            'App Version String')
    appversion = property(_getappversion, _setversion, lambda x: None,
            'L{IDroneModelAppVersion} provider')
    enabled = property(_getenabled, _setenabled, lambda x: None, 
            'instance enabled status')


###############################################################################
# Adapters allow our Models to change into other Models or other interface 
# providers, ideally this should insulate higher level user code.
###############################################################################
class AdaptToProcess(object):
    """I can adapt a L{IDroneModelAppProcess} provider or a 
       L{IDroneModelAppInstance} provider to a L{IKittProcess} provider.

       I hold no references to the Original Object after Instantiation.
    """
    implements(IKittProcess)
    def __init__(self, original):
        self.process = NullProcess() #assume the process is dead
        if original.server.hostname == config.HOSTNAME:
            #delay scanning the process, for as long as possible
            try: self.process = LiveProcess(original.pid, fast=True)
            except InvalidProcess: pass #raise all others
        else:
            self.process = RemoteProcess(ai.pid)
        #make an attempt to update the original caller
        if hasattr(original, 'pid'):
            try: original.pid = self.process.pid
            except: pass
        if hasattr(original, 'inode'):
            try: original.inode = self.process.inode
            except: pass

    def __getattribute__(self, name):
        try: return object.__getattribute__(self, name)
        except: return self.process.__getattribute__(name)
#provide an adapter for L{IDroneModelAppInstance} to L{IKittProcess}
components.registerAdapter(AdaptToProcess,AppInstance,IKittProcess)
#provide an adapter for L{IDroneModelAppProcess} to L{IKittProcess}
components.registerAdapter(AdaptToProcess,AppProcess,IKittProcess)

class AdaptToNullProcess(object):
    """I can adapt a L{IDroneModelAppProcess} provider or a 
       L{IDroneModelAppInstance} provider to a L{IKittNullProcess} provider.

       I hold no references to the Original Object after Instantiation.
    """
    implements(IKittNullProcess)
    def __init__(self, original):
        self.process = NullProcess()
        #make an attempt to update the original caller
        if hasattr(original, 'pid'):
            try: original.pid = self.process.pid
            except: pass
        if hasattr(original, 'inode'):
            try: original.inode = self.process.inode
            except: pass

    def __getattribute__(self, name):
        try: return object.__getattribute__(self, name)
        except: return self.process.__getattribute__(name)
#provide an adapter for L{IDroneModelAppInstance} to L{IKittProcess}
components.registerAdapter(AdaptToNullProcess,AppInstance,IKittNullProcess)
#provide an adapter for L{IDroneModelAppProcess} to L{IKittProcess}
components.registerAdapter(AdaptToNullProcess,AppProcess,IKittNullProcess)

@implementer(IDroneModelAppProcess)
def AdaptAppInstanceToAppProcess(ai):
    """I convert an AppInstance to an AppProcess.

       @param L{IDroneModelAppInstance} provider.
       @return L{IDroneModelAppProcess} provider.
    """
    pid = ai.pid
    server = ai.server
    ap = AppProcess(server, pid) #can still raise InvalidProcess
    ai.inode = ap.inode #keeps the AppInstance honest
    return ap #this is the new provider
components.registerAdapter(AdaptAppInstanceToAppProcess,AppInstance,
    IDroneModelAppProcess
)

@implementer(IDroneModelAppInstance)
def AdaptAppProcessToAppInstance(ap):
    """I convert an AppProcess to an AppInstance

       @raise AssertionError, when a L{IDroneModelAppInstance} provider
         is not available

       @param L{IDroneModelAppProcess} provider.
       @return L{IDroneModelAppInstance} provider.
    """
    server = ap.server
    pid = ap.pid
    inode = ap.inode
    for ai in AppInstance.objects:
        if ai.server != server: continue
        if ai.pid != pid: continue
        if not ai.__class__.isValid(ai): continue
        ai.inode = inode #keep the appinstance honest
        return ai #matched
    raise AssertionError('No AppInstance Found for This AppProcess')
components.registerAdapter(AdaptAppProcessToAppInstance,AppProcess,
    IDroneModelAppInstance
)

@implementer(IDroneModelApp)
def AdaptAppInstanceToApp(ai):
    """I convert an AppInstance to an App

       @param L{IDroneModelAppInstance} provider.
       @return L{IDroneModelApp} provider.
    """
    return App(ai.app.name)
components.registerAdapter(AdaptAppInstanceToApp,AppInstance,IDroneModelApp)

@implementer(IDroneModelApp)
def AdaptAppVersionToApp(av):
    """I convert an AppVersion to an App

       @param L{IDroneModelAppVersion} provider.
       @return L{IDroneModelApp} provider.
    """
    return App(av.app.name)
components.registerAdapter(AdaptAppVersionToApp,AppVersion,IDroneModelApp)

@implementer(IDroneModelApp)
def AdaptVersionToApp(version):
    """I convert a Version to an App

       @param version L{twisted.python.versions.Version}.
       @return L{IDroneModelApp} provider.
    """
    return App(version.package)
components.registerAdapter(AdaptVersionToApp,Version,IDroneModelApp)

@implementer(IDroneModelAppVersion)
def AdaptVersionToAppVersion(version):
    """I convert a Version to an AppVersion

       @param version L{twisted.python.versions.Version}.
       @return L{IDroneModelAppVersion} provider.
    """
    return AppVersion.makeAppVersion(version.package, version)
components.registerAdapter(AdaptVersionToAppVersion,Version,
    IDroneModelAppVersion
)

#Avoid import circularities
from droned.models.event import Event
from droned.models.server import Server

#this is the api we officially support
__all__ = ['AppProcess', 'App', 'AppVersion', 'AppInstance']
