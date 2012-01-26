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

__doc__ = '''
While there are a lot of classes in this file the way the fit together is relatively
straight forward with a little plain English explanation.
High level data flow:
Config > StatBlock [> Protocol ] > OutputHandler
                   [> Protocol ] > OutputHandler
       > StatBLock > ....
Where [> Protocol] represents an optional layer.

StatBlock object:
Represents the STAT: stanza from configuration
Key things to remember when creating a new statBlock class:
* set TYPE to the same string that will be used for the TYPE delaration in config
* ensure PROVIDED_METRICS has a handler for each metric that can be called from config.
* ensure that each metric has a short name and a fully qualified name
* if using protocols (see below) you'll need to make sure your DataPoint conforms or it will be dropped.
* each metric handler function is passed a save() method which it may use to save metrics generated
  in this function. the save() function provides nessesary safety checks to minimize boiler
  plate code in the handler function. 

Protocol object:
This object is an optional part of the hierarchy but may be required by a given output.
The purpose of Protocol objects is similar to that of interfaces. They guarantee presence
of certain named data and type. In reality a protocol can help enforce any schema what
so ever. It is up to the outputHandler to use a Protocol or not.
Specifically protocol objects are currently checking that metadata on a DataPoint
output from a StatBlock object conforms to a required format. I.e. certain keys
are present and they contain values of the right type.

OutputHandler objects:
These represent the final destination for a given set of metrics. They are in charge
of formating metrics output from a parent stat block  to a form that can be used in
their target output, Graphite, Database, flat file, etc.
Because an output handler may be the child of many different types of StatBlock 
parent the protocol exists to ensure some consistency of data format.

'''

   
import time,os,sys
import config
import re

from zope.interface import implements, Interface, Attribute

#the below are common imports you may not have need for them all and likely will need additional.
from twisted.python.failure import Failure
from twisted.python.log import err
from twisted.internet import task
from twisted.internet.task import LoopingCall
from twisted.internet.defer import TimeoutError, deferredGenerator, waitForDeferred, maybeDeferred

#these are typical droned objects. Same as twsited. Common are included but do not reprsent all imports.
#from droned.entity import Entity #Not currently used due to inheritance issues.
from droned.logging import log, debug, err
from droned.models.event import Event
from droned.models.timedefs import Interval
from droned.models.graphite import IDataPoint,DataPoint,TimeSeriesData

#kitt based imports
from kitt.decorators import raises
from kitt.util import ClassLoader
from kitt.numeric.vectors import SimpleVectorTransformLoader, VectorTransform 

try:
    import psutil
    SYSSTAT_PSUTIL_AVAILABLE=True
except:
    log("Unable to import psutil. `OS` related Stats will NOT be collected.")
    log("Consider installing psutil for your platform via: http://code.google.com/p/psutil/downloads/list")
    SYSSTAT_PSUTIL_AVAILABLE=False
 

class InvalidStatBlockDefinition(Exception):pass
class InvalidOutputBlockDefinition(Exception):pass

class IStatBlock(Interface):
    TYPE = Attribute("<string> name of STAT>TYPE block this object supports/backs.")
    
    PROVIDED_METRICS = Attribute("<dict:{string:callable}> short names of all metrics supported by this block")
    REQUESTED_METRICS = Attribute("<list:string> short names of all metrics supported by this block")
    COLLECT_INTERVAL = Attribute("<droned.models.timedefs.Interval> amount of time to wait between stat checks.")
    OUTPUT_INTERVAL = Attribute("<droned.models.timedefs.Interval> amount of time to wait between stat outputs.")
    AGGREGATION_METHOD = Attribute("<droned.models.timedefs.Interval> amount of time to wait between stat outputs.")
    OUTPUTS = Attribute("<list:droned.models.systemstats.IStatOutputHander> list outputs for this block")
    
    def __init__(block):
        '''@param bock: the STAT configuration block.
           @return: StatBlock instance
        '''
        pass
    
    def collect():
        '''collects statistics from specified sources.'''
        pass
    
    def output():
        '''this is called every OUTPUT_INTERVAL seconds'''
        pass
    
    def on_save(datapoint):
        '''this method is called every time 'datapoint_save' event
           is fired. Sub classes may also register other methods
           to handle this event but this method will always be called.
        '''
        pass
    def remove_invalid_request_metrics():
        '''a utility function to help clean up
           metrics requested by a user. All metrics
           our StatBlock cannot satisfy are 
           removed from the requested metrics
           list. Use is optional other functions
           touching requested metrics perform
           needed checks. 
        '''
        pass
    
    def after_aggregation(datapoint):
        '''called after aggregation as name implies.
           the purpose of this function is to allow
           any normalization of meta data that must be
           in lock step with the value of a datapoint.
           datapoint value may have been changed as a result
           of the aggregation phase and metadata may need
           to be updated as a result as well. subclasses
           of type IStatBlock should implemented this method
           to adjust meta data as needed. no return value is
           expected, just modify datapoint in place.
        '''
        pass
    
    def disable_collect():
        '''disables the collect task. on by default
        '''
        pass
        
    def enable_collect():
        '''enables the collect task. on by default
        '''
        pass
    
    def disable_output():
        '''disables the output task. on by default
        '''
        pass
        
    def enable_output():
        '''enable the output task. on by default
        '''
        pass
    
        
class StatBlockLoader(ClassLoader):
    interface_type = IStatBlock
    subloaders = []
    
