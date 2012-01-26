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

#this is a platform plugin, don't directly import it
#use ``import kitt.proc *`` for methods, attributes and classes

import struct, os, platform, time, re
from kitt.interfaces import IKittProcModule, IKittProcess, \
        IKittProcessSnapshot, IKittLiveProcess, implements, moduleProvides

if platform.system() != 'SunOS':
    raise OSError("Sorry, only SunOS is supported")

_sunos_version = int(platform.release().split('.')[-1])
if _sunos_version < 10:
    raise OSError("Sorry, version %d of SunOS is not supported" % _sunos_version)

__author__ = 'Justin Venus <justin.venus@orbitz.com>'

moduleProvides(IKittProcModule)

#python3 readiness
try:
   _range = xrange
except NameError:
   _range = range

PAGESIZE = os.sysconf('SC_PAGESIZE')
PROCDIR = '/proc'

stat_attribs = ('flag','nlwp','ppid','pgid','sid','uid','euid','gid', \
	'egid','addr','size','rssize','pad1','ttydev','pctcpu','pctmem','utime', \
	'stime','cutime','cstime','sigtrace','flttrace','sysentry','sysexit','dmodel', \
	'wstat','argc','argv','envp','dmodel','starttime','ctime','time','fname', \
	'cmdline','taskid','projid','nzomb','poolid','zoneid','contract')

class _SunProc(object):
    """Why does everything in solaris have to feel so obtuse. 
       Don't get me wrong I like solaris, but this is bullshit!!!

       wrap the structured binary files in proc on solaris

       i hope procfs is in memory, b/c we read this a lot
    """
    def __init__(self):
        #format of time struct
        self._timeStruct = "@iL"
        #/usr/include/sys/procfs.h, defines these
        self._lwpsinfo_t = [
            "@iiIIcccchcciHH",
            self._timeStruct,
            self._timeStruct,
            "@iiii",
        ]
        self._pstatus_t = [
            "@iiiiiiiiiIiIi",
            self._timeStruct,
            self._timeStruct,
            self._timeStruct,
            self._timeStruct,
            "@iiiic",
            "@3c",		#padding skip
            "@iiii"
            "@15i",		#unused as of 20110214 - skip
#            self._lwpsinfo_t,	#i don't feel like implementing this
        ]
        self._psinfo_t = [
            "@iiiiiiiiiiIiiiIHH",
            self._timeStruct,
            self._timeStruct,
            self._timeStruct,
            "@16c",		#PRFNSZ = 16
            "@80c",		#PRARGSZ = 80
            "@iiIIc",
            "@3c",		#padding skip
            "@iiiiii", 
#            "@2i",		#unused as of 20110214
#            self._lwpsinfo_t,	#i don't feel like implementing this
        ]

        #maps the structure of a procfile
        #status is readable by the owner
        #psinfo is world readable
        self.mapProcFiles = {
            'status': {
                 'T': self._pstatus_t, 
                 0: None, #use psinfo ('flags','nlwp','pid','ppid','pgid','sid','aslwpid','agentid','sigpend', 'brkbase','brksize','stksize','stkbase'),
                 1: ('utime',),
                 2: ('stime',),
                 3: ('cutime',),
                 4: ('cstime',),
                 5: ('sigtrace','flttrace','sysentry','sysexit','dmodel'),
                 6: None,
                 7: None, #use psinfo ('taskid','projid','nzomb','zoneid'),
                 8: None,
            },
            'psinfo' : {
                 'T': self._psinfo_t,
                 0: ('flag','nlwp','pid','ppid','pgid','sid','uid','euid', \
                     'gid','egid','addr','size','rssize','pad1','ttydev', \
                     'pctcpu','pctmem'),
                 1: ('starttime',),
                 2: ('time',),
                 3: ('ctime',),
                 4: ('fname',),
                 5: ('cmdline',),
                 6: ('wstat','argc','argv','envp','dmodel'),
                 7: None,
                 8: ('taskid','projid','nzomb','poolid','zoneid','contract')
            }
        }

    def readFile(self,f):
        if f in self.mapProcFiles:
            return self.__decode_struct(f)
        return open('%s/%s' % (self.path,f)).read()

    def __decode_struct(self, filename):
        """I hate this method!!!"""
        stat = {}
        T = None
        MagicDecoderRing = self.mapProcFiles[filename] 
        try:
            statusFile = open(self.path+'/'+filename)
            for i in _range(0,len(MagicDecoderRing['T'])):
                size_t = struct.calcsize(MagicDecoderRing['T'][i])
                T = struct.unpack(MagicDecoderRing['T'][i],statusFile.read(size_t))
                #None represents padding and should be skipped 
                if MagicDecoderRing[i] is not None:
                    #items with one to one attributes
                    if len(T) == len(MagicDecoderRing[i]):
                        for x in _range(0,len(T)):
                            stat[MagicDecoderRing[i][x]] = T[x]
                    #timestruc_t items below here
                    elif type(T[0]) is int:  
                        stat[MagicDecoderRing[i]] = self._nanosec2dec(T)
                    #must be a string ... err character array
                    elif type(T[0]) is str:
                        #worst list comprehension ever!!!!
                        stat[MagicDecoderRing[i]] = \
                                [b for b in ' '.join([a for a in \
                                ''.join(list(T)).split('\x00') \
                                if a != '']).split(' ') if b != ''] 
            statusFile.close()
        except: pass
        return stat 

    def _nanosec2dec(self, timetup=(0,0)):
        return timetup[0]+timetup[1]*0.000000001


