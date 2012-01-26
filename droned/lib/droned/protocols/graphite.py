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

try:
    import cPickle as pickle
except ImportError:
    import pickle
from twisted.internet.protocol import Protocol
from twisted.python.failure import Failure
from twisted.protocols.basic import Int32StringReceiver

class GraphiteProtocol(Int32StringReceiver):
    """base protocol for sending metrics to a Graphite Receiver"""
    metric = property(lambda s: s.get_metric())
    def __init__(self, *args, **kwargs):
        self.metricData = args[0]
        self.deferred = args[-1] #deferred must always be the last argument
        self.METRIC_SENT = False

    def get_metric(self):
        raise NotImplemented('you must implement this')

    def connectionMade(self):
        data = self.metric
        if data: #if we don't have data don't write
            self.sendString(data)
            self.METRIC_SENT = True
        self.transport.loseConnection()

    def connectionLost(self, reason):
        if self.deferred.called:
            return
        if not self.METRIC_SENT:
           self.deferred.errback(reason)
        else:
           self.deferred.callback(None)


class PickleEmitter(GraphiteProtocol):
    """Send Graphite Data in Pickle Receiver Format"""
    def get_metric(self):
        return pickle.dumps(self.metricData)


class LineEmitter(GraphiteProtocol):
    """Send Graphite Data in Line Receiver Format"""
    def get_metric(self):
        metrics = []
        for (metric, (value, stamp)) in self.metricData:
            metrics.append("%(metric)s %(value)s %(stamp)d" % locals())
        metrics = '\n'.join(metrics)
        if metrics and not metrics.endswith('\n'):
            metrics += '\n'
        return metrics

__all__ = ['LineEmitter', 'PickleEmitter']
