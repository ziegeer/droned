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
import signal
import platform
import copyright

###############################################################################
# SystemD Ready on Linux, thanks to following this guide.
# http://0pointer.de/public/systemd-man/daemon.html
###############################################################################
__author__ = "Justin Venus <justin.venus@orbitz.com>"
from twisted.python.usage import Options, portCoerce

#where did we come from?
DIRECTORY = os.path.abspath(os.path.dirname(__file__))
#cool we need this to find the config
sys.path.insert(0, DIRECTORY)
#setup our library path based on where we came from
sys.path.insert(0, os.path.join(DIRECTORY,'lib'))

#TODO and FIXME configuration is a mess between cli, config.py, and romeo

#TODO add platforms
DEFAULT_REACTORS = {
    'Linux': 'epoll',
    'FreeBSD': 'kqueue', #TODO proc support isn't there for FreeBSD
    'SunOS': 'select',
}

try: any
except NameError:
    from kitt.util import any

###############################################################################
# Raceless Daemon/Option Parser Class
###############################################################################
class Daemon(Options):
    """Option Parser and raceless Daemon Provider.

    """
    #some of the wording is borrowed from twistd directly.
    optParameters = sorted([
        ["uid", "u", "nobody","The uid to run as."],
        ["gid", "g", "nobody", "The gid to run as."],
        ["pidfile","",os.path.join(os.path.sep,'var','run','droned.pid'),
            "Name of the pidfile."],
        ['port',"-p", 5500, "The command and control port", portCoerce],
        ["umask", "", 0, "The (octal) file creation mask to apply.", int],
        ["reactor","r", DEFAULT_REACTORS.get(platform.system(),"select"), 
            "Which reactor to use."], #we try to pick the best reactor for you.
        ["maxfd","", 1024, "Maximum File Descriptors to use.", int],
        ["deadline", "", 10, "Maximum time to wait for droned to shutdown.", int],
        ["wait", "", 60, "Maximum time to wait for droned to daemonize.", int],
        ["journal","",os.path.join(os.path.sep,'var','lib','droned','journal'),
            "Location to write system history"],
        ["logdir","",os.path.join(os.path.sep,'var','log','droned'),
            "Location to write system logs"],
        ["homedir","",os.path.join(os.path.sep,'var','lib','droned','home'),
            "Location to use as a home directory"],
        ["config","", None, "Use configuration from file, overrides commandline"],
        ["webdir","",os.path.join(os.path.sep,'var','lib','droned','web'),
            "Location to use as a webroot directory"],
        ["debug", "", False, "Don't install signal handlers and turn on debuggging", bool],
        ["hostdb","",os.path.join(os.path.sep,'etc','hostdb'), 
            "The directory to providing ROMEO configuration."],
    ])
    optFlags = [
        ["nodaemon", "n", "don't daemonize, don't use default umask of 0."],
        ["stop", "", "Stop a running Drone Daemon."]
    ]

    SIGNALS = dict((k, v) for v, k in signal.__dict__.iteritems() if \
            v.startswith('SIG') and not v.startswith('SIG_'))

    HOSTDB = property(lambda s: s['hostdb'])
    DEBUG = property(lambda s: s['debug'])
    CONFIGFILE = property(lambda s: s['config'])
    PIDFILE = property(lambda s: s['pidfile'])
    UID = property(lambda s: s['uid'])
    GID = property(lambda s: s['gid'])
    UMASK = property(lambda s: int(s['umask']))
    REACTORNAME = property(lambda s: s['reactor'])
    MAXFD = property(lambda s: int(s['maxfd']))
    DAEMONIZED = property(lambda s: not s['nodaemon'])
    REDIRECT_TO = property(lambda s: hasattr(os, "devnull") and os.devnull \
            or "/dev/null")
    PORT = property(lambda s: int(s['port']))
    DRONED_HOMEDIR = property(lambda s: s['homedir'])
    DRONED_WEBROOT = property(lambda s: s['webdir'])
    JOURNAL_DIR = property(lambda s: s['journal'])
    LOG_DIR = property(lambda s: s['logdir'])

    def __init__(self):
        self.running = False
        self.parentPid = os.getpid()
        Options.__init__(self)
        self.parseOptions() # Automatically parse command line

    def _protect(self):
        self.running = True

    def postOptions(self):
        """used to decide what we need to do now. i am called by parseOptions.
        """
        if self.running: return
        #if we are given external configuration use it overrides commandline
        if self.CONFIGFILE and os.path.exists(self.CONFIGFILE):
            from ConfigParser import ConfigParser as _cf
            _config = _cf()
            _config.read(self.CONFIGFILE)
            for key in self.keys():
                if  any([ i for i in self.optFlags if key in i]):
                    continue #things like stop and nodaemon are not meant for config
                try: #attempt to update the keys
                    t = type(self[key])
                    self[key] = t(_config.get('droned', key))
                except: pass

        self.sanitize_droned(kill=self['stop'])
        if self['stop']: sys.exit(0)

    def sanitize_droned(self, kill):
        """prepare for droned to run"""
        from kitt.proc import InvalidProcess, Process
        try:
            if os.path.exists(self.PIDFILE):
                fd = open(self.PIDFILE, 'r')
                pid = int(fd.read().strip())
                fd.close()
                p = Process(pid)
                if not kill and p.running:
                    self.log('droned is running with pid %d' % p.pid)
                    sys.exit(1) #running, which is good but not when start is issued
                self.log('stopping droned with signal %d' % signal.SIGTERM)
                try: os.kill(p.pid, signal.SIGTERM)
                except: pass
                if not p.waitForDeath(timeout=self['deadline']):
                    os.kill(p.pid, signal.SIGKILL)
                    self.log('stopping droned with signal %d' % signal.SIGKILL)
            elif kill:
                self.log('No Pidfile %s' % self.PIDFILE)
                sys.exit(1)
        except InvalidProcess:
            if kill: self.log('droned is not running')
        except SystemExit: raise
        except NotImplemented:
            self.log('%s is not supported ... good luck' % \
                    platform.system())
        if os.path.exists(self.PIDFILE):
            self.log('removing pidfile %s' % self.PIDFILE)
            os.unlink(self.PIDFILE)
        #prevent this from being called ever again
        self.sanitize_droned = lambda: None

    def opt_version(self):
        """droned version"""
        if self.running: return
        #TODO make this reflect some real version
        self.log("droned (the Drone daemon) %s" % (copyright.version,))
        self.log(copyright.copyright)
        self.log("See LICENSE for details.")
        sys.exit(0)

    #emit events when we receive signals
    def signal_emitter(self, signum, frame):
        """trap as many os signals as we can and the send the signal as an event
           !!only call this right before reactor.run
        """
        if signum == signal.SIGTERM:
            #suppress further signals
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            self.log('Received SIGTERM Shutting Down in 5 seconds')
            self.reactor.callLater(5.0, self.reactor.stop)
        #imported below in this file
        Event('signal').fire(
            signum=signum,
            signame=self.SIGNALS[signum],
            frame=frame
        )

    def log(self, message):
        """log helper eventually maps to a log observer"""
        sys.stdout.write(str(message)+'\n')

    def drop_privileges(self):
        """drop privileges, and terminate the parent process"""
        if self.DAEMONIZED:
            #Child kills parent ... hmm sounds like a greek tragedy.
            os.kill(self.parentPid, signal.SIGTERM)
            self.parentPid = 0 #just in case

        if os.getuid() != 0:
            # We're not root so, like, whatever dude
            return

        import config
        import grp
        import pwd
        # Get the uid/gid from the name
        running_uid = pwd.getpwnam(config.DRONED_USER).pw_uid
        running_gid = grp.getgrnam(config.DRONED_GROUP).gr_gid
        self.log('set uid/gid %d/%d\n' % (running_uid,running_gid))
  
        # Remove group privileges
        os.setgroups([])
  
        # Try setting the new uid/gid
        os.setgid(running_gid)
        os.setuid(running_uid)
        # let services know it is ok to start
        self.reactor.fireSystemEvent('priviledges')
        #prevent this from being called ever again
        self.drop_privileges = lambda: None

    def set_reactor(self):
        """sets the reactor up"""
        #get the reactor in here
        if self.REACTORNAME == 'kqueue':
            from twisted.internet import kqreactor
            kqreactor.install()
        elif self.REACTORNAME == 'epoll':
            from twisted.internet import epollreactor
            epollreactor.install()
        elif self.REACTORNAME == 'poll':
            from twisted.internet import pollreactor
            pollreactor.install()
        else: #select is the default
            from twisted.internet import selectreactor
            selectreactor.install()

        from twisted.internet import reactor
        self.reactor = reactor
        #shouldn't have to, but sys.exit is scary
        self.reactor.callWhenRunning(self._protect)
        #prevent this from being called ever again
        self.set_reactor = lambda: None

    def __call__(self, *args, **kwargs):
        if self.running: return
        if not self.DAEMONIZED:
            self.set_reactor()
            self.reactor.callWhenRunning(self.drop_privileges)
            return 0

        pid = os.fork()
        if (pid == 0):
            os.setsid() #new process leader
            if (os.fork() ==  0):
                os.chdir(os.path.sep)
                os.umask(self.UMASK)
                import resource	# Resource usage information.
                maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
                if (maxfd == resource.RLIM_INFINITY):
                    maxfd = self.MAXFD
  
                # Iterate through and close all file descriptors.
                for fd in range(0, maxfd):
                    try: os.close(fd)
                    except OSError: pass #ignore
                os.open(self.REDIRECT_TO, os.O_RDWR)
                os.dup2(0, 1)
                os.dup2(0, 2)

                #setting up the reactor
                self.set_reactor()
                try: #SystemD expects the pidfile the moment the parent dies
                    fd = open(self.PIDFILE, 'w')
                    fd.write(str(os.getpid()))
                    fd.close()
                except:
                    os.kill(self.parentPid, signal.SIGTERM)
                    sys.exit(1)
                #make sure we can drop privs later ...
                #also we kill the parent in this code block as well
                #which should give us plenty of time to catch errors
                #before blindly telling init that we are OK.
                self.reactor.callWhenRunning(self.drop_privileges)
            else: sys.exit(0) #don't care about the middle process
        else:
            try: #we wait for the child to terminate us, SystemD Fix.
                self.set_reactor() #alow the child some period to start
                self.reactor.callLater(self['wait'], self.reactor.stop)
                self.reactor.run() #rely on another reactor to block for us.
            except: pass
            if os.path.exists(self.PIDFILE):
                fd = open(self.PIDFILE, 'r')
                pid = int(fd.read().strip())
                fd.close()
                self.log('droned is running with pid %d' % pid)
                sys.exit(0)
            #you are a terrible parent
            self.log("I lost the child process and I'm not sure why.")
            sys.exit(1)

    def suppress_signals(self):
        """install a signal handler"""
        if self.DEBUG: return
        for signum, signame in self.SIGNALS.items():
            if signame in ('SIGKILL',): continue
            try: signal.signal(signum, self.signal_emitter)
            except RuntimeError: pass #tried to set an invalid signal
        #prevent this from being called again
        self.suppress_signals = lambda: None

