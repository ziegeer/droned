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

from zope.interface import Interface,Attribute,implements
from droned.entity import Entity
from twisted.internet import defer, reactor
from twisted.python.failure import Failure
from kitt.decorators import synchronizedDeferred
from kitt.util import dictwrapper
from droned.clients import connect
import time


class IDataPoint(Interface):
    def __init__(self,time_value=None,value=None,meta_data=None): pass
    def __getattr__(self,name): pass
    def __iter__(self): pass
    def items(self):pass
    def set_meta_data(self,name,value):pass
    def update_meta_data(self,other):pass
    def del_meta_data(self,name):pass
    def __contains__(self,item):pass
    
    
class DataPoint(object):
    '''Simple wrapper around the (Time,value) tuple
       adds ability to put meta data on a data point.
       If using DataPoint interface the time recorded by
       TimeSeries data can be controlled by external logic as
       well. By default TimeSeries will record time as the
       time a data point is added to the TimeSeries object.
    '''
    implements(IDataPoint)
    def __init__(self,time_value=None,value=None,meta_data=None):
        '''@param time: <int|float> (epoch time), now if not provided
           @param value: <int|float> value for this data point 0 default
           @param param: <dict> meta data about this data point.
        '''
        if isinstance(time_value,(int,float)): self.time = time_value
        else: self.time = time.time()
        self.time_int = int(self.time)
        if isinstance(value,(int,float)): self.value = value
        else: self.value = 0
        if type(meta_data) == dict: self.meta_data = dictwrapper(meta_data)
        else: self.meta_data = dictwrapper({})
        self._core = {"time":self.time,
                      "time_int":self.time_int,
                      "value":self.value,
                      "meta_data":self.meta_data}
        
    def __getattr__(self,name):
        return self.meta_data.get(name)
    
    def __iter__(self):
        '''support for iteration over this object.
        '''
        out = self._core.keys()[:]
        out += self.meta_data.keys()
        for o in out: yield o
        
    def __contains__(self,item):
        if item in self._core.keys(): return True
        if item in self.meta_data.keys(): return True
        return False
        
    
    def items(self):
        '''same output as dict.items()
        '''
        for k,v in self._core.items():
            yield (k,v)
        for k,v in self.meta_data.items():
            yield (k,v)
    
    def set_meta_data(self,name,value):
        '''add/update a single meta datum on this object
           @param name: name of our meta data item
           @param value: value for that logical name
        '''
        self.meta_data[name] = value
    
    def update_meta_data(self,other):
        '''update multiple/add meta data on this object
           @param other: <dict> map of names/values 
        '''
        if type(other) != dict: return
        self.meta_data.update(other)
        
    def del_meta_data(self,name):
        '''remove a single meta datum from this object\
           @param name: logical name of that target 
        '''
        if name not in self.meta_data: return
        del self.meta_data[name]
        
        

class TimeSeriesData(Entity):
    """A serializable model to store graphite style time series data"""
    metricID = property(lambda s: s._name)
    pending = property(lambda s: bool(s.dataPoints))
    serializable = True #save metrics that haven't been sent yet
    def __init__(self, metricID):
        self._name = metricID
        self.dataPoints = {}
        busy = defer.DeferredLock()
        sync = synchronizedDeferred(busy)
        #protect the storage
        self.add = sync(self.add)
        self.produce = sync(self.produce)
        self.produce_all = sync(self.produce_all)


    def __getstate__(self):
        return {
            'name': self.metricID,
            'data': self.dataPoints
        }


    @staticmethod
    def construct(state):
        metric = TimeSeriesData(state['name'])
        metric.dataPoints = state['data']
        return metric


    def add(self, value):
        """add a metric value to this metric id

           Note: this method is wrapped in a deferred on class instantiation

           @value (int|float)
           @raise AssertionError

           @callback (NoneType)
           @errback (twisted.python.failure.Failure())

           @return defer.Deferred()
        """
        if not isinstance(value, (int,float,DataPoint)):
            errmsg = 'input must be `int` , `float` or `droned.models.graphite.DataPoint`'
            raise AssertionError(errmsg)
        
        #lose some precision on purpose
        updater = self.dataPoints.update
        if type(value) == DataPoint: updater({value.time_int: value.value})
        else: updater({int(time.time()): value})
        


    @defer.deferredGenerator
    def produce(self, host, port, protocol, timeout=5.0):
        """Produce metrics to the endpoint, sends the oldest metric and returns

           Note: this method is wrapped in a deferred on class instantiation

           @param host (string)
           @param port (int)
           @param protocol (class) - twisted.internet.protocol.Protocol
           @param timeout (int|float) - timeout parameter for the protocol

           @callback (int) - how many metrics were sent
           @errback (twisted.python.failure.Failure())

           @return defer.Deferred()
        """
        result = 0
        if self.pending:
            stamp = sorted(self.dataPoints.keys())[0] #send oldest first
            value = self.dataPoints[stamp]
            proto_args = ([(self.metricID, (stamp, value))],)
            proto_kwargs = {'timeout': timeout}
            try:
                d = connect(host, port, protocol, *proto_args, **proto_kwargs)
                wfd = defer.waitForDeferred(d)
                yield wfd
                wfd.getResult()
                result += 1
                del self.dataPoints[stamp] #remove the metric
            except:
                result = Failure()
        yield result
         

    @defer.deferredGenerator
    def produce_all(self, host, port, protocol, timeout=5.0):
        """Produce ALL metrics to the endpoint

           Note: this method is wrapped in a deferred on class instantiation

           @param host (string)
           @param port (int)
           @param protocol (class) - twisted.internet.protocol.Protocol
           @param timeout (int|float) - timeout parameter for the protocol

           @callback (int) - how many metrics were sent
           @errback (twisted.python.failure.Failure())

           @return defer.Deferred()
        """
        result = 0
        if self.pending:
            metrics = set()
            for stamp, value in self.dataPoints.iteritems():
                metrics.add((self.metricID, (stamp, value)))
            proto_args = (list(metrics),)
            proto_kwargs = {'timeout': timeout}
            try:
                d = connect(host, port, protocol, *proto_args, **proto_kwargs)
                wfd = defer.waitForDeferred(d)
                yield wfd
                wfd.getResult()
                result += 1
                self.dataPoints = {} #reset storage
            except:
                result = Failure()
        yield result


    @staticmethod
    @defer.deferredGenerator
    def produceAllMetrics(host, port, protocol, timeout=5.0, delay=0.0):
        """Produce ALL metrics of ALL metricID's to the endpoint with some 
           delay in between.

           @param host (string)
           @param port (int)
           @param protocol (class) - twisted.internet.protocol.Protocol
           @param timeout (int|float) - timeout parameter for the protocol
           @param delay (int|float) - delay between sends

           @callback (int) - how many metrics were sent
           @errback N/A

           @return defer.Deferred()
        """
        result = 0
        for obj in TimeSeriesData.objects:
            while obj.pending:
                try:
                    d = obj.produce_all(host, port, protocol, timeout=timeout)
                    wfd = defer.waitForDeferred(d)
                    yield wfd
                    result += wfd.getResult()
                    if delay:
                        d = defer.Deferred()
                        reactor.callLater(delay, d.callback, None)
                        wfd = defer.waitForDeferred(d)
                        yield wfd
                        wfd.getResult()
                except: pass #swallow errors
        yield result
