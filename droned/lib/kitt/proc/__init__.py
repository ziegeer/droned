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
import warnings
import platform
import traceback

__author__ = 'Justin Venus <justin.venus@orbitz.com>'
__doc__ = """Library to track processes. Used heavily by DroneD

This library makes use of a ``platform.system()`` loader to bring
in the proper components for a system.

If you are adding platform support you need to implement the
following methods and classes. If you are a consumer of this
library be mindful of the fact that this is all the library
guarentees.

  METHODS:
    def listProcesses():
        '''Returns a list of PID's
           @return (list)
        '''

    def findProcesses(s):
        '''Finds Process ID by pattern
           @return (dict) of LiveProcesses: regex
        '''
        

    def findThreadIds(s='.*'):
        '''Finds Threads ID by pattern
           @return (set)
        '''

    def isRunning(pid):
        '''is a given process id running

           @return (bool)
        '''

    def cpuStats():
        '''Returns a dictionary of cpu stats
           Note: stats will be platform specific
           @return (dict)
        '''

    def cpuTotalTime():
        '''Returns Total CPU Time Used in seconds
           @return (int)
        '''


  CLASSES:
    class Process(object):
        '''base class for processes'''
        implements(IKittProcess)

    class LiveProcess(Process):
        '''Get realtime access to process information'''
        implements(IKittLiveProcess)

    class ProcessSnapshot(Process):
        '''Snapshot of process information'''
        implements(IKittProcessSnapshot)

    #optionally implement, a platform agnostic implementation is provided
    class NullProcess(Process):
        '''Represents a non-existant process'''
        implements(IKittNullProcess)
"""

CPU_COUNT = os.sysconf('SC_NPROCESSORS_CONF')

class InvalidProcess(Exception): pass

from kitt.interfaces import IKittProcModule, IKittProcess, \
        IKittProcessSnapshot, IKittLiveProcess, IKittNullProcess, \
        IKittRemoteProcess, implements

#used by the platform loader at the end of this file
_process_interfaces = {
    'Process': IKittProcess,
    'ProcessSnapshot': IKittProcessSnapshot,
    'LiveProcess': IKittLiveProcess,
    'NullProcess': IKittNullProcess,
    'RemoteProcess': IKittRemoteProcess,
}

###############################################################################
# <PLATFORM specific=True>
# the following classes need a platform specific backend
###############################################################################
class Process(object):
    """Represents a process
       A platform specific backend should be developed
       The purpose of this class is to demonstrate
       a skeleton for the implementation of IKittProcess.
    """
    implements(IKittProcess)

    #expected attributes
    running = property(lambda s: s.isRunning())
    inode = property(lambda s: 0) #figure out how to get
    pid = property(lambda s: 0) #figure out how to get
    ppid = property(lambda s: 0) #figure out how to get
    exe = property(lambda s: None) #figure out how to get
    cmdline = property(lambda s: []) #figure out how to get
    memory = property(lambda s: s.memUsage())
    fd_count = property(lambda s: len(s.getFD()) or 3)
    stats = property(lambda s: s.getStats())
    environ = property(lambda s: s.getEnv())
    threads = property(lambda s: len(s.getTasks()))

    def __init__(self, pid):
        raise NotImplemented()
   
    def isRunning(self): return False
    def getEnv(self): return {}
    def getFD(self): return {}
    def getTasks(self): return {}
    def getStats(self): return {}
    def memUsage(self): return 0
    def cpuUsage(self): return {
        'user_util' : 0.0,
        'sys_util' : 0.0,
    }
    def __str__(self):
        return '%s(pid=%d)' % (self.__class__.__name__,self.pid)
    __repr__ = __str__


class LiveProcess(Process):
    """Get realtime access to process information"""
    implements(IKittLiveProcess)
    pass

class ProcessSnapshot(Process):
    """Snapshot of process information"""
    implements(IKittProcessSnapshot)
    pass
###############################################################################
# </PLATFORM>
###############################################################################

###############################################################################
# Platform Agnostic Implemenation
###############################################################################
class NullProcess(Process):
    """Represents a non-existant process"""
    #   Note: you should not need to override
    #     this implemenation, but you can if you
    #     want too
    implements(IKittNullProcess)
    pid = property(lambda s: 0)
    ppid = property(lambda s: 0)
    inode = property(lambda s: 0)
    exe = property(lambda s: None)
    cmdline = property(lambda s: [])
    fd_count = property(lambda s: 0)

    def __init__(self, pid=0): self._pid = 0
    def isRunning(self): return False
    def getEnv(self): return {}
    def getFD(self): return {}
    def getStats(self): return {}
    def getTasks(self): return {}
    def memUsage(self): return 0
    def cpuUsage(self): return {
        'user_util' : 0.0,
        'sys_util' : 0.0,
    }