###############################################################################
# Parse options and get ready to run
###############################################################################
try:
    drone = Daemon() 
except SystemExit: raise
except:
    from twisted.python.failure import Failure
    from kitt.util import getException
    failure = Failure()
    #use sys.stderr b/c we may have failed to create the class
    sys.stderr.write('%s: %s\n' % (sys.argv[0], failure.getErrorMessage()))
    sys.stderr.write('%s: Try --help for usage details.\n' % (sys.argv[0]))
    sys.exit(1)

drone() #lets daemonize (assuming !nodaemon) and get going
drone.reactor.callWhenRunning(drone.log, "DroneD reactor is now running.")

import droned.logging
if drone.DAEMONIZED:
    droned.logging.logToDir(drone.LOG_DIR)
    sys.stdout = droned.logging.StdioKabob(0)
    sys.stderr = droned.logging.StdioKabob(1)
else: droned.logging.logToStdout(timestamp=drone.DEBUG)
drone.log('logging subsystem initialized')

from twisted.application import service
from twisted.internet import defer
from twisted.python.failure import Failure
from twisted.python.log import err
from droned.entity import Entity

import romeo #Relational Object Mapping of Environmental Organization
import copy
from kitt import rsa
###############################################################################
#configuration management
###############################################################################
class ConfigManager(Entity):
    """ConfigManager Provides an Interface to get to any
       configuration item.
       
       After the ConfigManager has been instantiated you can
       access config from any python package in the DroneD
       framework simply by placing ```import config``` in
       your code.
    """
    serializable = False #would not be discovered in this file anyway
    def __init__(self):
        sys.modules['config'] = self
        self.data = {}
        drone.log('Initializing Configuration...')
        self.configure()
        drone.log('Configuration is loaded.')

    def configure(self):
        """load configuration for the rest of us."""