class Process(_SunProc):
    """base class for processes"""
    implements(IKittProcess)

    running = property(lambda s: s.isRunning())
    memory = property(lambda s: s.memUsage())
    stats = property(lambda s: s.getStats())
    environ = property(lambda s: s.getEnv())
    threads = property(lambda s: len(s.getTasks()))
    fd_count = property(lambda s: len(s.getFD()) or 3)

    def __init__(self, pid):
        self.pid = int(pid)
        self.path = "%s/%d" % (PROCDIR,int(self.pid))
        if not os.path.isdir(self.path):
            #this exception is injected into the module on import
            raise InvalidProcess("Invalid PID (%s)" % pid)
        self.inode = os.stat(self.path).st_ino
        _SolProc.__init__(self)

    def isRunning(self):
        """is a process running
           @return (bool)
        """
        try:
            if self.pid > 0:
                #in case the process is an unreaped child
                os.waitpid(self.pid, os.WNOHANG)
        except: pass
        try: return os.stat(self.path).st_ino == self.inode
        except: return False

    def waitForDeath(self,timeout=10,delay=0.25):
        """wait for process to die

           @return (bool)
        """
        while timeout > 0:
            if not self.isRunning(): return True
            time.sleep(delay)
            timeout -= delay
        return False

#FIXME
    def getEnv(self):
        """the environment settings from the processes perpective,
           @return (dict)
        """
        env = {}
        return env

    def getFD(self):
        """Get all open file descriptors
           @return (dict)
        """
        fd = {}
        try: #can't decide if we should 'path' or 'fd'
            for link in os.listdir('%s/fd' % self.path):
                try: fd[link] = os.readlink('%s/fd/%s' % (self.path,link))
                except: pass
        except: pass
        return fd

    def getTasks(self):
        """Get all open tasks/threads
           @return (set)
        """
        try:
            taskDir = os.path.join(self.path,'lwp')
            if os.path.exists(taskDir): return set( map(int,os.listdir(taskDir)) )
            else: return set()
        except: return set()


    def getStats(self):
        """Get the process' stats
           @return (dict)
        """
        #get first dictionary
        x = self.readFile('psinfo')
        #get second dictionary
        y = self.readFile('status')
        #update first with contents of second
        return dict(x, **y)

    def memUsage(self):
        """Get the process' stats
           @return (dict)
        """
        if not hasattr(self, 'size'):
            size = self.readFile('psinfo')['size']
            self.size = size
        return (self.size * 1024) #b/c it is in Kb

    def __str__(self):
        return '%s(pid=%d)' % (self.__class__.__name__,self.pid)
    __repr__ = __str__