class StatBlock(object):
    '''Base representation for a stat block of config related to systemstats service.
       see systemstats service for full doc.
       @Event datapoint_save: Datapoint=Datapoint object, fires during save process.
    '''
    implements(IStatBlock)
    TYPE = "null"
    
    @raises(InvalidStatBlockDefinition)
    def __init__(self,block):
        '''all CAPS variables are explained in systemstats service doc
           #1 REQUESTED_METRICS is a map of metric names to supply func
              this func should return a numeric value for the metric in
              question for its value NOW. 
        '''
        self.config_block = block
        self.PROVIDED_METRICS = {} #1
        self.REQUESTED_METRICS = []
        self.COLLECT_INTERVAL = Interval(block.get("COLLECT_INTERVAL","60s"))
        self.OUTPUT_INTERVAL = Interval(block.get("OUTPUT_INTERVAL","60s"))
        self.OUTPUTS = []
        self.PROTOCOLS = [BasicMetaData()]
        self.AGGREGATION_METHOD = self.get_aggregator(block.get('AGGREGATION_METHOD',"none"))
        self.requested_metric_data = {} #holds the intermediate data
        #let the fun begin
        self.REQUESTED_METRICS = block['METRICS']
        self.collect_task = task.LoopingCall(self.collect)
        self.collect_task.start(self.COLLECT_INTERVAL.seconds,False)
        self.output_task = task.LoopingCall(self.output)
        self.output_task.start(self.OUTPUT_INTERVAL.seconds,False)
        self.current_log_level = "info"
        self.log_levels = ("debug","info","debug")
        outputs = []
        for OUTPUT in block['OUTPUTS']:
            if 'OUTPUT' in OUTPUT:
                outputs.append(OUTPUT['OUTPUT'])
        output_handlers = StatOutputHandlerLoader.load()
        for o in outputs:
            for h in output_handlers:
                if h.OUTPUT_TYPE == o['TYPE']:
                    try: self.OUTPUTS.append(h(o,self))
                    except:
                        self.info("There was a error loading the below output block in the provided stat block.")
                        self.error("Output block: %s" % str(o))
                        self.error("Stat block: %s" % str(self.config_block))
                        self.debug("") 
                    break
                
    def set_log_level(self,level):
        if level in self.log_levels:
            self.current_log_level = level
    
    def info(self,msg):
        log(msg)
        
    def error(self,msg):
        gaurd = ("error","debug")
        if self.current_log_level in gaurd: self.info(msg)
        else: return
        try:
            f = Failure()
            log("error: %s" % f.value)
        except: pass
        
    def debug(self,msg):
        if self.current_log_level == "debug": self.error(msg)
        else: return
        try:
            err("Stack Trace:")
        except: pass
    
    def output(self):
        '''This is called every OUTPUT_INTEVAL seconds. This method
           is responsible for summarizing all collected stats as 
           needed and then making the output available to every
           output object in self.OUTPUTS. each object in self.OUTPUTS
           is called as so for o in self.OUTPUTS: o.do_output().
           `o` is expected to already have a reference to this stat
           object and may call back into stat object for whatever
           state it needs to format and send output data.
        '''
        self.aggregate_data()
        for o in self.OUTPUTS:
            try: o.do_output()
            except:
                self.error("Error loading datapoint")
                self.debug("")
        self.clear_data()
    
    def collect(self):
        '''This is called every COLLECT_INERVAL seconds. This method
           is responsible for collecting all the data points from all
           valid requested metrics. Those data points are stored in
           the requested_metric_data object to be shipped off to one
           or more outputs after OUTPU_INTERVAL seconds.
           #1 fully qualified name of provided metric from config
           #2 short name of metric in case fqn was given
           #3 actual name we found (hopefuly) in provided_metrics 
              to match up logic of request(config) and provide(code) sides.
        '''
        pm = self.PROVIDED_METRICS
        for m in self.REQUESTED_METRICS:
            fqn = self.TYPE + "." + m #1
            sn = ".".join( m.split(".")[1:] ) #2
            matched_name = None #3
            for n in [m,fqn,sn]:
                if n in pm:
                    matched_name = n
                    break
            if not matched_name: continue
            try: 
                if matched_name not in self.requested_metric_data:
                    self.requested_metric_data[matched_name] = []
                collected_metrics = self.requested_metric_data[matched_name]
                handler = pm[matched_name]
                def save(data_point):
                    '''this allows us to ensure output consistency'''
                    err = "Invalid return type got %s expected IDataPoint"
                    assert IDataPoint.implementedBy(data_point.__class__), err % type(data_point)
                    self.on_save(data_point)
                    if not self.validate_protocols(data_point): return
                    Event('datapoint_save').fire(datapoint=data_point)
                    collected_metrics.append(data_point)
                    self.save_diag_output(data_point)
                handler(save)
            except:
                err = Failure().value
                fn = pm[matched_name].__name__
                self.error("Error while loading data point via %s" % fn)
                self.debug("")
                continue
        #perform exit clean up of any empty metrics.
        nulls =[k for k,v in self.requested_metric_data.items() if not v ]
        for null in nulls: del self.requested_metric_data[null]
    
    def save_diag_output(self,datapoint):
        '''this method is used to augment diagnostic statements
           around datapoints during the save process. 
        '''
        dpID = id(datapoint)
        self.error("Saving datapoint with unique ID: %s" % dpID)
        self.debug("datapoint[%s] - value = %s" % (dpID,datapoint.value) )
        self.debug("datapoint[%s] - time = %s" % (dpID,datapoint.time) )
        self.debug("datapoint[%s] - metadata:" % dpID)
        for k,v in datapoint.meta_data.items():
            self.debug("datapoint[%s] -\t %s = %s" % (dpID,k,v))
        
    
    def disable_collect(self):
        '''disables the collect task. on by default
        '''
        self.collect_task.stop()
        
    def enable_collect(self):
        '''enables the collect task. on by default
        '''
        self.collect_task.start(self.COLLECT_INTERVAL.seconds)
    
    def disable_output(self):
        '''disables the output task. on by default
        '''
        self.output_task.stop()
        
    def enable_output(self):
        '''enable the output task. on by default
        '''
        self.output_task.start(self.OUTPUT_INTERVAL.seconds)
             
    def on_save(self,datapoint):
        '''this method is called while a datapoint is being saved
           in requested_metric_data. Represents a hook to add or
           modify metadata on a datapoint.
        '''
        datapoint.variables.append("hostname")
        datapoint.meta_data['hostname'] = config.HOSTNAME
        datapoint.variables.append("stat")
        datapoint.meta_data['stat'] = self
        datapoint.meta_data.get("")
        
    def clear_data(self):
        '''thank goodness for memory mgt '''
        self.requested_metric_data = {}
            
    def aggregate_data(self):
        updates = {}
        for metric,datapoints in self.requested_metric_data.items():
            values = [d.value for d in datapoints]
            values = self.AGGREGATION_METHOD.compute(values)
            if len(values) > len(datapoints): 
                output_array = self.fill_meta_data(datapoints,values)
            elif len(values) < len(datapoints): 
                output_array = self.merge_meta_data(datapoints,values)
            else: 
                for d,v in zip(datapoints,values): d.value = v
                output_array = datapoints
            for o in output_array:
                o.meta_data_validator(o)
            updates[metric] = output_array
        self.requested_metric_data.update(updates)
        
    def after_aggregation(self,datapoint):
        return None
        
    def fill_meta_data(self,datapoints,values):
        '''values grew during aggregation. use last datapoint
           as template to make new datapoints for extra values.
        '''
        diff = len(datapoints) - len(values)
        last = datapoints[-1]
        for value in values[diff:]:
            datapoints.append(DataPoint(value=value,meta_data=last.meta_data.copy()))
        return datapoints
        
    def merge_meta_data(self,datapoints,values):
        '''values shrank during aggregation. this is expected.
           merge all meta data fields and return the last
           len(values) datapints with the updated meta data
           and values.
        '''
        diff = len(datapoints) - len(values)
        rest = datapoints[diff:]
        updates = {}
        for d in datapoints:
            updates.update(d.meta_data)
            for d,v in zip(rest,values):
                d.value = v
                d.meta_data.update(updates)
        return rest
    
    def remove_invalid_request_metrics(self):
        '''see interface for doc.
        '''
        ml = len(self.REQUESTED_METRICS)
        for i in range(ml):
            m = self.REQUESTED_METRICS[i]
            sn = ".".join(m.split(".")[1:])
            if m in self.PROVIDED_METRICS: continue
            if sn in self.PROVIDED_METRICS: continue
            index = self.REQUESTED_METRICS.index(m)
            del self.REQUESTED_METRICS[index]
            
    def get_aggregator(self,agname):
        '''chooses vector transform object based
           on type variable of the transform
           and the provided name user chose in
           config.
        '''
        ags = SimpleVectorTransformLoader.load()
        for a in ags:
            if a.TYPE == agname:
                return a()
        return VectorTransform()
        
    def validate_protocols(self,datapoint):
        for p in self.PROTOCOLS:
            if not p.conforms(datapoint):
                msg = "datapoint captured in usage_percent does not conform "
                msg += "to protocol %s" % p
                self.error(msg)
                return False
        return True
       
        