#FIXME, we need to fix romeo to load configuration for a directy specified at startup
#and allow SIGHUP to reload configuration
        try:
            drone.log('Processing ROMEO Configuration')
            romeo.reload(datadir=drone.HOSTDB)
            me = romeo.whoami()
        except romeo.IdentityCrisis:
            drone.log('ROMEO Configuration is missing SERVER entry for %s' % \
                    (romeo.MYHOSTNAME,))
            drone.log('DroneD is Exiting')
            exit(1) #Config FAIL!!!!

        ENV_NAME = [ i for i in romeo.listEnvironments() \
                if i.isChild(me) ][0].get('NAME').VALUE

        ENV_OBJECT = romeo.getEnvironment(ENV_NAME)

        #figure out if we are supposed to run new services
        SERVICES = {}
        for service in me.VALUE.get('SERVICES', []):
            if 'SERVICENAME' not in service: continue
            SERVICES[service['SERVICENAME']] = copy.deepcopy(service)

        #figure out if we are supposed to manage application artifacts
        APPLICATIONS = {}
        for i in romeo.grammars.search('my SHORTNAME'):
            search = str('select ARTIFACT')
            for x in romeo.grammars.search(search):
                if x.get('SHORTNAME') != i: continue
                if not ENV_OBJECT.isChild(x):
                    continue #right artifact/wrong env check
                APPLICATIONS[i.VALUE] = copy.deepcopy(x.VALUE)

        #journal and drone are builtins and should always run
        AUTOSTART_SERVICES = ('journal','drone')
        for service_object in SERVICES.values():
            if 'AUTOSTART' in service_object and service_object['AUTOSTART']:
                if service_object['SERVICENAME'] in AUTOSTART_SERVICES: continue
                AUTOSTART_SERVICES += (service_object['SERVICENAME'],)

        #make sure the application service is available
        if APPLICATIONS and 'application' not in AUTOSTART_SERVICES:
            AUTOSTART_SERVICES += ('application',)
        #primary data storage
        self.data = {
            'AUTOSTART_SERVICES': AUTOSTART_SERVICES,
            'EXCESSIVE_LOGGING': drone.DEBUG,
            'ROMEO_API': romeo,
            'ROMEO_HOST_OBJECT': me,
            'ROMEO_ENV_NAME': ENV_NAME,
            'ROMEO_ENV_OBJECT': ENV_OBJECT,
            'HOSTNAME': me.get('HOSTNAME').VALUE,
            'SERVICES': SERVICES,
            'APPLICATIONS': APPLICATIONS,
            'DRONED_PORT': drone.PORT,
            'DRONED_USER': drone.UID,
            'DRONED_GROUP': drone.GID,
            'DRONED_HOMEDIR': drone.DRONED_HOMEDIR,
#FIXME move webroot to drone service
            'DRONED_WEBROOT': drone.DRONED_WEBROOT,
#FIXME move journaldir to journal service
            'JOURNAL_DIR': drone.JOURNAL_DIR,
            'LOG_DIR': drone.LOG_DIR,
            'DEBUG_EVENTS': drone.DEBUG,
#FIXME cli, config file override these ... some of it needs to go into services
            'DRONED_PRIMES': '/usr/share/droned/primes',
            'DRONED_KEY_DIR': '/etc/pki/droned',
            'DRONED_MASTER_KEY_FILE': '/etc/pki/droned/local.private',
            'DRONED_MASTER_KEY': rsa.PrivateKey('/etc/pki/droned/local.private'),
            'DRONED_POLL_INTERVAL': 30,
            'SERVER_POLL_OFFSET': 0.333,
            'INSTANCE_POLL_INTERVAL': 1.0,
            'ACTION_EXPIRATION_TIME': 600,
            'DO_NOTHING_MODE': False,
            'MAX_CONCURRENT_COMMANDS': 5,
            'SERVER_MANAGEMENT_INTERVAL': 10,
        }

    def __getitem__(self, param):
        return self.data.get(param)

    def __setitem__(self, param, value):
        self.data[param] = value

    def __delitem__(self, param):
        if param in self.data:
            del self.data[param]

    def __getattr__(self, param): #compatibility hack
        try:
            return self.data[param]
        except KeyError:
            raise AttributeError("%s has no attribute \"%s\"" % (self, param))

    def __iter__(self):
        for key,value in sorted(self.data.items()):
            yield (key,value)