class ProcessSnapshot(Process):
    """Snapshot of process information"""
    implements(IKittProcessSnapshot)
    def __init__(self,*args):
        Process.__init__(self,*args)
        self.update()

    def update(self):
        """Update the snapshot"""
        vars(self).update(self.getStats())
        self.cwd = os.readlink('%s/path/cwd' % self.path)
        self.environ = self.getEnv()
        self.exe = self.fname[0] 
        self.fd = self.getFD()
        self.tasks = self.getTasks()
        self.root = os.readlink('%s/path/root' % self.path)


class LiveProcess(Process):
    """Get realtime access to process information"""
    implements(IKittLiveProcess)
    def __init__(self,pid,fast=False):
        Process.__init__(self,pid)
        #Creates dummy attribs for user friendliness unless fast=True is specified
        if not fast:
            other_attribs = ('cwd','environ','exe','fd','root','tasks')
            dummyAttrs = dict([(a,self.__getattribute__(a)) for a in \
                    stat_attribs + other_attribs])
            vars(self).update(dummyAttrs)
        self.cpuTime = self.__cpuSnapShot()

    def __times(self):
        """Returns seconds of system and user times"""
        return (self.utime, self.stime)

    def cpuUsage(self):
        """Returns a dictionary of system and user cpu utilization in terms 
           of percentage used
           @return (dict)
        """
        baseline = self.cpuTime
        self.cpuTime = self.__cpuSnapShot()
        u = (self.cpuTime[0] - baseline[0]) / (self.cpuTime[2] - baseline[2])
        s = (self.cpuTime[1] - baseline[1]) / (self.cpuTime[2] - baseline[2])
        return {
            'user_util' : 100 * u,
            'sys_util' : 100 * s,
        }

    def __cpuSnapShot(self): #FIXME probably, not tested enough
        return self.__times() + tuple( [ (time.time() - self.time) ] )

    def __getattribute__(self,attr):
        if attr == 'cwd':
            try: return os.readlink('%s/cwd' % self.path)
            except: return None
        elif attr == 'environ': return self.getEnv()
        elif attr == 'exe': self.fname[0]
        elif attr == 'fd': return self.getFD()
        elif attr == 'tasks': return self.getTasks()
        elif attr == 'cwd':
            try: return os.readlink('%s/path/cwd' % self.path)
            except: return None
        elif attr == 'root':
            try: return os.readlink('%s/path/root' % self.path)
            except: return None
        elif attr in stat_attribs: 
            try: return self.getStats()[attr]
            except: pass 
        else: return object.__getattribute__(self,attr)

###############################################################################
# Platform specific api methods
###############################################################################
def listProcesses():
    """Returns a list of PID's"""
    return [int(p) for p in os.listdir(PROCDIR) if p.isdigit()]


def findProcesses(s):
    """Finds Process ID by pattern"""
    res = []
    regex = re.compile(s,re.I)
    for pid in listProcesses():
        try:
            p = LiveProcess(pid,fast=True)
            cmd = ' '.join(p.cmdline)
            match = regex.search(cmd)
            if match: res.append((p,match))
        except: continue
    if res:
        return dict(res)
    return {}


def findThreadIds(s='.*'):
    """Finds Threads ID by pattern"""
    procs = findProcesses(s).keys()
    tids = set()
    for p in procs:
        for tid in p.tasks:
            tids.add(tid)
    return tids 


def isRunning(pid):
    """is a given process id running, returns Boolean"""
    return bool(os.path.exists('%s/%d' % (PROCDIR,int(pid))))

#FIXME
def cpuStats():
    """Returns a dictionary of cpu stats"""
    return {}

#FIXME
def cpuTotalTime():
    """Returns Total CPU Time Used in seconds"""
    return float()

#no new attributes, methods, or classes to expose
__all__ = []
