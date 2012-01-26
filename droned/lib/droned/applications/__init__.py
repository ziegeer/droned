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

from twisted.internet import defer, reactor
from twisted.python.failure import Failure
from kitt.util import dictwrapper
from kitt.decorators import debugCall, deferredAsThread
from kitt.proc import Process, listProcesses, findProcesses
from kitt.blaster import DIGEST_INIT
from droned.clients import command
from droned.protocols.application import ApplicationProtocol
from droned.models.appmgr import AppManager
import config
import time
import copy
import re
try: any
except NameError:
    from kitt.util import any

#for interfaces
from kitt.interfaces import implements, implementer, components, \
        IDroneDApplication, IDroneModelAppManager

__author__ = 'Justin Venus <justin.venus@orbitz.com>'
__doc__ = """
This module provides the foundation for DroneD's application management
abilites.
"""

class ApplicationPlugin(object):
    """Basis for DroneD Application Management.  There are some expectations
       that you must meet for this to work.  All started apps must daemonize
       ie fork away from DroneD.  The protocol must return the application pid
       or a failure if it does not the call will be cancelled and your app will
       terminate. take a look "__init__" to get an idea on the attributes that
       need to be setup, defaults are provided.

           read documentation of twisted.internet.reactor.spawnProcess and read
           droned.clients.__init__.command to see how it is being used.

           you need to define the following in your implementation of this class.
           
               name: (str) should be the name of your application

               #how to manage your application
               STARTUP_INFO: (dict)
               SHUTDOWN_INFO: (dict)

               #protocols to handle your application
               startProtocol: (class(droned.protocols.application.ApplicationProtocol))
               stopProtocol: (class(droned.protocols.application.ApplicationProtocol))

               #arguments to protocols
               startProtoArgs: (tuple)
               stopProtoArgs: (tuple)

               #keyword arguments to protocols
               startProtoKwargs: (dict)
               stopProtoKwargs: (dict)

           #further reading ...
           see droned.applications.ApplicationPlugin.__init__ and
           see droned.applications.ApplicationStorage.__init__ for
           the implementation specific details.

       This class and its derivatives use a metaclass to add storage
       capabilities.  also note that some of the instance methods are
       actually implemented inside of the metaclass.

       !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
       All plugins become singletons based on the ``class`` and ``name``.
       If you are extending another plugin class definition DONOT call it's
       __init__ method.  MRO and Singleton pattern will cause you hell.
       !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    """
    implements(IDroneDApplication)

    def __init__(self, *args, **kwargs):
        """The DroneD Service that loads ApplicationPlugins DOES NOT pass custom
           arguments or keyword parmeters to the constructor.  So you should
           not create constructors that expect external configuration. If you
           need external configuration you should implement a library to use for
           this purpose.  Default settings are provided in '__init__'.

           #all of these settings are required

           #provided by the metaclass as well
           #self.name = name
           #self.INITIALIZED = False

           #the metaclass provides these as defaults
           # self.STARTUP_INFO = {
           #    'START_USEPTY' : 0,
           #    'START_CHILDFD' : {0:'w',1:'r',2:'r'},
           #    'START_ENV' : {},
           #    'START_PATH' : None,
           #    'START_CMD' : '/bin/true',
           #    'START_ARGS' : (),
           # }
           # self.SHUTDOWN_INFO = { 
           #    'STOP_USEPTY' : 0,
           #    'STOP_CHILDFD' : {0:'w',1:'r',2:'r'},
           #    'STOP_ENV' : {},
           #    'STOP_PATH' : None,
           #    'STOP_CMD' : '/bin/true',
           #    'STOP_ARGS' : (),
           # }
           #
           #these protocol settings must be defined the metaclass will
           #provide sane defaults, that work for 90% of use cases
           #
           # self.startProtocol = ApplicationProtocol
           # self.startProtoArgs = () #protocol constructor *args
           # self.startProtoKwargs = {} #protocol constructor **kwargs
           # 
           # self.stopProtocol = ApplicationProtocol
           # self.stopProtoArgs = () #protocol constructor *args
           # self.stopProtoKwargs = {} #protocol constructor **kwargs
        """

    @defer.deferredGenerator
    def recoverInstance(self, occurance):
        """Recover Crashed Instances of the Application.
           this method should be subscribed to Event('instance-crashed')

           @param occurance: (object)
           @return defer.Deferred()
        """
        #check to make sure this is one of our instances
        if occurance.instance.app.name == self.name:
            self.log('application crashed restarting')
            #by default go through the AppManager
            d = self.service.startInstance(occurance.instance.label)
            d.addCallback(lambda x: self.log('sucessfully restarted') and x)
            d.addErrback(lambda x: self.log('failed to recover from crash') and x)
            result = None
            try:
                wfd = defer.waitForDeferred(d)
                yield wfd
                yield wfd.getResult()
            except:
                failure = Failure()
                self.log('throttling restart attempts')
                d = defer.Deferred()
                self.reactor.callLater(10, d.callback, None)
                wfd = defer.waitForDeffered(d)
                yield wfd
                wfd.getResult()
                yield failure
        else:
            yield 'not my application instance'

    @defer.deferredGenerator 
    def startInstance(self, label):
        """Starts an Application Instances based on our models rules

           @param label: (string) - app instance label

           @return defer.Deferred - be prepared for Failures()
        """
        start = dictwrapper(copy.deepcopy(self.STARTUP_INFO))

        #configure our protocol
        if 'debug' not in self.startProtoKwargs:
            self.startProtoKwargs['debug'] = False
        if 'timeout' not in self.startProtoKwargs:
            self.startProtoKwargs['timeout'] = self.DEFAULT_TIMEOUT
        if 'logger' not in self.startProtoKwargs:
            self.startProtoKwargs['logger'] = self.log

        #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        #
        # !! READ THIS COMMENT BLOCK !!
        #
        # the callback result from your protocol should return a dictionary
        # with a KEY 'pid' included and 'pid' should be an integer otherwise
        # the injected callback immediately following 'command' will fail to
        # update your instance state.  You have been warned.
        #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        result = None
        try:
            thisInst = self.getInstance(label)
            TIME = str(time.time())
            anchor = DIGEST_INIT()
            anchor.update(self.name)
            anchor.update(label)
            anchor.update(TIME) #add some randomness
            anchor = str(anchor.hexdigest())
            #inject some env variables that we may want to retrieve later
            ENV = {
                'DRONED_IDENTIFIER': anchor,
                'DRONED_STARTTIME': TIME,
                'DRONED_LABEL': label,
                'DRONED_APPLICATION': self.name,
                'DRONED_LOGDIR': config.LOG_DIR,
            }
            if thisInst.version:
                ENV['DRONED_VERSION'] = thisInst.version
            #add these vars to the start env of the contained application
            start.START_ENV.update(ENV)
            d = command(start.START_CMD, start.START_ARGS, start.START_ENV,
                start.START_PATH, start.START_USEPTY, start.START_CHILDFD,
                self.startProtocol, *self.startProtoArgs,
                **self.startProtoKwargs)
            wfd = defer.waitForDeferred(d)
            yield wfd
            result = wfd.getResult() #we probably might not know the pid yet
            #if allowed by config search for the instance after some delay
            pid = result.get('pid', 0) #just in case the protocol knows it
            if isinstance(self.SEARCH_DELAY, (int, float)) and not pid:
                d = defer.Deferred()
                self.reactor.callLater(self.SEARCH_DELAY, d.callback, None)
                wfd = defer.waitForDeferred(d)
                yield wfd
                wfd.getResult() #don't care about this result
                d = self.findProcesses()
                wfd = defer.waitForDeferred(d)
                yield wfd
                data = wfd.getResult()
                if data:
                    data = data.pop(0)[1] #we are just going to take the first
                    result.update(data) #we should have the pid captured
            thisInst.pid = int(result.get('pid', 0))
        except:
            result = Failure()
        yield result