ConfigManager = ConfigManager() #hacktastic Singleton
import config #provided by ConfigManager
###############################################################################
# Setup basic logging working as soon as possible
###############################################################################

###############################################################################
# Setup our configuration from ENV or use sane defaults
###############################################################################

#if true deferreds will be traceable
defer.setDebugging(drone.DEBUG)

###############################################################################
# Setup our application services
###############################################################################
class ServiceManager(Entity):
    """ServiceManager Provides an Interface to get to any
       methods a service may provide.
       
       After the ServiceManager has been instantiated you can
       access services from any python package in the DroneD
       framework simply by placing ```import services``` in
       your code.
    """
    parentService = property(lambda s: s._parent)
    serializable = False #would not be discovered in this file anyway
    def __init__(self):
        if 'services' in sys.modules:
            e = "Instantiate ServiceManager before the services module!"
            raise AssertionError(e)
        self.SERVICE_STATE = {}
        self._parent = None
        drone.log('Loading Services')
        import services
        mask = ('loadAll',) #mask as private
        #truely become service module
        for var, val in vars(services).items():
            if var.startswith('_'): continue
            if var in mask: continue
            setattr(self, var, val) #bind the module globals to self
        services.loadAll() #load all services before replacing module
        sys.modules['services'] = self #replace the services module

        from droned.models.action import AdminAction
        #droneblaster action hooks
        self._action = AdminAction('service')
        self._action.expose('start', self._startService, ('name',),
            'starts the service'
        )
        self._action.expose('stop', self._stopService, ('name',),
            'stops the service'
        )
        self._action.expose('disable', self._disableService, ('name',),
            'prevent the service from starting'
        )
        self._action.expose('enable', self._enableService, ('name',),
            'allow the service to start'
        )
        self._action.expose('status', self._statusService, ('name',),
            'status of the service'
        )
        self._action.expose('list', lambda: \
                self._action.resultContext('\n'.join([ i for i in \
                    self.EXPORTED_SERVICES.keys() ]), None),
            (), 'list all services'
        )
        self._action.buildDoc() #finalize the admin action

    def _installServices(self, parentService):
        """Install Services for DroneD to run

           @param parentService (instance service.Application)
           @return None
        """
        drone.log('Installing Services')
        self._parent = parentService
        dead = set() #track objects that blow up on setup
        for name,obj in self.EXPORTED_SERVICES.items():
            try:
                #decorate start and stop methods for eventing
                obj.start = self._startDecorator(obj.start, name)
                obj.stop = self._stopDecorator(obj.stop, name)
                obj.install(self.parentService) #set the twisted parent service
                obj.parentService = self.parentService #make sure it's set
            except:
                err(Failure(), 'Exception while installing %s' % (name,))
                dead.add(name)

        drone.log('Evaluating Services Startup')
        #start up services that should run after everything is setup
        for name,obj in self.EXPORTED_SERVICES.items():
            if name in dead: continue
            #make sure we have a notion of dis/enabled
            if name not in self.SERVICE_STATE:
                self.SERVICE_STATE[name] = name in config.AUTOSTART_SERVICES
            #service is not in autostart and is not marked to start
            if name not in config.AUTOSTART_SERVICES:
                if not self.SERVICE_STATE[name]:
                    continue
            #service is marked as down even though it is in AUTO_START
            elif not self.SERVICE_STATE[name]: continue
            try:
                self.SERVICE_STATE[name] = True #be safe
                self._startService(name)
            except: #logging is not setup yet use twisted's err facility
                err(Failure(), 'Exception while registering %s' % (name,))

    def _statusService(self, name):
        """used by the AdminAction handler"""
        status = self.getService(name).running() and 'running and' or \
                'stopped and'
        status += self.SERVICE_STATE.get(name, False) and ' enabled' or \
                ' disabled'
        return self._result(status, name)

    def _startService(self, name):
        """used by the AdminAction handler"""
        obj = self.getService(name)
        if not obj.running():
            result = obj.start()
            if isinstance(result, Failure): return result
        return self._result('running', name)

    def _stopService(self, name):
        """used by the AdminAction handler"""
        obj = self.getService(name)
        if obj.running():
            result = obj.stop()
            if isinstance(result, Failure): return result
        return self._result('stopped', name)

    def _enableService(self, name):
        """used by the AdminAction handler"""
        self.SERVICE_STATE[name] = True #mark service as runnable
        return self._result('enabled', name)

    def _disableService(self, name):
        """used by the AdminAction handler"""
        self.SERVICE_STATE[name] = False #mark service as unrunnable
        return self._result('disabled', name)

    def _result(self, description, name):
        template = '[%(application)s] %(description)s'
        context = {'application': name, 'description': description}
        return self._action.resultContext(template, None, **context)

    def _startDecorator(self, func, name):
        """decorate the service start method for eventing"""
        log = droned.logging.logWithContext(type=name)
        obj = self.getService(name)
        def newfunc():
            try:
                if not self.SERVICE_STATE[name]:
                    raise AssertionError('%s is disabled' % (name,))
                if not obj.running():
                    log('Starting Service')
                    func() #don't really care about the return
                    if not obj.running():
                        raise AssertionError("%s not running" % (name,))
                    Event('service-started').fire(service=obj)
                    log('Started Service')
            except: return Failure()
            return True
        return newfunc

    def _stopDecorator(self, func, name):
        """decorate the service stop method for eventing"""
        log = droned.logging.logWithContext(type=name)
        obj = self.getService(name)
        def newfunc():
            try:
                if obj.running():
                    log('Stopping Service')
                    func() #we don't really care about the return
                    if obj.running():
                        raise AssertionError("%s is still running" % (name,))
                    Event('service-stopped').fire(service=obj)
                    log('Stopped Service')
            except: return Failure()
            return True
        return newfunc

    def _stopAll(self):
        for name in self.EXPORTED_SERVICES.keys():
            self._stopService(name)

    def __getattr__(self, param): #compatibility hack
        try: return self.EXPORTED_SERVICES[param]
        except KeyError:
            return object.__getattr__(self, param)
