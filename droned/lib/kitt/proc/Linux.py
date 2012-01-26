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

import sys, os, re, time, platform
#all backends need to import these at minimum
from kitt.interfaces import IKittProcModule, IKittProcess, \
        IKittProcessSnapshot, IKittLiveProcess, implements, moduleProvides

if platform.system() != 'Linux':
    raise OSError("Sorry, only Linux is supported")

__author__ = 'CMDavis' #correct me if i am wrong
__doc__ = """Best supported kitt.proc platform specific implemenations
I believe the original implementation author was Chris M. Davis.  The
zope interfaces are designed around this implementation.
"""

#last updated by Justin Venus 2011-12-08
moduleProvides(IKittProcModule)

_release = platform.release()
#supported linux kernels
KERNEL24 = _release.startswith('2.4')
KERNEL26 = _release.startswith('2.6')
KERNEL3x = _release.startswith('3.') #hopefully this remains true

PROCDIR = '/proc'
STATES = {
    'R': 'Running',
    'S': 'Sleeping (interruptable)',
    'D': 'Sleeping (uninterruptable disk i/o)',
    'Z': 'Zombie',
    'T': 'Traced (or stopped on a signal)',
    'W': 'Paging',
}
PAGESIZE = os.sysconf('SC_PAGESIZE')
JIFFIES_PER_SECOND = os.sysconf('SC_CLK_TCK')

stat_attribs = ('comm','state','ppid','pgrp','session','tty_nr','tpgid','flags', \
           'minflt','cminflt','majflt','cmajflt','utime','stime','cutime', \
           'cstime','priority','nice','unused','itrealvalue','starttime', \
           'vsize','rss','rlim','startcode','endcode','startstack', \
           'kstkesp','kstkeip','signal','blocked','sigignore','sigcatch', \
           'wchan','nswap','cnswap','exit_signal','processor', \
           'rt_priority','policy')

###############################################################################
# platform specific class methods
###############################################################################
class Process(object):
    """base class for processes"""
    implements(IKittProcess)

    running = property(lambda s: s.isRunning())
    memory = property(lambda s: s.memUsage())
    stats = property(lambda s: s.getStats())
    environ = property(lambda s: s.getEnv())
    threads = property(lambda s: len(s.getTasks()))
    fd_count = property(lambda s: len(s.getFD()) or 3)

    def __init__(self,pid):
        self.pid = int(pid)
        self.path = "%s/%d" % (PROCDIR,pid)
        if not os.path.isdir(self.path):
            self.path = "%s/.%d" % (PROCDIR,pid) #For kernel 2.4 threads
            if not os.path.isdir(self.path):
                #this exception is injected into the module on import
                raise InvalidProcess("Invalid PID (%s)" % pid)
        self.inode = os.stat(self.path).st_ino

    def readFile(self,f):
        return open('%s/%s' % (self.path,f)).read()

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

    def getEnv(self):
        """the environment settings from the processes perpective,
           @return (dict)
        """
        env = {}
        try: envlist = self.readFile('environ').split('\000')
        except: return env
        for e in envlist:
            if '=' in e:
                k,v = e.split('=',1)
            else:
                k,v = e,''
            k,v = k.strip(),v.strip()
            if not k: continue
            env[k] = v
        return env

    def getFD(self):
        """Get all open file descriptors
           @return (dict)
        """
        fd = {}
        try:
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
            if KERNEL26 or KERNEL3x:
                taskDir = os.path.join(self.path,'task')
                if os.path.exists(taskDir):
                    return set( map(int,os.listdir(taskDir)) )
                else: return set()
            else:
                my_pid = self.pid #Attribute lookup is heavy for LiveProcess's
                my_threads = set()
                for entry in os.listdir(PROCDIR):
                    if entry[0] != '.': continue
                    try:
                        pid = int( entry[1:] )
                        thread = LiveProcess(pid, fast=True)
                        if thread.tgid == my_pid:
                            my_threads.add(pid)
                    except: pass
                return my_threads
        except: pass
        return set()

    def getStats(self):
        """Get the process' stats
           @return (dict)
        """
        stats = {}
        statstr = self.readFile('stat')
        begin,end = statstr.find('('),statstr.rfind(')')
        comm = statstr[begin+1:end]
        statlist = [comm] + statstr[end+2:].split(' ')
        for i in range(len(stat_attribs)):
            try: stats[stat_attribs[i]] = int(statlist[i])
            except:
                try: stats[stat_attribs[i]] = statlist[i]
                except IndexError:
                    pass #2.4 kernels don't have last 2 stat_attribs
        return stats

    def memUsage(self):
        """Returns resident memory used in bytes
           @return (int)
        """
        return int(self.rss * PAGESIZE)

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
        stats = os.stat(self.path)
        self.uid = stats.st_uid
        self.gid = stats.st_gid
        self.cmdline = self.readFile('cmdline').split('\000')[:-1]
        try: self.cwd = os.readlink('%s/cwd' % self.path)
        except: self.cwd = None