#NOTE runs hot due to IO read on Linux and Solaris
    @deferredAsThread
    def findProcesses(self):
        """Attempt to find a process by an ASSIMILATION pattern.
           This is a relatively naive attempt to find an application
           that works in most cases. 

           NOTE:
             If your ASSIMILATION pattern includes group matches the 
             dictionary will be updated with the output of
             ``groupdict() from re.search``.  If droned is able to
             read the environment settings from the application that
             will be inlcuded in the result dictionary as well. 


           @callback (list) -  sorted([(int('PID'), dict), ...])
           @errback (twisted.python.failure.Failure())
           @return defer.Deferred()
        """
        candidates = {}
        def safe_process(pid):
            try: #because processes can be invalid
                return AppProcess(Server(config.HOSTNAME), pid)
            except: return None

        if self.PROCESS_REGEX:
            #rescan the whole system for processes
            for process in ( safe_process(pid) for pid in listProcesses() ):
                try:
                    if not process: continue 
                    if not process.__class__.isValid(process): continue
                    if process.pid in candidates: continue
                    if process.ppid != 1: continue #droned wants your daemons
                    if not process.running: continue
                    if not process.localInstall: continue
                    if process.managed: continue #already managed
                    cmd = ' '.join(process.cmdline)
                    if not cmd: continue
                    match = self.PROCESS_REGEX.search(cmd)
                    if not match: continue
                    #remember we tried to set some VARS on startInstance
                    _result = dict(**process.environ)
                    #allows us to set interesting parameters in the regex
                    _result.update(match.groupdict())
                    _result.update({'pid': process.pid})
                    candidates[_result['pid']] = _result
                except:
                    self.log('error searching for process check console log')
                    err('error searching for process')
        return sorted([(pid, d) for (pid, d) in candidates.items() if pid > 1])
         
    @defer.deferredGenerator
    def assimilateProcess(self, information):
        """Naive assimilation method. This should work for standard single
           instance applications, it will attempt to work with multi-instance
           applications as well. You should consider overriding this in an
           ApplicationPlugin if you need more advanced strategies.

           This is used by the ``services.application`` module to assimilate
           rogue application instances.

           This makes a best guess of which instance this should be assigned
           too.

           @param information (dict) "result of self.findPid"
              - required key "pid": (int) > 0
              - optional key "name": (str) self.name == name
              - optional key "label": (str) bind to this instance
              - optional key "version": (str) set version or promote version

           NOTES
              ``information['label']`` if the instance is running already
                  assimilation will fail

           @callback (instance of droned.models.app.AppInstance or None)
           @return (instance of defer.Deferred)
        """
        result = None
        pid = information.get('pid', 0)
        #droned attempted to inject these environment variables into the app
        name = information.get('name', information.get('DRONED_APPLICATION', self.name))
        version = information.get('version', information.get('DRONED_VERSION', None))
        label = information.get('label', information.get('DRONED_LABEL', None))
        try:
            assert pid #process is dead
            assert App.exists(name) #no such app
            if label: #appinstance label is known
                thisInst = self.getInstance(label) #may throw AssertionError
                assert not thisInst.running #make sure this instance isn't running
                if bool(version) and (thisInst.version != version):
                    thisInst = self.setVersion(label, version)
                thisInst.updateInfo({'pid': pid})
                result = thisInst
                raise Exception('assimilated process')
            else: #make a best guess attempt
                options = set()
                for ai in App(name).localappinstances:
                    if ai.running: continue 
                    options.add(ai)
                if bool(version): #try to perform a version match
                    for opt in options:
                        if opt.version == version:
                            opt.updateInfo({'pid': pid})
                            result = opt
                            raise Exception('assimilated process')
                #last ditch effort, pick lowest free container
                thisInst = sorted([i for i in options if not i.running])[0]
                if bool(version) and (thisInst.version != version):
                    thisInst = self.setVersion(thisInst.label, version)
                thisInst.updateInfo({'pid': pid})
                result = thisInst
                raise Exception('assimilated process')
        except: pass #swallow errors
        #minor cool down period
        d = defer.Deferred()
        self.reactor.callLater(0.1, d.callback, result)
        wfd = defer.waitForDeferred(d)
        yield wfd
        result = wfd.getResult() 
        yield result 

    def stopInstance(self, label):
        """Stops an Application Instances based on our models rules

           @param label: (string)      - app instance label

           @return defer.Deferred - be prepared for Failures()
        """
        stop = dictwrapper(self.SHUTDOWN_INFO)

        #configure our protocol
        if 'debug' not in self.stopProtoKwargs:
            self.stopProtoKwargs['debug'] = False
        if 'timeout' not in self.stopProtoKwargs:
            self.stopProtoKwargs['timeout'] = self.DEFAULT_TIMEOUT
        if 'logger' not in self.stopProtoKwargs:
            self.stopProtoKwargs['logger'] = self.log

        return command(stop.STOP_CMD, stop.STOP_ARGS, stop.STOP_ENV,
                stop.STOP_PATH, stop.STOP_USEPTY, stop.STOP_CHILDFD,
                self.stopProtocol, *self.stopProtoArgs,
                **self.stopProtoKwargs)

    def setVersion(self, label, version):
        """sets the version of this instance

           I attempt to delegate to the original provider.

           @param label: (string)
           @param version: (string)

           @return AppInstance()
        """
        version = AppVersion.makeVersion(self.name, version)
        thisInst = None

        thisInst = self.getInstance(label)

        if thisInst.version != version:
            thisInst.version = version
        return thisInst

    def addInstance(self, label):
        """add a new application instance optionally changing the version

           I attempt to delegate to the original provider.

           @param label: (string)

           @return AppInstance()
        """
        label = str(label)
        return AppInstance(Server(config.HOSTNAME), App(self.name), label)

    def delInstance(self, label):
        """delete an application instance

           I attempt to delegate to the original provider.

           @param label (string)

           @return None
        """
        label = str(label)
        thisInst = self.getInstance(label)
        if thisInst.running:
            raise AssertionError('cannot delete running application instance')
        AppInstance.delete(thisInst)

    def statusInstance(self, label):
        """Report the status of our Application Instance"""
        myInst = self.getInstance(label)
        result = {
            'name': self.name,
            'label': myInst.label,
            'enabled': bool(myInst.enabled),
            'running': myInst.running,
            'version': myInst.version,
            'pid': myInst.pid,
            'ppid': myInst.ppid,
            'inode': myInst.inode,
            'crashed': bool(myInst.crashed),
            'threads': myInst.threads,
            'memory': int(myInst.memory),
            'files': myInst.fd_count,
            'cpu': float(myInst.cpu),
        }
        state = str(getattr(myInst, 'state', 'unknown'))
        description = '%s is %s.' % (myInst.description, state)
        result['state'] = state
        result['description'] = description
        return result

    def getInstance(self, label):
        """get a reference to the application instance

           I attempt to delegate to the original provider.

           @param label: (string)

           @return AppInstance()
           @exception AssertionError
        """
        label = str(label)
        if AppInstance.exists(Server(config.HOSTNAME), App(self.name), label):
            return AppInstance(Server(config.HOSTNAME), App(self.name), label)
        raise AssertionError('no such application instance')

    def expose(self, *args, **kwargs):
        """expose methods via the L{IDroneModelAppManager} provider"""
        return self.service.expose(*args, **kwargs)

    def unexpose(self, *args, **kwargs):
        """unexpose methods via the L{IDroneModelAppManager} provider"""
        return self.service.unexpose(*args, **kwargs)

    def log(self, *args, **kwargs):
        """log messages via the L{IDroneModelAppManager} provider"""
        return self.service.log(*args, **kwargs)