sm = ServiceManager()
import services #provided by ServiceManager

###############################################################################
# Setup Log Handlers
###############################################################################
from kitt.daemon import owndir
owndir(config.DRONED_USER, config.DRONED_HOMEDIR)
owndir(config.DRONED_USER, config.DRONED_WEBROOT)
owndir(config.DRONED_USER, config.JOURNAL_DIR)
if drone.DAEMONIZED:
    owndir(config.DRONED_USER, config.LOG_DIR)

#on linux with systemd we don't daemonize ourself
if not drone.DAEMONIZED:
    observer = droned.logging.logs['console']
    for srvc in vars(services)['EXPORTED_SERVICES'].keys():
        droned.logging.logs[srvc] = observer
else: #daemons get full blown logging support
    #setup the individual service logs
    droned.logging.logToDir(
        config.LOG_DIR,
        vars(services)['EXPORTED_SERVICES'].keys()
    )


#get all of our services ready to run
from droned.models.environment import *
import droned.events

#load all known events
droned.events.loadAll()

#import event prior to installing services
from droned.models.event import Event

#load servers that are part of my environment from ROMEO
env.loadServers()


###############################################################################
# Twisted Application Container Setup
###############################################################################

#create the application service container
application = service.Application("droned")

#make sure the top level service container is ready to go
drone.reactor.callWhenRunning(
    service.IService(application).startService
)
#install and start services after privledges drop
drone.reactor.addSystemEventTrigger('after', 'priviledges', 
    sm._installServices, application
)
#make sure our services properly terminate
drone.reactor.addSystemEventTrigger('before', 'shutdown', sm._stopAll)
#make twisted services properly terminate
drone.reactor.addSystemEventTrigger('before', 'shutdown',
    service.IService(application).stopService
)

###############################################################################
# Signal Handler and Reactor Startup
###############################################################################

#the signal handler must be installed after the reactor is running!!!
drone.reactor.callWhenRunning(drone.suppress_signals)
#last step, turn the reactor loose
drone.log('DroneD is starting the reactor.')
drone.reactor.run()
drone.log('DroneD is now Exiting.')
sys.exit(0) #done now, let's do this again sometime
