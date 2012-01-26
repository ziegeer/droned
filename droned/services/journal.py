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


SERVICENAME = 'journal'
SERVICECONFIG = dictwrapper({
    'JOURNAL_RETENTION': 60,
    'JOURNAL_DIR': '/var/lib/droned/journal',
    'JOURNAL_FREQUENCY': 60,
})

from twisted.python.log import msg
from twisted.python.failure import Failure
from twisted.internet import defer, threads, task, reactor
from twisted.application.service import Service
from droned.entity import Entity
from droned.logging import logWithContext, err
from droned.models.event import Event
import signal
import config
import time
import os
import gc

__doc__ = """
The Journal Service records DroneD's modeled state inorder to preserve the
notion of what is going on in between restarts. This service is considered
as a core component and is configured through ENVIRONMENT configuration.
"""

log = logWithContext(type=SERVICENAME)

SUFFIX = '.pickle'
def list_snapshots():
    return [ name[:-len(SUFFIX)] for name in os.listdir(config.JOURNAL_DIR) \
            if name.endswith(SUFFIX) ]

def load():
    snapshots = sorted( map(int, list_snapshots()) )
    if not snapshots: return
    path = os.path.join(config.JOURNAL_DIR, str(snapshots[-1]) + SUFFIX)
    timestamp = time.ctime(snapshots[-1])
    log('loading %s (%s)' % (path,timestamp))
    journal = open(path, 'rb')
    c = 0
    while True:
        try:
            obj = Entity.deserialize(journal)
        except EOFError:
            journal.close()
            break
        except: err('problem unspooling')
        c += 1
    log('loaded %d objects' % c)


class Journal(Service):
    """This Service is responsible for maintaining DroneD's notion of 
       environmental state.
    """
    writing = defer.succeed(None)

    def write(self, occurence=None):
        """update the journal
           @param occurance - unused place holder for event subscription
        """
        if occurence and occurence.name == 'signal':
            if occurence.signum != signal.SIGTERM: return
            log('Attempting to save journal before shutdown.')
        if self.writing.called:
            self.writing = threads.deferToThread(self.blocking_journal_write)
        else:
            log('Journal is still being written from previous iteration,' + \
                    ' will hold off until next iteration')

    def _journal_failure(self, occurrence):
        badFile = occurrence.journal
        log('File %s is corrupt' % (badFile,))
        os.rename(badFile, badFile+str('_corrupt'))
        log('renaming the file to preserve system history')

    def blocking_journal_write(self):
        if not self._task.running: return #account for lazy task start
        now = int( time.time() )
        snapshot = '%d.pickle' % now
        path = os.path.join(config.JOURNAL_DIR, snapshot)
        outfile = open(path, 'wb')
        c = 0
        for obj in gc.get_objects():
            if isinstance(obj, Entity) and obj.serializable and \
                    obj.__class__.isValid(obj):
                try:
                    data = obj.serialize()
                    outfile.write(data)
                    c += 1
                except:
                    #don't ever reference the ``obj`` in here, it is probably
                    #an invalid Entity and will raise an Exception on access.
                    failure = err('Exception Serializing an Object')
                    Event('journal-error').fire(failure=failure, journal=path)
        outfile.close()
        plural = 's'
        if c == 1: plural = ''
        log('stored %d object%s' % (c,plural))
        old = sorted( map(int, list_snapshots()) )[:-config.JOURNAL_RETENTION]
        for timestamp in old:
            path = os.path.join(config.JOURNAL_DIR, str(timestamp) + SUFFIX)
            os.unlink(path)

    def startService(self):
        self._task = task.LoopingCall(self.write)
        #delay first journaling
        reactor.callLater(
            config.JOURNAL_FREQUENCY, 
            self._task.start, 
            config.JOURNAL_FREQUENCY
        )
        #minimize the chances of losing started instances
        Event('journal-error').subscribe(self._journal_failure)
        Event('instance-started').subscribe(self.write)
        Event('signal').subscribe(self.write)
        Service.startService(self)

    def stopService(self):
        Event('instance-started').unsubscribe(self.write)
        Event('signal').unsubscribe(self.write)
        Event('journal-error').unsubscribe(self._journal_failure)
        if self._task.running: self._task.stop()
        if not self.writing.called:
            self.writing.addBoth(lambda x: Service.stopService(self) and x or x)
            return self.writing #the main service will deal with it
        Service.stopService(self)

# module state globals
parentService = None
service = None

###############################################################################
# API Requirements
###############################################################################
def install(_parentService):
    global parentService
    global SERVICECONFIG
    parentService = _parentService
    for var, val in SERVICECONFIG.wrapped.items():
        setattr(config, var, val)
    #loading historic data must happen before any service starts
    load() #load the historic journal

def start():
    global service
    if not running():
        service = Journal()
        service.setName(SERVICENAME)
        service.setServiceParent(parentService)

def stop():
    global service
    if running():
        service.stopService()
        service.disownServiceParent()
        service = None

def running():
    return bool(service) and service.running

__all__ = ['install', 'start', 'stop', 'running']