#NOTE this is a private helper class
class StorageMixin(object):
    """This class is mixed in to provide storage for the ${LDroneDApplication}
       provider and fulfills API oblications for the L{IDroneModelAppManager}
       provider.  It is not overridable.
    """
    def load(self, var, default=None):
        """like getattribute, but values persist"""
        if var in self.__dict__:
            raise AttributeError('%s is a reserved attribute in %s' % str(self))
        if not var in self.service.applicationContext:
            self.service.applicationContext[var] = default
        return self.__getattribute__(var)

    def persist(self, var, val):
        """like setattribute, but values persist"""
        if var in self.__dict__:
            raise AttributeError('%s is a reserved attribute in %s' % str(self))
        self.service.applicationContext[var] = val
        return self.__getattribute__(var)

    def __getattribute__(self, key):
        """overrides getattr's behaviour for the instance"""
        try: return object.__getattribute__(self, key)
        except AttributeError:
            try: return self.service.applicationContext[key]
            except KeyError:
                raise AttributeError("'%s' object has no attribute '%s'" % \
                        (self.__class__.__name__, key))

    def __setattribute__(self, key, value):
        """overrides setattr's behaviour for the instance"""
        if key in self.service.applicationContext:
            self.service.applicationContext[key] = value
            return #we have safed our data for another day
        object.__setattribute__(self._object, key, value) 


