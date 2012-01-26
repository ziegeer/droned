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

#api requirements
SERVICENAME = 'graphite'
SERVICECONFIG = dictwrapper({})

__doc__ = """
The graphite services will write all TimeSeriesData models to
a given graphite server.  This service is configured through
romeo.
"""

from twisted.python.log import msg, err
from twisted.python.failure import Failure
from twisted.internet import defer, task
from twisted.application.service import Service
from droned.logging import logWithContext
from droned.models.graphite import TimeSeriesData
from droned.protocols.graphite import PickleEmitter, LineEmitter
import time

log = logWithContext(type=SERVICENAME)

class Graphite(Service):
    writing = defer.succeed(None)
    protocol = property(lambda s: {
            'pickle': PickleEmitter,
            'line': LineEmitter,
            None: None #just being explicit
        }.get(SERVICECONFIG.wrapped.get('GRAPHITE_FORMAT'))
    )
    graphite_host = property(lambda s: SERVICECONFIG.wrapped.get('GRAPHITE_HOST'))
    graphite_port = property(lambda s: int(SERVICECONFIG.wrapped.get('GRAPHITE_PORT',0)))
    graphite_timeout = property(lambda s: float(SERVICECONFIG.wrapped.get('GRAPHITE_TIMEOUT',5.0)))
    graphite_delay_iteration = property(lambda s: float(SERVICECONFIG.wrapped.get('GRAPHITE_DELAY',0)))
    _task = None

    def success(self,result):
        log('Wrote %d metric points' % (result,))
        return result

    def write(self):
        if self.writing.called:
            self.writing = TimeSeriesData.produceAllMetrics(
                    self.graphite_host, self.graphite_port, self.protocol,
                    timeout=self.graphite_timeout,
                    delay=self.graphite_delay_iteration
            )
            self.writing.addCallback(self.success)
        else:
            log('Graphite data is still being written from previous iteration,' + \
                    ' will hold off until next iteration')

    def startService(self):
        if self.graphite_host and self.graphite_port and self.protocol:
            self._task = task.LoopingCall(self.write)
            self._task.start(60.0) #graphite only cares about minutely precision
            Service.startService(self)
        else:
            self.disownServiceParent() #effectively self destruct
            global service
            service = None
            raise AssertionError('%s is not configured' % (SERVICENAME,))

    def stopService(self):
        if self._task and self._task.running: self._task.stop()
        while not self.writing.called:
            time.sleep(1) #block the reactor
        Service.stopService(self)

# module state globals
parentService = None
service = None

###############################################################################
# API Requirements
###############################################################################
def install(_parentService):
    global parentService
    parentService = _parentService

def start():
    global service
    if not running():
        service = Graphite()
        service.setName(SERVICENAME)
        service.setServiceParent(parentService)
        service.startService()

def stop():
    global service
    if running():
        service.stopService()
        service.disownServiceParent()
        service = None

def running():
    global service
    return bool(service) and service.running

__all__ = ['install', 'start', 'stop', 'running']
