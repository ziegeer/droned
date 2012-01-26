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

from kitt.interfaces import moduleProvides, IDroneDService
moduleProvides(IDroneDService) #requirement
from kitt.util import dictwrapper
import config

SERVICENAME = 'janitizer'
#default configuration cleanup logs older than 7 days
SERVICECONFIG = dictwrapper({
    'JANITIZE': {
        config.LOG_DIR: [
            ('.*.log.\d+.*', int(7*len(config.AUTOSTART_SERVICES))), 
        ],
    }
})
import os, re, time
from twisted.application.service import Service
from twisted.internet import defer, task
from droned.logging import logWithContext
from kitt.decorators import synchronizedDeferred, deferredAsThread
import copy

__doc__ = """
    config [JANITOR_DICT, AUTOSTART_SERVICES] 

    This service when properly configured will keep the filesystem
    cleaned up when running.


    keep the most recent 10 copies of files that match the pattern
    # files that don't match the pattern are ignored.
    Janitizer.garbage = {
      '/tmp/example1/log/directory' : [  
                                        ( 'foo_[a-z].+\.log.*', 10)
                                      ]
    }
"""

#logging context
log = logWithContext(type=SERVICENAME)

def ageCompare(f1,f2):
    t1 = os.path.getmtime(f1)
    t2 = os.path.getmtime(f2)
    if t1 > t2: return 1
    if t2 == t2: return 0
    if t2 < t2: return -1


class Janitizer(Service):
    minute = property(lambda foo: 60)
    hour = property(lambda foo: 3600)
    day = property(lambda foo: 86400)
    week = property(lambda f: 604800)
    oldfiles = {}
    #get the watch dictionary from romeo
    watchDict = property(lambda s: SERVICECONFIG.wrapped.get('JANITIZE',{}))
    #lock aquired before starting a thread that modifies class state
    busy = defer.DeferredLock()


    def update(self, watchDict):
        """Inspects occurrence for a watchDict parameter and updates
           the internal state of Janitizer

           @param watchDict (dict)

           return None
        """
        #break references
        tmp = copy.deepcopy(self.watchDict)
        tmp.update(watchDict) #apply updates
        SERVICECONFIG.JANITIZE = tmp
        


    #this would have blocked the reactor w/o the thread
    @synchronizedDeferred(busy)
    @deferredAsThread
    def garbageCheck(self):
        """Check for file patterns that are removeable"""
        watchDict = copy.deepcopy(self.watchDict) #use locals for safety
        for directory,garbageList in watchDict.iteritems():
            if not os.path.exists(directory): continue
            for pattern,limit in garbageList:
                #blocking method in a thread
                self.cleanupLinks(directory)
                files = [os.path.join(directory,f) for f in os.listdir(directory) \
                        if re.search(pattern,f)]
                files = sorted(files)
                if len(files) > int(limit):
                    log('These files matched:\n\t%s' % '\n\t'.join(files))
                while len(files) > int(limit):
                    oldfile = files.pop(0)
                    log('Deleting %s' % oldfile)
                    if os.path.islink(oldfile): continue
                    if os.path.isdir(oldfile):
                        for base, dirs, myfiles in os.walk(oldfile, topdown=False):
                            for name in myfiles:
                                os.remove(os.path.join(base, name))
                            for name in dirs:
                                os.rmdir(os.path.join(base, name))
                        os.rmdir(oldfile)
                    else: os.unlink(oldfile)
            #blocking method in a thread
            self.cleanupLinks(directory)


    #this will block the reactor
    def cleanupLinks(self, directory):
        """cleans broken symlinks

           @param directory: (string)
           return list
        """
        files = [os.path.join(directory,f) for f in os.listdir(directory)]
        for f in files[:]:
            if not os.path.exists(f):
                log('Removing broken symlink %s' % f)
                os.unlink(f)
                files.remove(f)
        return files

     
    def clean_old_files(self, directory, age, recurse=True):
        """mark this directory for cleaning at a certain age

           @param directory: (string)
           @param age: (float)
           @param recurse: (bool)

           return None
        """
        self.oldfiles[directory] = (age,recurse)

 
    #this would have blocked the reactor w/o the thread
    @synchronizedDeferred(busy)
    @deferredAsThread
    def clean_elderly(self):
        """clean old files in a thread"""
        for directory in self.oldfiles:
            self.recursive_clean(directory,*self.oldfiles[directory])


    #this will block the reactor
    def recursive_clean(self, directory, age, recurse):
        """recusively clean a directory

           @param directory: (string)
           @param age: (float)
           @param recurse: (bool)

           return bool
        """
        try: data = map(lambda n: os.path.join(directory,n), os.listdir(directory))
        except:
            log('could not find directory %s' % directory)
            return

        for node in data:
            if os.path.isdir(node) and recurse:
                #blocking method in a thread
                empty = self.recursive_clean(node,age,recurse)
                if empty:
                    try: os.rmdir(node)
                    except: log('could not remove directory: %s' % node)
                continue
            if os.path.isdir(node): continue #in case recurse is False
            if (time.time() - os.stat(node).st_mtime) > age:             
                try: os.remove(node)
                except: log('could not remove file: %s' % node)
        return bool(os.listdir(directory))


    def startService(self):
        """Start Janitizer Service"""
        self.GARBAGE_CHECK = task.LoopingCall(self.garbageCheck)
        self.ELDERLY_CHECK = task.LoopingCall(self.clean_elderly)
        #start the service
        Service.startService(self)
        self.GARBAGE_CHECK.start(self.minute * 20)
        self.ELDERLY_CHECK.start(self.minute)


    def stopService(self):
        """Stop All Janitizer Service"""
        try:
            if self.GARBAGE_CHECK.running:
                self.GARBAGE_CHECK.stop()
            if self.ELDERLY_CHECK.running:
                self.ELDERLY_CHECK.stop()
        except: pass
        Service.stopService(self)

# module state globals
parentService = None
service = None

#exported service api 
def update(watchDict):
    global service
    if not running():
        raise AssertionError('janitizer service is not running')
    return service.update(watchDict)


###############################################################################
# API Requirements
###############################################################################
def install(_parentService):
    global parentService
    parentService = _parentService

def start():
    global service
    if not running():
        service = Janitizer()
        service.setName(SERVICENAME)
        service.setServiceParent(parentService)

def stop():
    global service
    if running():
        service.disownServiceParent()
        service.stopService()
        service = None

def running():
    return bool(service) and service.running

__all__ = ['install', 'start', 'stop', 'running']