from droned.logging import log, err, logWithContext
import os

###############################################################################
# Application Plugin Wrapper Entity that uses a tiny bit of Metaclass Magic
###############################################################################
class _PluginFactory(object):
    applications = property(lambda s: (i for i in s._config.keys() if i))
    def __init__(self):
        #get romeo configuration
        self._config = copy.deepcopy(config.APPLICATIONS)
        #default plugin provider
        self._default = copy.deepcopy(ApplicationPlugin)
        self._classMap = {ApplicationPlugin.__name__: self._default}
        self._instanceMap = {}
        #interface magic tricks
        components.registerAdapter(
            self.AppManagerAdaptToPlugin,
            AppManager, 
            IDroneDApplication
        )

    def makeAdaptable(self, klass):
        """take care of registering this plugin with a zope interface adapter.

           @param klass L{IDroneDApplication} implementor
           @return L{IDroneDApplication} implementor
        """
        #register for adaptation to an AppManager Model
        components.registerAdapter(
            self.ApplicationPluginAdaptToAppManager,
            klass, #plugin that needs adaptation
            IDroneModelAppManager
        )
        return klass

    def loadAppPlugins(self):
        """load all of the application plugins"""
        #find all application plugins
        my_dir = os.path.dirname(__file__)
        for filename in os.listdir(my_dir):
            if not filename.endswith('.py'): continue
            if filename == '__init__.py': continue
            modname = filename[:-3]
            try:
                mod = __import__(__name__ + '.' + modname, {}, {}, [modname])
            except:
                err('Application Plugin Loader Caught Exception')
                continue #horribly broken module ... skipping
            for name,obj in vars(mod).items():
                if name in self._classMap: continue
                try:
                    #need the interfaces to be what we expect
                    if IDroneDApplication.implementedBy(obj):
                        self._classMap[name] = copy.deepcopy(obj)
                except TypeError: pass
                except:
                    err('Application Plugin Scanner Caught Exception')

    def build_plugin(self, name):
        """build or lookup plugins

           @param name C{str} name of the application

           @return L{IDroneDApplication} provider
        """
        if name in self._instanceMap:
            return self._instanceMap[name]
        #create a logging router
        logging = logWithContext(
            type="%s,plugin" % (name,),
            route='application'
        )
        logging('dynamically building new plugin class')

        pluginConfig = self._config.get(name, {})
        #look up the application class by name
        className = pluginConfig.get('CLASS')
        if isinstance(className, bool) and not className:
            return None #this is explicitly disabled in config
        #get the positional constructor args from configuration
        classArgs = tuple(pluginConfig.get('CLASSARGS', ()))
        #get the constructor keyword args from configuration
        classKwargs = pluginConfig.get('CLASSKWARGS', {})

        #try to get your application plugin, defaults to builtin
        bases = (self._classMap.get(className, self._default),)
        MRO = set()
        for x in bases:
            MRO.add(x)
            for i in x.__bases__: MRO.add(i)
        #check if mro is ok
        MRO = any([b for b in MRO if ApplicationPlugin is b or \
                issubclass(b, ApplicationPlugin)])
        if not MRO:
            i = 'adding %s to %s for MRO safety' % \
                    (ApplicationPlugin, bases[0])
            logging(i) #log what we are doing to take the mystory out of it.
            bases += (ApplicationPlugin,)
        else: logging('Method Resolution Order looks good')
        logging('Adding Storage API to the Plugin.')
        bases = (StorageMixin,) + bases
        #######################################################################
        # new class defaults!!!!
        #######################################################################
        #setup the plugin by dynamically building a new class based
        #off of the provided reference design.
        newClassName = "Plugin(app=%s, class=%s)" % (name, bases[1].__name__)
        logging('creating plugin %s' % (newClassName,))
        plugin = self.makeAdaptable(type(newClassName, bases, {
            'name': property(lambda s: name),
            'service': property(lambda s: IDroneModelAppManager(s)),
            'configuration': property(lambda s: pluginConfig),
            'reactor': property(lambda s: reactor),
            'STARTUP_INFO': {
                'START_USEPTY' : 0,
                'START_CHILDFD' : {0:'w',1:'r',2:'r'},
                'START_ENV' : {},
                'START_PATH' : None,
                'START_CMD' : '/bin/true',
                'START_ARGS' : (),
            },
            'SHUTDOWN_INFO': {
                'STOP_USEPTY' : 0,
                'STOP_CHILDFD' : {0:'w',1:'r',2:'r'},
                'STOP_ENV' : {},
                'STOP_PATH' : None,
                'STOP_CMD' : '/bin/true',
                'STOP_ARGS' : (),
            },
            'startProtocol': ApplicationProtocol,
            'startProtoArgs': tuple(),
            'startProtoKwargs': dict(),
            'stopProtocol': ApplicationProtocol,
            'stopProtoArgs': tuple(),
            'stopProtoKwargs': dict(),
        })) #this guarentees we have a known API to work against
        #instantiate the plugin object with it's parameters
        self._instanceMap[name] = plugin(*classArgs, **classKwargs)
        self._instanceMap[name].log('application plugin interface initialized')
        self._pluginSetup(self._instanceMap[name])
        return self._instanceMap[name]

    def delete_plugin(self, instance):
        """remove the application plugin from use

           @param instance L{IDroneDApplication} provider
           @return None
        """
        for instanceID, _instance in self._instanceMap.items():
            if _instance is instance:
                self._instanceMap[instanceID].log('destroying plugin interface')
                del self._instanceMap[ instanceID ]
                return

    def _pluginSetup(self, plugin):
        """get romeo configuration bound in order to update the instance

           This gets called by the factory below.

           Note: ROMEO configuration always overrides the ApplicationPlugin's
             default constructor!!!!
        """
        plugin.log('applying configuration from romeo')
        tmp = getattr(plugin, 'INSTANCES', 1) #allow constructor to set this up 
        plugin.INSTANCES = plugin.configuration.get('INSTANCES', tmp)
        #get the real settings from configuration
        plugin.STARTUP_INFO.update(plugin.configuration.get('STARTUP_INFO',{}))
        plugin.STARTUP_INFO['START_ARGS'] = tuple(plugin.STARTUP_INFO['START_ARGS'])
        plugin.SHUTDOWN_INFO.update(plugin.configuration.get('SHUTDOWN_INFO',{}))
        plugin.SHUTDOWN_INFO['STOP_ARGS'] = tuple(plugin.SHUTDOWN_INFO['STOP_ARGS'])
        #how long to wait before searching for a newly started process
        tmp = getattr(plugin, 'SEARCH_DELAY', 5.0) #allow constructor to set this up 
        plugin.SEARCH_DELAY = plugin.configuration.get('SEARCH_DELAY', tmp)
        #how long to wait on a command before timing out!!! Timeout implies failure!
        tmp = getattr(plugin, 'DEFAULT_TIMEOUT', 120) #allow constructor to set this up 
        plugin.DEFAULT_TIMEOUT = plugin.configuration.get('DEFAULT_TIMEOUT', tmp) #seconds
        #how to assimilate an application
        tmp = getattr(plugin, 'ASSIMILATION_PATTERN', None) #allow constructor to set this up 
        plugin.ASSIMILATION_PATTERN = plugin.configuration.get('ASSIMILATION_PATTERN', tmp)
        #prepare the process regular expression
        plugin.PROCESS_REGEX = None
        if plugin.ASSIMILATION_PATTERN:
            plugin.PROCESS_REGEX = re.compile(plugin.ASSIMILATION_PATTERN, re.I)
        #if you don't like the default behavior of addInstance override it
        for i in range(plugin.INSTANCES):
            try: plugin.getInstance(i)
            except AssertionError:
                plugin.addInstance(i)
        tmp = getattr(plugin, 'AUTO_RECOVER', False) #allow constructor to set this up 
        #configure automatic restart after crash
        if plugin.configuration.get('AUTO_RECOVER', tmp):
            Event('instance-crashed').subscribe(plugin.recoverInstance)
        #allow romeo to hint that droned manages the daemonization of this app.
        if plugin.configuration.get('MANAGED', False):
            plugin.startProtoKwargs.update({'daemonize': True})
        plugin.log('plugin is configured and ready to be used')

    @implementer(IDroneDApplication)
    def AppManagerAdaptToPlugin(self, am):
        """I adapt an L{IDroneModelAppManager} provider to a L{IDroneDApplication}
           provider.

           @return L{IDroneDApplication} provider
        """
        #build the plugin at the last possible moment
        #or look it up, which ever happens happens.
        return self.build_plugin(am.name)

    @implementer(IDroneModelAppManager)
    def ApplicationPluginAdaptToAppManager(self, app):
        """I adapt any L{IDroneDApplication} provider to a corresponding
           L{IDroneModelAppManager} provider.

           @return L{IDroneModelAppManager} provider
        """
        return AppManager(app.name)

###############################################################################
# Application Plugin Wrapper
###############################################################################
pluginFactory = _PluginFactory()


#avoid circularities
from droned.models.server import Server
from droned.models.event import Event
from droned.models.app import App, AppInstance, AppVersion, AppProcess
__all__ = ['ApplicationPlugin', 'pluginFactory']