class RemoteProcess(NullProcess):
    """This is a remote process that looks like a live process"""

    implements(IKittRemoteProcess)
    pid = property(lambda s: s.info.get('pid', 0))
    inode = property(lambda s: s.info.get('inode', 0))
    ppid = property(lambda s: s.info.get('ppid', 0))
    memory = property(lambda s: s.info.get('memory', 0))
    fd_count = property(lambda s: s.info.get('fd_count', 0))
    stats = property(lambda s: s.info.get('stats', {}))
    threads = property(lambda s: s.info.get('threads', 0))
    exe = property(lambda s: s.info.get('exe', None))
    cmdline = property(lambda s: s.info.get('cmdline', []))
    environ = property(lambda s: s.info.get('environ', {}))
    def __init__(self, pid):
        self.info = {'pid': pid}

    def updateProcess(self, infoDict):
        self.info.update(infoDict)

    def isRunning(self): return bool(self.pid)
    def memUsage(self): return self.memory
    def getFD(self): return [ i for i in self.fd_count ]
    def getStats(self): return self.stats
    def getEnv(self): return self.environ
    def getTasks(self): return set([ i for i in self.threads ])
    def cpuUsage(self):
        return {
            'user_util': self.info.get('user_util', 0.0),
            'sys_util': self.info.get('sys_util', 0.0),
        }
    def __str__(self): return '%s(pid=%d)' % (self.__class__.__name__, self.pid)
    __repr__ = __str__

###############################################################################
# Platform Agnostic Implemenation
###############################################################################


###############################################################################
# <required_methods fatal=True default_throw_exceptions=True>
###############################################################################
def listProcesses():
    """Returns a list of PID's"""
    raise NotImplemented()

def findProcesses(s):
    """Finds Process ID by pattern"""
    raise NotImplemented()

def findThreadIds(s='.*'):
    """Finds Threads ID by pattern"""
    raise NotImplemented()

def isRunning(pid):
    """is a given process id running, returns Boolean"""
    raise NotImplemented()

def cpuStats():
    """Returns a dictionary of cpu stats
       Note: stats will be platform specific
    """
    raise NotImplemented()

def cpuTotalTime():
    """Returns Total CPU Time Used in seconds"""
    raise NotImplemented()
###############################################################################
# </required_methods>
###############################################################################

_required_methods = [
    'listProcesses',
    'findProcesses',
    'findThreadIds',
    'isRunning',
    'cpuStats',
    'cpuTotalTime',
]

#import the platform specific backend, validate it and expose it
_platform = platform.system()
_backend = os.path.join(os.path.abspath(os.path.dirname(__file__)), 
    _platform + '.py'
)
#exportable interfaces
_EXPORTED = set(_process_interfaces.keys() + _required_methods)

if os.path.exists(_backend):
    name = None
    _has_all = False
    try:
        name = __name__ + '.' + _platform
        mod = __import__(name, {}, {}, [_platform])
        mod.InvalidProcess = InvalidProcess #for compatibility
        #validate the module interface
        if not IKittProcModule.providedBy(mod):
            e = ImportError("%s does not implement IKittProcModule interface" \
                    % name)
            raise e #throw exception as an import error
        if '__all__' in vars(mod):
            _EXPORTED.update(set(mod.__all__))
            _has_all = True
        for var, obj in vars(mod).items():
            if hasattr(obj, '__class__') and var in _process_interfaces:
                #demonstrate you at least read the implementation
                if not _process_interfaces[var].implementedBy(obj):
                    e = 'Class [%s] from %s does not match interface' % \
                            (var,name) 
                    warnings.warn(e)
                    continue
            #update our namespace
            globals().update({var: obj})
            if _has_all: continue
            #add to exported interfaces
            if not var.startswith('_'):
                _EXPORTED.add(var)
    except ImportError:
        e = 'Failed load platform specific process backend for [%s]' % \
                (_platform,)
        warnings.warn(e)
        traceback.print_exc()
    except AssertionError: pass
    except: traceback.print_exc()
    #clean up the sys.modules
    if name and name in sys.modules:
        del sys.modules[name]
else:
    e = 'Platform %s is not supported, expect problems' % (_platform,)
    warnings.warn(e)

#export public attributes, methods, and classes
__all__ = list(_EXPORTED)