class DiskStat(StatBlock):
    TYPE = "disk"
    
    @raises(InvalidStatBlockDefinition)
    def __init__(self,block):
        global SYSSTAT_PSUTIL_AVAILABLE
        if not SYSSTAT_PSUTIL_AVAILABLE: 
            msg = "%s STAT block is unavailable " % self.TYPE
            msg += "due to missing requirement: psutil module"
            raise Exception(msg)
        StatBlock.__init__(self,block)
        self.PARTITIONS = block['PARTITIONS']
        self.PROVIDED_METRICS.update({
            "usage.percent":self.usage_percent,
            "usage.free":self.usage_free,
            "usage.total":self.usage_total,
            "usage.used":self.usage_used,
            "counters.read":self.counters_read,
            "counters.write":self.counters_write,
            "bytes.read":self.bytes_read,
            "bytes.write":self.bytes_write,
            "time.read":self.time_read,
            "time.write":self.time_write})
        self.PROTOCOLS += [DiskStatMetaData()]
        self.remove_invalid_request_metrics()
       
    def format_partition(self,partition):
        sep = os.path.sep
        if partition == sep: return "FS_ROOT"
        if partition.startswith(sep): partition = partition[1:]
        if partition.endswith(sep):partition = partition[:-1]
        return partition.replace(sep,"_")
    
    def aggregate_data(self):
        '''disk data represents a special case and we need to do a
           custom aggregation as a result. even though a metric
           requested may be the same, example usage.percent
           that metric will have multiple partitions and should
           be treated as different metrics. so we need to aggregate
           by partition and metric type. 
        '''
        partition_groups = {}
        for metric,datapoints in self.requested_metric_data.items():
            for datapoint in datapoints:
                mpID = metric + "::" + datapoint.partition
                if mpID not in partition_groups:
                    partition_groups[mpID]  = []
                partition_groups[mpID].append(datapoint)
        self.requested_metric_data = partition_groups
        StatBlock.aggregate_data(self)
        
    def partition_map(self,name,func):
        pmask = [a.mountpoint for a in psutil.disk_partitions()]
        for partition in self.PARTITIONS:
            if partition not in pmask: continue
            try: func(partition)
            except:
                msg = "Error while processing %s" % name
                self.error(msg)
                self.debug("")
    
    def get_disk_by_partition(self,partition):
        disks = psutil.disk_io_counters(perdisk=True).keys()
        findID = ""
        for p in psutil.disk_partitions():
            if p.mountpoint != partition: continue
            findID = p.device.split("/")[-1]
            if findID in disks: break 
            if "VolGroup" in p.device or "LogVol" in p.device:
                findID = "dm-" + p.device[-1]                 
                if findID in disks: break
        return findID
            
    def usage_percent(self,save):
        '''captures percent used for some disk partition
        '''
        def _validate(datapoint):
            datapoint.meta_data['disk.usage.percent'] = datapoint.value
            datapoint.meta_data['usage.percent'] = datapoint.value
            
        def _run(partition):
            pobj = psutil.disk_usage(partition)
            meta = {"variables": ["partition","disk.usage.percent","usage.percent"],
                    "partition":self.format_partition(partition),
                    "disk.usage.percent":pobj.percent,
                    "usage.percent":pobj.percent,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=pobj.percent,meta_data=meta)
            save(dp)
        self.partition_map("disk.usage.percent", _run)
        
    def usage_free(self,save):
        def _validate(datapoint):
            datapoint.meta_data['disk.usage.free'] = datapoint.value
            datapoint.meta_data['usage.free'] = datapoint.value
            
        def _run(partition):
            pobj = psutil.disk_usage(partition)
            meta = {"variables": ["partition","disk.usage.free","usage.free"],
                    "partition":self.format_partition(partition),
                    "disk.usage.free":pobj.free,
                    "usage.free":pobj.free,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=pobj.free,meta_data=meta)
            save(dp)
        self.partition_map("disk.usage.free", _run)
        
    def usage_total(self,save):
        def _validate(datapoint):
            datapoint.meta_data['disk.usage.total'] = datapoint.value
            datapoint.meta_data['usage.total'] = datapoint.value
         
        def _run(partition):
            pobj = psutil.disk_usage(partition)
            meta = {"variables": ["partition","disk.usage.total","usage.total"],
                    "partition":self.format_partition(partition),
                    "disk.usage.total":pobj.total,
                    "usage.total":pobj.total,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=pobj.total,meta_data=meta)
            save(dp)
        self.partition_map("disk.usage.total", _run)
        
    def usage_used(self,save):
        def _validate(datapoint):
            datapoint.meta_data['disk.usage.used'] = datapoint.value
            datapoint.meta_data['usage.used'] = datapoint.value
         
        def _run(partition):
            pobj = psutil.disk_usage(partition)
            meta = {"variables": ["partition","disk.usage.used","usage.used"],
                    "partition":self.format_partition(partition),
                    "disk.usage.used":pobj.used,
                    "usage.used":pobj.used,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=pobj.used,meta_data=meta)
            save(dp)
        self.partition_map("disk.usage.used", _run)
        
    def counters_read(self,save):
        disk_stats = psutil.disk_io_counters(perdisk=True) 
        def _validate(datapoint):
            datapoint.meta_data['disk.counters.read'] = datapoint.value
            datapoint.meta_data['counters.read'] = datapoint.value
         
        def _run(partition):
            disk = self.get_disk_by_partition(partition)
            pobj = disk_stats[disk]
            meta = {"variables": ["partition","disk","disk.counters.read","counters.read"],
                    "partition":self.format_partition(partition),
                    "disk": disk,
                    "disk.counters.read":pobj.read_count,
                    "counters.read":pobj.read_count,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=pobj.read_count,meta_data=meta)
            save(dp)
        self.partition_map("disk.counters.read", _run)
        
    def counters_write(self,save):
        disk_stats = psutil.disk_io_counters(perdisk=True) 
        def _validate(datapoint):
            datapoint.meta_data['disk.counters.write'] = datapoint.value
            datapoint.meta_data['counters.write'] = datapoint.value
         
        def _run(partition):
            disk = self.get_disk_by_partition(partition)
            pobj = disk_stats[disk]
            meta = {"variables": ["partition","disk","disk.counters.write","counters.write"],
                    "partition":self.format_partition(partition),
                    "disk": disk,
                    "disk.counters.write":pobj.write_count,
                    "counters.write":pobj.write_count,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=pobj.write_count,meta_data=meta)
            save(dp)
        self.partition_map("disk.counters.write", _run)
        
    def bytes_read(self,save):
        disk_stats = psutil.disk_io_counters(perdisk=True) 
        def _validate(datapoint):
            datapoint.meta_data['disk.bytes.read'] = datapoint.value
            datapoint.meta_data['bytes.read'] = datapoint.value
         
        def _run(partition):
            disk = self.get_disk_by_partition(partition)
            pobj = disk_stats[disk]
            meta = {"variables": ["partition","disk","disk.bytes.read","bytes.read"],
                    "partition":self.format_partition(partition),
                    "disk": disk,
                    "disk.bytes.read":pobj.read_bytes,
                    "bytes.read":pobj.read_bytes,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=pobj.read_bytes,meta_data=meta)
            save(dp)
        self.partition_map("disk.bytes.read", _run)
        
    def bytes_write(self,save):
        disk_stats = psutil.disk_io_counters(perdisk=True) 
        def _validate(datapoint):
            datapoint.meta_data['disk.bytes.write'] = datapoint.value
            datapoint.meta_data['bytes.write'] = datapoint.value
         
        def _run(partition):
            disk = self.get_disk_by_partition(partition)
            pobj = disk_stats[disk]
            meta = {"variables": ["partition","disk","disk.bytes.write","bytes.write"],
                    "partition":self.format_partition(partition),
                    "disk": disk,
                    "disk.bytes.write":pobj.write_bytes,
                    "bytes.write":pobj.write_bytes,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=pobj.write_bytes,meta_data=meta)
            save(dp)
        self.partition_map("disk.bytes.write", _run)
        
    def time_read(self,save):
        disk_stats = psutil.disk_io_counters(perdisk=True) 
        def _validate(datapoint):
            datapoint.meta_data['disk.time.read'] = datapoint.value
            datapoint.meta_data['time.read'] = datapoint.value
         
        def _run(partition):
            disk = self.get_disk_by_partition(partition)
            pobj = disk_stats[disk]
            meta = {"variables": ["partition","disk","disk.time.read","time.read"],
                    "partition":self.format_partition(partition),
                    "disk": disk,
                    "disk.time.read":pobj.read_time,
                    "time.read":pobj.read_time,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=pobj.read_time,meta_data=meta)
            save(dp)
        self.partition_map("disk.time.read", _run)
        
    def time_write(self,save):
        disk_stats = psutil.disk_io_counters(perdisk=True) 
        def _validate(datapoint):
            datapoint.meta_data['disk.time.write'] = datapoint.value
            datapoint.meta_data['time.write'] = datapoint.value
         
        def _run(partition):
            disk = self.get_disk_by_partition(partition)
            pobj = disk_stats[disk]
            meta = {"variables": ["partition","disk","disk.time.write","time.write"],
                    "partition":self.format_partition(partition),
                    "disk": disk,
                    "disk.time.write":pobj.write_time,
                    "time.write":pobj.write_time,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=pobj.write_time,meta_data=meta)
            save(dp)
        self.partition_map("disk.time.write", _run)
        
        