#        self.environ = self.getEnv()
        try: self.exe = os.readlink('%s/exe' % self.path)
        except: self.exe = None
        self.fd = self.getFD()
        self.tasks = self.getTasks()
        try: self.root = os.readlink('%s/root' % self.path)
        except: self.root = None
        self.tgid = int( self.readFile('status').split('Tgid:',1)[1].split(None,1)[0] )
        vars(self).update(self.getStats())


class LiveProcess(Process):
    """Get realtime access to process information"""
    implements(IKittLiveProcess)
    def __init__(self,pid,fast=False):
        """Represents the /proc entries for a process, values are read 
           each time you access an attribute.
        """
        Process.__init__(self,pid)
        #Creates dummy attribs for user friendliness unless fast=True is specified
        if not fast:
            other_attribs = ('cmdline','cwd','environ','exe','fd','root','tgid')
            dummyAttrs = dict([(a,self.__getattribute__(a)) for a in \
                    stat_attribs + other_attribs])
            vars(self).update(dummyAttrs)
        self.cpuTime = self.__cpuSnapShot()

    def __times(self):
        """Returns seconds of system and user times"""
        return (float(self.utime) / JIFFIES_PER_SECOND,
                float(self.stime) / JIFFIES_PER_SECOND)

    def cpuUsage(self):
        """Returns a dictionary of system and user cpu utilization in terms 
           of percentage used
        """
        baseline = self.cpuTime
        self.cpuTime = self.__cpuSnapShot()
        u = (self.cpuTime[0] - baseline[0]) / (self.cpuTime[2] - baseline[2])
        s = (self.cpuTime[1] - baseline[1]) / (self.cpuTime[2] - baseline[2])
        return {
            'user_util' : 100 * u,
            'sys_util' : 100 * s
        }

    def __cpuSnapShot(self):
        return self.__times() + tuple( [ cpuTotalTime() ] )

    def __getattribute__(self,attr):
        if attr == 'cmdline': return self.readFile('cmdline').split('\000')[:-1]
        elif attr == 'cwd': 
            try: return os.readlink('%s/cwd' % self.path)
            except: return None
        elif attr == 'environ': return self.getEnv()
        elif attr == 'exe':
            try: return os.readlink('%s/exe' % self.path)
            except: return None
        elif attr == 'fd': return self.getFD()
        elif attr == 'tasks': return self.getTasks()
        elif attr == 'root':
            try: return os.readlink('%s/root' % self.path)
            except: return None
        elif attr == 'tgid':
            return int( self.readFile('status').split('Tgid:',1)[1].split(None,1)[0] )
        elif attr in stat_attribs: return self.getStats()[attr]
        elif attr == 'uid': 
            try: return os.stat(self.path).st_uid
            except: return None
        elif attr == 'gid': 
            try: return os.stat(self.path).st_gid
            except: return None
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
        try: #This fails if a process dies after listProcesses but before .comm lookup
            p = LiveProcess(pid,fast=True)
            cmd = ' '.join(p.cmdline)
            if not cmd: cmd = p.comm #cmdline can be blank if process is swapped out
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

def cpuStats():
    """Returns a dictionary of cpu stats"""
    a = [ b for b in [ i for i in open('%s/stat' % PROCDIR).read().split('\n') \
	if i.startswith('cpu ') ][0].split(' ') if b != '' ]
    a.pop(0) #pops off cpu from the list
    #order matters in this list, as new fields are add this list needs updated
    x = [ 
        'user',
        'nice',
        'system',
        'idle',
        'iowait',
        'irq',
        'softirq',
        'steal',
        'guest'
    ]
    if len(a) != len(x):
        while len(a) < len(x): x.pop() #not all entries exist on all systems
        unknown = 0
        while len(x) < len(a): #add unknown for safety
            x.append("unknown%d" % unknown)
            unknown += 1
    #the names in "x" are keys for the dictionary and position is lookup for "a"
    return dict([ (b, int( a[x.index(b)] )) for b in x ])

def cpuTotalTime():
    """Returns Total CPU Time Used in seconds"""
    #throws away the keys and sums cpuStats dictionary
    return float( sum( val for var, val in cpuStats().items()) ) / \
            JIFFIES_PER_SECOND

#no new attributes, methods, or classes to expose
__all__ = []