class CpuStat(StatBlock):
    TYPE = "cpu"
    def __init__(self,block):
        global SYSSTAT_PSUTIL_AVAILABLE
        if not SYSSTAT_PSUTIL_AVAILABLE: 
            msg = "%s STAT block is unavailable " % self.TYPE
            msg += "due to missing requirement: psutil module"
            raise Exception(msg)
        StatBlock.__init__(self,block)
        self.CPUS = block.get('CPUS',[])
        affirm = ["yes","true","1","on","active"]
        per_cpu_test = str(block.get('PER_CPU',0)).lower()
        if per_cpu_test in affirm: 
            self.PER_CPU = True
            self.cpu_percent = psutil.cpu_percent(interval=1,percpu=True)
        else:
            self.PER_CPU = False
            self.cpu_percent = psutil.cpu_percent(interval=1)
        self.cpu_percent_task = task.LoopingCall(self.collect_cpu_percent)
        self.cpu_percent_task.start(1,False)
        self.PROVIDED_METRICS.update({
            "usage.percent": self.usage_percent,
            "time.user": self.time_user,
            "time.system": self.time_system,
            "time.nice": self.time_nice,
            "time.iowait": self.time_iowait,
            "time.irq": self.time_irq,
            "time.softirq": self.time_softirq})
        self.PROTOCOLS += [CpuStatMetaData()]
        self.remove_invalid_request_metrics()
    
    def collect_cpu_percent(self):
        per_check = bool(self.PER_CPU or self.CPUS)
        self.cpu_percent = psutil.cpu_percent(interval=0,percpu=per_check)
        
    def aggregate_data(self):
        '''disk data represents a special case and we need to do a
           custom aggregation as a result. even though a metric
           requested may be the same, example usage.percent
           that metric will have multiple partitions and should
           be treated as different metrics. so we need to aggregate
           by partition and metric type. 
        '''
        if not self.PER_CPU and not self.CPUS:
                StatBlock.aggregate_data(self)
                return
        sub_groups = {}
        for metric,datapoints in self.requested_metric_data.items():
            for datapoint in datapoints:
                mpID = metric + "::" + datapoint.cpu
                if mpID not in sub_groups:
                    sub_groups[mpID]  = []
                sub_groups[mpID].append(datapoint)
        self.requested_metric_data = sub_groups
        StatBlock.aggregate_data(self)
        
    def cpu_map(self,name,func):
        '''since cpu stat count costs time , our most expensive resource
           do stat collection in the map function once and pass results
           to stat generators.
        '''
        if not self.PER_CPU and not self.CPUS:
            cputime = psutil.cpu_times()
            try: 
                func(cpu_str='ALL',cpu_int=-1,cpu_pct=self.cpu_percent,cpu_times=cputime)
                return
            except:
                msg = "Error while processing %s" % name
                self.error(msg)
                self.debug("")
        else:
            cputime = psutil.cpu_times(percpu=True)
            cpu_count = len(self.cpu_percent)
            for cpu in range(cpu_count):
                if self.CPUS and cpu not in self.CPUS: continue
                try: func(cpu_str=str(cpu),cpu_int=cpu,cpu_pct=self.cpu_percent[cpu],cpu_times=cputime[cpu])
                except:
                    msg = "Error while processing %s" % name
                    self.error(msg)
                    self.debug("")
    
        
    def usage_percent(self,save):
        def _validate(datapoint):
            datapoint.meta_data['cpu.usage.percent'] = datapoint.value
            datapoint.meta_data['usage.percent'] = datapoint.value
             
        def _run(cpu_str="ALL",cpu_int=-1,cpu_pct=None,cpu_times=None):
            meta = {"variables": ["cpu","cpu.usage.percent","usage.percent"],
                    "cpu": cpu_str,
                    "cpu.usage.percent":cpu_pct,
                    "usage.percent":cpu_pct,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=cpu_pct,meta_data=meta)
            save(dp)
        self.cpu_map("cpu.usage.percent", _run)
        
    def time_user(self,save):
        def _validate(datapoint):
            datapoint.meta_data['cpu.time.user'] = datapoint.value
            datapoint.meta_data['time.user'] = datapoint.value
                
        def _run(cpu_str="ALL",cpu_int=-1,cpu_pct=None,cpu_times=None):
            meta = {"variables": ["cpu","cpu.time.user","time.user"],
                    "cpu": cpu_str,
                    "cpu.time.user":cpu_times.user,
                    "time.user":cpu_times.user,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=cpu_times.user,meta_data=meta)
            save(dp)
        self.cpu_map("cpu.time.user", _run)
        
    def time_system(self,save):
        def _validate(datapoint):
            datapoint.meta_data['cpu.time.system'] = datapoint.value
            datapoint.meta_data['time.system'] = datapoint.value
                
        def _run(cpu_str="ALL",cpu_int=-1,cpu_pct=None,cpu_times=None):
            meta = {"variables": ["cpu","cpu.time.system","time.system"],
                    "cpu": cpu_str,
                    "cpu.time.system":cpu_times.system,
                    "time.system":cpu_times.system,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=cpu_times.system,meta_data=meta)
            save(dp)
        self.cpu_map("cpu.time.system", _run)
        
    def time_nice(self,save):
        ln = "cpu.time.nice"
        sn = "time.nice"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(cpu_str="ALL",cpu_int=-1,cpu_pct=None,cpu_times=None):
            value = cpu_times.system
            meta = {"variables": ["cpu",ln,sn],
                    "cpu": cpu_str,
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.cpu_map(ln, _run)
    
    def time_iowait(self,save):
        ln = "cpu.time.iowait"
        sn = "time.iowait"
        obj,valname = ("cpu_times","iowait")
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(cpu_str="ALL",cpu_int=-1,cpu_pct=None,cpu_times=None):
            value = getattr(locals()[obj],valname)
            meta = {"variables": ["cpu",ln,sn],
                    "cpu": cpu_str,
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.cpu_map(ln, _run)
    
    def time_irq(self,save):
        ln = "cpu.time.irq"
        sn = "time.irq"
        obj,valname = ("cpu_times","irq")
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(cpu_str="ALL",cpu_int=-1,cpu_pct=None,cpu_times=None):
            value = getattr(locals()[obj],valname)
            meta = {"variables": ["cpu",ln,sn],
                    "cpu": cpu_str,
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.cpu_map(ln, _run)
    
    def time_softirq(self,save):
        ln = "cpu.time.softirq"
        sn = "time.softirq"
        obj,valname = ("cpu_times","softirq")
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(cpu_str="ALL",cpu_int=-1,cpu_pct=None,cpu_times=None):
            value = getattr(locals()[obj],valname)
            meta = {"variables": ["cpu",ln,sn],
                    "cpu": cpu_str,
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.cpu_map(ln, _run)
    
class MemoryStat(StatBlock):
    TYPE = "memory"
    def __init__(self,block):
        global SYSSTAT_PSUTIL_AVAILABLE
        if not SYSSTAT_PSUTIL_AVAILABLE: 
            msg = "%s STAT block is unavailable " % self.TYPE
            msg += "due to missing requirement: psutil module"
            raise Exception(msg)
        StatBlock.__init__(self,block)
        self.PROVIDED_METRICS.update({
            "phymem.total":self.phymem_total,
            "phymem.used":self.phymem_used,
            "phymem.free":self.phymem_free,
            "phymem.percent":self.phymem_percent,
            "phymem.cached":self.phymem_cached,
            "phymem.buffers":self.phymem_buffers,
            "virtmem.total":self.virtmem_total,
            "virtmem.used":self.virtmem_used,
            "virtmem.free":self.virtmem_free,
            "virtmem.percent":self.virtmem_percent,})
        self.PROTOCOLS += [MemoryStatMetaData()]
        self.remove_invalid_request_metrics()
        
    def phymem_free(self,save):
        ln = "memory.phymem.free"
        sn = "phymem.free"
        value = psutil.phymem_usage().free
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
            
        meta = {"variables": [ln,sn],
                ln:value,
                sn:value,
                "meta_data_validator": _validate}
        dp = DataPoint(value=value,meta_data=meta)
        save(dp)
    
    def phymem_used(self,save):
        ln = "memory.phymem.used"
        sn = "phymem.used"
        value = psutil.phymem_usage().used
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
            
        meta = {"variables": [ln,sn],
                ln:value,
                sn:value,
                "meta_data_validator": _validate}
        dp = DataPoint(value=value,meta_data=meta)
        save(dp)
    
    def phymem_total(self,save):
        ln = "memory.phymem.total"
        sn = "phymem.total"
        value = psutil.phymem_usage().free
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
            
        meta = {"variables": [ln,sn],
                ln:value,
                sn:value,
                "meta_data_validator": _validate}
        dp = DataPoint(value=value,meta_data=meta)
        save(dp)
    
    def phymem_percent(self,save):
        ln = "memory.phymem.percent"
        sn = "phymem.percent"
        value = psutil.phymem_usage().percent
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
            
        meta = {"variables": [ln,sn],
                ln:value,
                sn:value,
                "meta_data_validator": _validate}
        dp = DataPoint(value=value,meta_data=meta)
        save(dp)
    
    def phymem_buffers(self,save):
        ln = "memory.phymem.buffers"
        sn = "phymem.buffers"
        value = psutil.phymem_buffers()
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
            
        meta = {"variables": [ln,sn],
                ln:value,
                sn:value,
                "meta_data_validator": _validate}
        dp = DataPoint(value=value,meta_data=meta)
        save(dp)
    
    def phymem_cached(self,save):
        ln = "memory.phymem.cached"
        sn = "phymem.cached"
        value = psutil.cached_phymem()
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
            
        meta = {"variables": [ln,sn],
                ln:value,
                sn:value,
                "meta_data_validator": _validate}
        dp = DataPoint(value=value,meta_data=meta)
        save(dp)
    
    def virtmem_total(self,save):
        ln = "memory.virtmem.total"
        sn = "virtmem.total"
        value = psutil.virtmem_usage().total
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
            
        meta = {"variables": [ln,sn],
                ln:value,
                sn:value,
                "meta_data_validator": _validate}
        dp = DataPoint(value=value,meta_data=meta)
        save(dp)
    
    def virtmem_free(self,save):
        ln = "memory.virtmem.free"
        sn = "virtmem.free"
        value = psutil.virtmem_usage().free
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
            
        meta = {"variables": [ln,sn],
                ln:value,
                sn:value,
                "meta_data_validator": _validate}
        dp = DataPoint(value=value,meta_data=meta)
        save(dp)
    
    def virtmem_used(self,save):
        ln = "memory.virtmem.used"
        sn = "virtmem.used"
        value = psutil.virtmem_usage().used
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
            
        meta = {"variables": [ln,sn],
                ln:value,
                sn:value,
                "meta_data_validator": _validate}
        dp = DataPoint(value=value,meta_data=meta)
        save(dp)
    
    def virtmem_percent(self,save):
        ln = "memory.virtmem.percent"
        sn = "virtmem.percent"
        value = psutil.virtmem_usage().percent
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
            
        meta = {"variables": [ln,sn],
                ln:value,
                sn:value,
                "meta_data_validator": _validate}
        dp = DataPoint(value=value,meta_data=meta)
        save(dp)
    

class NetworkStat(StatBlock):
    TYPE = "network"
    def __init__(self,block):
        global SYSSTAT_PSUTIL_AVAILABLE
        if not SYSSTAT_PSUTIL_AVAILABLE: 
            msg = "%s STAT block is unavailable " % self.TYPE
            msg += "due to missing requirement: psutil module"
            raise Exception(msg)
        StatBlock.__init__(self,block)
        self.INTERFACES = block.get('INTERFACES',[])
        affirm = ["yes","true","1","on","active"]
        per_interface_test = str(block.get('PER_INTERFACE',0)).lower()
        if per_interface_test in affirm: self.PER_INTERFACE = True
        else: self.PER_INTERFACE = False
        self.PROVIDED_METRICS.update({
            "bytes.sent": self.bytes_sent,
            "bytes.recv": self.bytes_recv,
            "packets.sent": self.packets_sent,
            "packets.recv": self.packets_recv})
        self.PROTOCOLS += [NetworkStatMetaData()]
        self.remove_invalid_request_metrics()
        
    def aggregate_data(self):
        '''disk data represents a special case and we need to do a
           custom aggregation as a result. even though a metric
           requested may be the same, example usage.percent
           that metric will have multiple partitions and should
           be treated as different metrics. so we need to aggregate
           by partition and metric type. 
        '''
        if not self.PER_INTERFACE and not self.INTERFACES:
                StatBlock.aggregate_data(self)
                return
        sub_groups = {}
        for metric,datapoints in self.requested_metric_data.items():
            for datapoint in datapoints:
                mpID = metric + "::" + datapoint.nic
                if mpID not in sub_groups:
                    sub_groups[mpID]  = []
                sub_groups[mpID].append(datapoint)
        self.requested_metric_data = sub_groups
        StatBlock.aggregate_data(self)
        
    def nic_map(self,name,func):
        '''since cpu stat count costs time , our most expensive resource
           do stat collection in the map function once and pass results
           to stat generators.
        '''
        if not self.PER_INTERFACE and not self.INTERFACES:
            nic_counters = psutil.network_io_counters(pernic=False)
            try: 
                func("ALL",nic_counters)
                return
            except:
                msg = "Error while processing %s" % name
                self.error(msg)
                self.debug("")
        else:
            nic_counters = psutil.network_io_counters(pernic=True)
            for nic in nic_counters:
                nic_str = nic.split(":")[0]
                if self.INTERFACES and nic not in self.INTERFACES: continue
                try: func(nic_str,nic_counters[nic])
                except:
                    msg = "Error while processing %s" % name
                    self.error(msg)
                    self.debug("")
        
    def bytes_sent(self,save):
        ln = "network.bytes.sent"
        sn = "bytes.sent"
        obj,valname = ("nic","bytes_sent")
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(nic_str,nic):
            value = getattr(locals()[obj],valname)
            meta = {"variables": ["nic",ln,sn],
                    "nic": nic_str,
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.nic_map(ln, _run)
        
    def bytes_recv(self,save):
        ln = "network.bytes.recv"
        sn = "bytes.recv"
        obj,valname = ("nic","bytes_recv")
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(nic_str,nic):
            value = getattr(locals()[obj],valname)
            meta = {"variables": ["nic",ln,sn],
                    "nic": nic_str,
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.nic_map(ln, _run)
        
    def packets_sent(self,save):
        ln = "network.packets.sent"
        sn = "packets.sent"
        obj,valname = ("nic","packets_sent")
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(nic_str,nic):
            value = getattr(locals()[obj],valname)
            meta = {"variables": ["nic",ln,sn],
                    "nic": nic_str,
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.nic_map(ln, _run)
        
    def packets_recv(self,save):
        ln = "network.packets.recv"
        sn = "packets.recv"
        obj,valname = ("nic","packets_recv")
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(nic_str,nic):
            value = getattr(locals()[obj],valname)
            meta = {"variables": ["nic",ln,sn],
                    "nic": nic_str,
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.nic_map(ln, _run)
        
    
class ProcessStat(StatBlock):
    TYPE = "process"
    
    def __init__(self,block):
        global SYSSTAT_PSUTIL_AVAILABLE
        if not SYSSTAT_PSUTIL_AVAILABLE: 
            msg = "%s STAT block is unavailable " % self.TYPE
            msg += "due to missing requirement: psutil module"
            raise Exception(msg)
        StatBlock.__init__(self,block)
        #this confusing bit gets all "STATUS" elements from psutils and converts it to a dict
        #this is used to perform quick lookups on status value of proc which is <int> by default.
        #we want the string name not the integer.
        self.status_map = dict([(getattr(psutil,d),d.replace("STATUS_","")) 
                                for d in dir(psutil) if d.startswith("STATUS") ])
        self.match_lists = {
             "MATCH_PID":     self.compile_all("MATCH_PID"),
             "MATCH_PPID":    self.compile_all("MATCH_PPID"),
             "MATCH_NAME":    self.compile_all("MATCH_NAME"),
             "MATCH_EXE":     self.compile_all("MATCH_EXE"),
             "MATCH_USER":    self.compile_all("MATCH_USER"),
             "MATCH_CMDLINE": self.compile_all("MATCH_CMDLINE"),
             "MATCH_STATUS":  self.compile_all("MATCH_STATUS"),
        }
        self.PROVIDED_METRICS.update({
            "threads.count": self.threads_count,
            "children.count": self.children_count,
            "files.count": self.files_count,
            "memory.rss": self.memory_rss,
            "memory.vms": self.memory_vms,
            "network.connection.count": self.net_conn_count,
            "network.connection.tcp.count": self.net_conn_tcp_count,
            "network.connection.udp.count": self.net_conn_udp_count,
            "disk.counters.read": self.disk_read_count,
            "disk.counters.write": self.disk_write_count,
            "disk.bytes.read": self.disk_read_bytes,
            "disk.bytes.write": self.disk_write_bytes,
            "cpu.usage.percent": self.cpu_usage_percent,
            "cpu.time.user": self.cpu_time_user,
            "cpu.time.system": self.cpu_time_system,
            })
        self.PROTOCOLS += [ProcessStatMetaData()]
        self.remove_invalid_request_metrics()
        
    def compile_all(self,name):
        ml = self.config_block.get(name,[])
        out = []
        for m in ml:
            out.append(re.compile(m))
        self.error("%s patterns loaded for match list %s" % ( len(out), name) )
        return out
        
    def aggregate_data(self):
        '''disk data represents a special case and we need to do a
           custom aggregation as a result. even though a metric
           requested may be the same, example usage.percent
           that metric will have multiple partitions and should
           be treated as different metrics. so we need to aggregate
           by partition and metric type. 
        '''
        sub_groups = {}
        for metric,datapoints in self.requested_metric_data.items():
            for datapoint in datapoints:
                mpID = metric + "::" + str(datapoint.pid)
                if mpID not in sub_groups:
                    sub_groups[mpID]  = []
                sub_groups[mpID].append(datapoint)
        self.requested_metric_data = sub_groups
        StatBlock.aggregate_data(self)
        
    def apply_filters(self):
        '''for all proces on system
           take a proc and iterate over all defined match lists
           for each match list pass the proc and the match list
           to a handler function that knows how to check contents of that list
           the result of that list check func is true or false
           true if any items matched, false if all failed to match.
           if result is true for any given list (ml) stop right there
           we must have at least one match per list (i.e. true from handler)
        '''
        for proc in psutil.process_iter():
            fpassed = True
            for k,ml in self.match_lists.items():
                if not ml: continue
                fn = k.lower()+"_filter"
                if not hasattr(self,fn):
                    msg = "filter: %s was specified by has not handler logic."
                    raise Exception(msg)
                fpassed = getattr(self,fn)(proc,ml)
                if not fpassed: break
                msg = "match found for pid %s in match list %s" % (proc.pid,k)
                self.debug(msg)
            if not fpassed: continue
            yield proc
                
    def match_pid_filter(self,proc,match_list):
        pid = str(proc.pid) 
        for m in match_list:
            match = m.match(pid)
            if match: return True
        return False
    
    def match_ppid_filter(self,proc,match_list):
        ppid = str(proc.ppid)
        for m in match_list:
            match = m.match(ppid)
            if match: return True
        return False
    
    def match_name_filter(self,proc,match_list):
        name = proc.name
        for m in match_list:
            match = m.match(name)
            if match: return True
        return False
    
    def match_exe_filter(self,proc,match_list):
        exe = proc.exe
        for m in match_list:
            match = m.match(exe)
            if match: return True
        return False
    
    def match_user_filter(self,proc,match_list):
        user = proc.username
        for m in match_list:
            match = m.match(user)
            if match: return True
        return False
    
    def match_cmdline_filter(self,proc,match_list):
        cmd_array = proc.cmdline
        for m in match_list:
            for cmd in cmd_array:
                match = m.match(cmd)
                if match: return True
        return False
        
    def match_status_filter(self,proc,match_list):
        status = self.status_map[proc.status]
        for m in match_list:
            match = m.match(status)
            if match: return True
        return False
       
    def proc_map(self,name,func):
        for proc in self.apply_filters():
            try:
                #in case our process doesn't have access to target just skip.                
                try: proc.exe
                except psutil.AccessDenied: continue 
                func(proc)
            except:
                msg = "Error while processing %s" % name
                self.error(msg)
                self.debug("")
                  
    def cpu_time_system(self,save):
        ln = "process.cpu.time.system"
        sn = "cpu.time.system"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = proc.get_cpu_times().system
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
                  
    def cpu_time_user(self,save):
        ln = "process.cpu.time.user"
        sn = "cpu.time.user"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = proc.get_cpu_times().user
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
                 
    def cpu_usage_percent(self,save):
        ln = "process.cpu.usage.percent"
        sn = "cpu.usage.percent"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = proc.get_cpu_percent()
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
                
    def disk_write_bytes(self,save):
        ln = "process.disk.bytes.write"
        sn = "disk.bytes.write"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = proc.get_io_counters().write_bytes 
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
               
    def disk_read_bytes(self,save):
        ln = "process.disk.bytes.read"
        sn = "disk.bytes.read"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = proc.get_io_counters().read_bytes 
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
              
    def disk_write_count(self,save):
        ln = "process.disk.counters.write"
        sn = "disk.counters.write"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = proc.get_io_counters().write_count 
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
             
    def disk_read_count(self,save):
        ln = "process.disk.counters.read"
        sn = "disk.counters.read"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = proc.get_io_counters().read_count 
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
            
    def net_conn_udp_count(self,save):
        ln = "process.network.connection.udp.count"
        sn = "network.connection.udp.count"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = len(proc.get_connections(kind="udp")) 
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
           
    def net_conn_tcp_count(self,save):
        ln = "process.network.connection.tcp.count"
        sn = "network.connection.tcp.count"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = len(proc.get_connections(kind="tcp")) 
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
          
    def net_conn_count(self,save):
        ln = "process.network.connection.count"
        sn = "network.connection.count"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = len(proc.get_connections(kind='all')) 
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
         
    def memory_rss(self,save):
        ln = "process.memory.rss"
        sn = "memory.rss"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = proc.get_memory_info().rss 
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
        
    def memory_vms(self,save):
        ln = "process.memory.vms"
        sn = "memory.vms"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = proc.get_memory_info().vms 
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
       
    def files_count(self,save):
        ln = "process.files.count"
        sn = "files.count"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = len(proc.get_open_files())
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
        
    def children_count(self,save):
        ln = "process.children.count"
        sn = "children.count"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = len(proc.get_children())
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
                
    def threads_count(self,save):
        ln = "process.threads.count"
        sn = "threads.count"
        def _validate(datapoint):
            datapoint.meta_data[ln] = datapoint.value
            datapoint.meta_data[sn] = datapoint.value
                
        def _run(proc):
            value = len(proc.get_threads())
            meta = {"variables": ["pid","ppid","pname","exe","user","status",ln,sn],
                    "pid": str(proc.pid),
                    "ppid": str(proc.ppid),
                    "pname": proc.name.replace(" ","_"),
                    "exe": proc.exe,
                    "user": proc.username,
                    "status": self.status_map[proc.status],
                    ln:value,
                    sn:value,
                    "meta_data_validator": _validate}
            dp = DataPoint(value=value,meta_data=meta)
            save(dp)
        self.proc_map(ln, _run)
        
        
        
class IDataPointMetaDataProtocol(Interface):
    '''An optional interface to guarantee meta data in an instance of
       droned.models.graphite.DataPoint conforms to a given protocol/schema.
    '''
    def conforms(self,datapoint):
        '''this method checks if a given data point's meta data conforms to the
           protocol defined by this class. Will return true if so. False otherwise.
           @param datapoint:<droned.models.graphite.DataPoint> input data point
           @return: <bool> true if this data point confirms to the protocol
                    described by this class. 
        '''
        pass
    
    def provides_keys(self):
        '''@return: <list:str> name of keys guaranteed to be in DataPoint Metadata
                    optional or partially/conditionally present keys are not returned.
        '''
        pass
    
    
    def key_value_type(self,key):
        '''returns the (type(),) tuple for the value that is associated with the
           input key in a DataPoint's meta_data. example:
           if DataPoint.meta_data == {"foo":1 OR 1.0}
           key_value_type("foo") -> (int,float)
           this is suitable for use with isinstance() checks. 
           @param key: <str> key name to lookup
           @return: <type> type associated with some key in meta_data
        '''
        pass
        
class BasicMetaData(object):
    implements(IDataPointMetaDataProtocol)
    def conforms(self,datapoint):
        '''@keyword stat: stat object that generated this DataPoint
        '''
        if "meta_data_validator" not in datapoint: return False
        if "stat" not in datapoint: return False
        if not IStatBlock.implementedBy(datapoint.stat.__class__): return False
        if "variables" not in datapoint: return False
        if type(datapoint.variables) != list: return False
        for i in datapoint.variables:
            if i not in datapoint: return False
        return True
    
    def provides_keys(self):
        ''' stat -> the stat block object that generated this datapoint
            variables -> variables that can be access via user config
            post_aggregation_validator -> a function that take a data point and 
                    can validate its values and metadata following aggregation
                    process.
        '''
        return ["stat","variables","meta_data_validator"]
    
    def key_value_type(self,key):
        if key == "stat": return (IStatBlock,)
        if key == "variables": return (list,) 
        if key == "meta_data_validator": return (type(self.key_value_type),)

class DiskStatMetaData(object):
    implements(IDataPointMetaDataProtocol)
    _keys = ["usage.percent",
             "usage.free",
             "usage.total",
             "usage.used",
             "counters.read",
             "counters.write",
             "bytes.read",
             "bytes.write",
             "time.read",
             "time.write"]
    
    def conforms(self,datapoint):
        if "partition" not in datapoint: return False
        prefix = "disk."
        found = [d for d in DiskStatMetaData._keys if d in datapoint]
        if not found: return False #must find at least one key
        for f in found:
            if (prefix + f) not in datapoint: return False
        return True
    
    def provides_keys(self):
        return ["partition"]
    
    def key_value_type(self,key):
        number = (int,float,long)
        if key == "partition": return (str,)
        if key in DiskStatMetaData._keys: return number
        sn = ".".join(key.split(".")[1:])
        if sn in DiskStatMetaData._keys: return number

class CpuStatMetaData(object):
    implements(IDataPointMetaDataProtocol)
    _keys = ["usage.percent",
            "time.user",
            "time.system",
            "time.nice",
            "time.iowait",
            "time.irq",
            "time.softirq"]        
    
    def conforms(self,datapoint):
        if "cpu" not in datapoint: return False
        prefix = "cpu."
        found = [k for k in CpuStatMetaData._keys if k in datapoint]
        if not found: return False #must find at least one key
        for f in found:
            if (prefix + f) not in datapoint: return False
        return True
    
    def provides_keys(self):
        return ["cpu"]
    
    def key_value_type(self,key):
        number = (int,float,long)
        if key == "cpu": return (int,)
        if key in self._keys: return number
        sn = ".".join(key.split(".")[1:])
        if sn in self._keys: return number
        
class MemoryStatMetaData(object):
    implements(IDataPointMetaDataProtocol)
    _keys = ["phymem.total",
             "phymem.used",
             "phymem.free",             "phymem.percent",             "phymem.cached",             "phymem.buffers",             "virtmem.total",             "virtmem.used",             "virtmem.free",             "virtmem.percent"]    
    def conforms(self,datapoint):
        prefix = "memory."
        found = [k for k in self._keys if k in datapoint]
        if not found: return False #must find at least one key
        for f in found:
            if (prefix + f) not in datapoint: return False
        return True
    
    def provides_keys(self):
        return []
    
    def key_value_type(self,key):
        number = (int,float,long)
        if key in self._keys: return number
        sn = ".".join(key.split(".")[1:])
        if sn in self._keys: return number
        
class NetworkStatMetaData(object):
    implements(IDataPointMetaDataProtocol)
    _keys = ["bytes.sent",
             "bytes.recv",
             "packets.sent",
             "packets.recv",]
    
    def conforms(self,datapoint):
        if "nic" not in datapoint: return False
        prefix = "network."
        found = [k for k in self._keys if k in datapoint]
        if not found: return False #must find at least one key
        for f in found:
            if (prefix + f) not in datapoint: return False
        return True
    
    def provides_keys(self):
        return ["nic"]
    
    def key_value_type(self,key):
        if key == "nic": return (str,)
        number = (int,float,long)
        if key in self._keys: return number
        sn = ".".join(key.split(".")[1:])
        if sn in self._keys: return number
        

class ProcessStatMetaData(object):
    implements(IDataPointMetaDataProtocol)
    _keys = ["threads.count",
            "children.count",
            "files.count",
            "memory.rss",
            "memory.vms",
            "network.connection.count",
            "network.connection.tcp.count",
            "network.connection.udp.count",
            "disk.counters.read",
            "disk.counters.write",
            "disk.bytes.read",
            "disk.bytes.write",
            "cpu.usage.percent",
            "cpu.time.user",
            "cpu.time.system"]
    
    def conforms(self,datapoint):
        if "pid" not in datapoint: return False
        if "ppid" not in datapoint: return False
        if "pname" not in datapoint: return False
        if "exe" not in datapoint: return False
        if "user" not in datapoint: return False
        if "status" not in datapoint: return False
        prefix = "process."
        found = [k for k in self._keys if k in datapoint]
        if not found: return False #must find at least one key
        for f in found:
            if (prefix + f) not in datapoint: return False
        return True
    
    def provides_keys(self):
        return ["pid","ppid","pname","exe","user","status"]
    
    def key_value_type(self,key):
        if key in self.provides_keys(): return (str,)
        number = (int,float,long)
        if key in self._keys: return number
        sn = ".".join(key.split(".")[1:])
        if sn in self._keys: return number

        
class IStatOutputHandler(Interface):
    OUTPUT_TYPE = Attribute("<string>: name of the output type handled by this class.")
    REQUIRED_PROTOCOLS = Attribute("<list>: array of protocols that must be implemented")
    def __init__(self,block,stat):
        '''@param block: OUTPUT config block.
           @param stat: stat block object that is parent to this output.
        '''
        pass
    
    def do_output(self):
        '''this should be run every OUTPUT_INTERVAL seconds.
           takes summarized or raw data and outputs it in format
           specific to this output. 
        '''
        pass
    
    def extract_variables(self,text):
        '''for a given text extract all the variable names
           defined in this text.
           @param text: <str> string to extract from
           @return: <set> list of variable names.
        '''
        pass
    
    def input_variables(self,text,map):
        '''for some text replace all variables with
           the values for each variable in map
           @param text: <str> string to replace variables in
           @param map: <dict> mapping of variable names to values
           @return: <str> text with variables replaced.
        '''
    
class StatOutputHandlerLoader(ClassLoader):
    interface_type = IStatOutputHandler
    subloaders = []
    
class StatOutputHandler(object):
    implements(IStatOutputHandler)
    OUTPUT_TYPE = "null"
    REQUIRED_PROTOCOLS = [BasicMetaData()]
    
    @raises(InvalidOutputBlockDefinition)
    def __init__(self,block,stat):
        self.block = block
        self.stat = stat
        self.var_reg = re.compile("(<[^>]+>)")
        
    def do_output(self):
        pass
    
    def extract_variables(self,text):
        out = set()
        raw_vars = self.var_reg.findall(text)
        for r in raw_vars:
            out.add( r.replace("<","").replace(">","") )
        return out
   
    def input_variables(self,text,vmap):
        for k,v in vmap.items():
            var = "<"+k+">"
            if var not in text: continue
            text = text.replace(var,v)
        return text
    
    def map_metrics(self,callback,*args,**kwargs):
        '''convenience function that maps each datapoint
           to the given callback with the provided args
           passed to that callback(datapoint,*args)
        '''
        out = []
        gaurd_len = len(self.REQUIRED_PROTOCOLS)
        for name,datapoints in self.stat.requested_metric_data.items():
            for datapoint in datapoints:
                gaurd = [p for p in self.REQUIRED_PROTOCOLS if p.conforms(datapoint)]
                if len(gaurd) != gaurd_len: continue
                ret = callback(datapoint,*args,**kwargs)
                out.append(ret)
        return out
        
class GraphiteOutputHandler(StatOutputHandler):
    OUTPUT_TYPE = "graphite"
    
    def do_output(self):
        '''look through all datapoint and figure out which ones
           can build the metric names we have been asked to genterate.
           for some metric foo.bar.<variable> <othervar>
           there may only be a select few metrics that can 
           supply all variable values. each one is a unique metric
           however and will get its own TimeSeriesData Entity 
        '''
        metrics = self.block['METRICS']
        for m in metrics:
            self.map_metrics(self.resolve_metric,m)
            
    def issue_value_warning(self,datapoint,metric,value):
        '''we have detected that our value does not appear to be correct.
           this may not be an issue as specified in #2 of resove_metric()
           but we will issue a warning that is visible if logging is turned up
           to at least error.
        '''
        dpID = id(datapoint)
        sdpID = "datapoint[%s] - " % dpID
        msg1 = sdpID + "the metric value being updated as specified "
        msg1 += "via user config does not appear to be a number"
        msg2 = sdpID + "metric_in_config = %s" % metric
        msg3 = sdpID + "value_variable_contents = %s" % value 
        self.stat.error(msg1)
        self.stat.error(msg2)
        self.stat.error(msg3)
                    
    def resolve_metric(self,datapoint,metric):
        '''basically just extracts variables from datapoint metadata
           and inserts them into the metric string.
           #1 make sure this datapoint has all the meta data we need
              to replace all variables in the metric string.
           #2 metrics string has this form <metric_name> <value_variable>
              we need to make sure the variable name stored in 
              variable_value has a value its self equal to what our
              data point value is. this should generally be the case but
              there is no enforcement of this. a user *should* have a
              metric that look something like this: 
              foo.bar.baz <corresponding_metric_value_variable> 
              this however is not enforced if the user wnats to use
              some other variable as the value for this metric they are
              free to do so. we should just update our datapoint.value to be
              whatever that value of the user specified variable is. this may
              break that metric but its not up to this code to enforce that.
           #3 here we are just replacing variables in our metric name
              with the values collected 
           #4 this is a graphite specific limitation. graphite uses "dot == ." 
              as its seperator for metric names. things like FQDN need to have
              period replaced with underscore. example:
              myhost.company.com -> myhost_company_com
        '''
        variables = datapoint.variables
        text_vars = self.extract_variables(metric)
        tvl = len(text_vars)
        found = [v for v in text_vars if v in variables]
        if len(found) != tvl: return #1
        name,value = [m.strip() for m in metric.split()] #1
        value = self.extract_variables(value).pop() #2
        meta_value = datapoint.meta_data[value]
        if datapoint.value != meta_value: #2
            if not isinstance(meta_value, (int,float)): 
                self.issue_value_warning(datapoint,metric,meta_value)
            datapoint.value = datapoint.meta_data[value] #2
        varmap = {}
        meta_data = datapoint.meta_data
        for tvar in text_vars: #3
            val = getattr(meta_data,tvar) #3
            if type(val) ==  str: val = val.replace(".","_") #4
            varmap[tvar] = val #3
        resolved_metric = self.input_variables(name,varmap) #3
        dpID = id(datapoint)
        self.stat.error("datapoint[%s] - sending metric to graphite via output" % dpID)
        self.stat.debug("datapoint[%s] - value = %s" %(dpID,datapoint.value))
        self.stat.debug("datapoint[%s] - metric = %s" % (dpID,resolved_metric))
        TimeSeriesData(resolved_metric).add(datapoint)
        
        


# These come after our class definitions to avoid circular import dependencies
from droned.models.droneserver import DroneD
from droned.management.server import ServerManager
