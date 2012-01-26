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
#  Jun 11, 2011:
# @author: cbrinley
# module name: systemstats
###############################################################################

#api requirements
from kitt.util import dictwrapper
SERVICENAME = 'systemstats'
SERVICECONFIG = dictwrapper({})

__doc__ = """
!!! NOTE !!!!
This service does a bunch of small blocking IO operations. in most cases this will not be
a problem at all however if you are running a lot higher frequency services or services that
have sub-second requirements for other services you may notice interference from this
service. This will be fixed in a future release. For the majority of operations oriented
tasks this is not a big deal.

This service will produce system stats at the assigned poll interval.
CPU,Memory,Disk,network IO, Process specific stats are available.
The below configuration as shown would be included for an individual server. 
It is also possible to put this as an include or via a label "&" sytnax.

Minimum required config:
- SERVICE: &systemstats1
    SERVCIENAME: systemstats

**************** EXAMPLE USAGE ******************
#Collecting basic disk and memory stats
- SERVICE: &systemstats2
    SERVCIENAME: systemstats
    STATS:
- STAT:
    TYPE: disk
    PARTIIONS: ["/","/myDBmount"]
    METRICS: ["usage.percent","usage.free"]
    COLLECT_INTERVAL: 5s
    OUTPUT_INTERVAL: 60s
    AGGREGATION_METHOD: average
    OUTPUTS:
		- OUTPUT: 
		    TYPE: graphite
		    METRICS: 
			- servers.<hostname>.disk.percent_used <usage.percent> 
			- servers.<hostname>.disk.free_bytes <usage.free>            
	- STAT:
	    TYPE: memory
	    METRICS: ["physmem.precent","physmem.free"]
	    INTERVAL: 1m #same as above
	    OUTPUTS:
		- OUTPUT:
		    TYPE: graphite
		    METRICS: [servers.<hostname>.memory.percent_used <physmem.percent>, ...]

#Colleting CPU and thread info for a specific process
- SERVICE: &systemstats3
    SERVICENAME: systemstats
    STATS:
	- STAT:
	    TYPE: process
	    MATCH_USER: [mysql,postgres]
	    MATCH_EXE: [.*mysqld$,.*postgres$]
	    METRICS: [cpu.usage.percent,threads.count]
	    COLLECT_INTERVAL: 5s
	    AGGREGATION_METHOD: none
	    OUTPUTS:
		- OUTPUT:
		    TYPE: graphite
		    OUTPUT_INTERVAL: 1m
		    METRICS:  #equiv to [a,b,c] syntax
			- services.databases.<hostname>.<pname>.threads <threads.count>
			- services.databases.<hostname>.<pname>.cpu.percent_used <cpu.usage.percent>

******************** VARIABLES ********************
Variables may be inserted in any string. Some Stat types may support context aware variable.
Variable syntax is as follows: <variable_name> 
The string <variable_name> will be replaced by the computed value.
  * Available Variables:
    * <usage.percent> = this is a special variable that will hold the value of the last metric sample.
			the name between the angle brackets can be any valid metric name. see METRICS
			section below for valid metric names and meanings.
    * <hostname> = the hostname of the computer droned is currently running on.
    * <partition> = the name of the partition currently being evaluated. only valid in disk stat block. "/" slashes removed.
    * <nic> = the network interface currently being evaluated. only valid in network stat block.
    * <cpu> = the ordinal of the cpu currently being evaluated. only valid in a cpu stat block.
    * <pid> = pid of the current process. only valid in process stat block
    * <ppid> = parent pid of the current process. only valid in process stat block
    * <pname> = name of the current process. only valid in process stat block
    * <exe> = executable of the current process. only valid in process stat block
    * <user> = username of the current process. only valid in process stat block
    * <status> = status of the current process. only valid in process stat block
 

    
****************** STAT BLOCKS *******************
METRIC NOTES:
* All metrics are contained in a namespace that is the same as the type of stats block.
  An example would be for the Stat block of type "disk" the fully qualified name of the "usage.percent"
  metric is "disk.usage.percent". When you are in a stat block of type "disk" you may omit
  the prefix "disk" in the metric "disk.usage.percent". That is to say in the "disk" stat
  block "disk.usage.percent" and "usage.percent" are equivalent.  When is the prefix required?
  The type prefix is required when you are referencing a metric from a differnet block type. This
  is currently only required in the "process" stat block. The process stat block may report cpu
  statistics as well as memory statistics. To find the correct metric the full name must be
  specified in this case. Use "cpu.usage.percent" not "usage.percent" to locate the proper metric.
  Invalid metrics will be ignored.  

* STATS: defines the start of all stat definitions  
* - STAT: defines the start of a statistic block. this defines what to capture and where to send resutls of that capture.
  *  TYPE: defines the type of stat valid options are: disk,memory,cpu,network,process
  *  COLLECT_INTERVAL: how often to poll for stat. format <int><unit> where int is a number (1,3,499) and unit is one of "s,m,h,d"
	s = seconds. example 60s == 1 minute
	m = minutes. example 2m == 120 seconds
	h = hours. example 24h == 1 day
	d == days. example 5 days == miller time!
	w == week. example 1 week == 7 days 
	y == 365 days. example 1 year == 365 days.
  * AGGREGATION_METHOD: how to roll up metrics collected during the intermediate collect intervals.
	none = this is default if nothing is specified. this means all data collected is passed on to output with no processing.
	average = average all values received during the OUTPUT_INTERVAL period
	sum = sum all values
	max = take maximum value
	min = take minimum value
  * OUPUTS: defines the start of all output definitions.
    *  OUTPUT: defines the start of an output block. this defines where to send captured metrics.
      * TYPE: defines the type of output. currently supported are: graphite
Stat Type options:
TYPE: disk
  * PARTITIONS: list of which partitions to monitor ["/","/opt",etc] partition should be same as shown in output of df -h
  * METRICS: string list of what to capture. valid options are:
    * usage.percent: collects percent of partition used and is returned as float between 0.0-100.0
    * usage.free: bytes available on the selected partition
    * usage.total: total available bytes on selected partition. this will not change typically.
    * usage.used: bytes currently used on selected partition. inverse of usage.free.
    * counters.read: number of reads to the selected partition
    * counters.write: write counts
    * bytes.read: number of bytes to the selected partition
    * bytes.write: number of write bytes
    * time.read: time spent reading from partition in milliseconds
    * time.write: time spent writing in MS

TYPE: memory
NOTE - short hand used here where not specified all formats and options are same as disk
  * METRICS: see disk
    * phymem.percent,free,total,used: all same as disk counter parts but for physical memory in system.
    * virtmem.percent,free,total,used: all same as disk counter parts but for vitual memory in system.
    * phymem.buffers: number of memory buffers on the system.
    * phymem.cached: amount of cached memory in bytes.
    
TYPE: network
NOTE - short hand used here where not specified all formats and options are same as disk
  * INTERFACES: optional. list of interfaces to collect stats for. if this is omitted aggregate counts will be computed.
		if the <nic> variable is used it will evaluate to the string "all" if list not given and PER_INTERFACE = False 
  * PER_INTERFACE: optional. bool. if true list stats per interface even if INTERFACES is not specified. Default False
  * METRICS: see disk
    * bytes.sent,recv: number of bytes sent or received. either per NIC or total.
    * packets.sent,recv: number of packets sent or recieve. either per NIC or total.

TYPE: cpu
  * CPUS: optional. a list of cpu's to collect stats for. this will be of the form [0,2,7,...] where these number represent which
	  CPU you are collecting stats for. <cpu> variable will evaluate to "all" if not used and PER_CPU not True.
  * PER_CPU: optional. bool. if true list stats per cpu even if CPUSis not specified. Default False
  * METRICS: see disk
    * usage.percent: same as disk but for CPU
    * time.user: represents time in user mode.
    * time.system: time in kernel/system
    * time.nice: (unix) time niced down.
    * time.iowait: time waiting on disk or network IO
    * time.irq: time handling hardware interrupts
    * time.softirq: (linux) time handling software interrupts.
NOTE - short hand used here where not specified all formats and options are same as disk

TYPE: process
  * MATCH_*: these are all used to scope which processes are monitored by this stat block. if not given all processes will be monitored!
	     MATCH lists are conjunctive meaning that are all "AND'd" together.
	     items in a MATCH list are OR'd together. 
	     what this effectively means is that each target process must match a least one pattern in each ALL MATCH lists.
	     each MATCH_ list is a list of regular expressions. as soon as a match is made the system moves on to the next
	     MATCH_ list. if a list is not specified in config an automatic match is assumed.
	     example: [".*java.*",".exe$"]. Note the whole string must match so you should prefix and postfix '.*'
	     to your regular expression if you are specifying only part of a command line.
  * MATCH_PID: list of PIDS. only monitor processes whose PID can be found in this list.
  * MATCH_PPID: list of parent PIDS. only monitor processes whose parent is found in this list.
  * MATCH_NAME: match the short name of this process. i.e. "java"
  * MATCH_EXE: match the full path to the executable for this process, i.e. "/usr/bin/java"
  * MATCH_USER: match the user who owns this process. i.e. root
  * MATCH_CMDLINE: part of a command line for a target process.
  * MATCH_STATUS: status elements must be one of DEAD,DISK_SLEEP,IDLE,LOCKED,RUNNING,SLEEPING,STOPPED,TRACING_STOP,WAKING,ZOMBIE
                  remember using more than one will match a process of any of the status types specified.
  * METRICS: 
    * threads.count: OS threads this process is using
    * children.count: child processes owned by this PID
    * files.counts: number of open files in use by this process
    * memory.rss: in bytes resident memory size of this process
    * memory.vms: virtual memory size in bytes of this process
    * network.connections.count: total number of IP connections this process has open
    * network.connections.tcp.count: same but just TCP
    * network.connections.udp.count: same but just UDP
    -- PROCESS SPECIFIC VERSION OF PERVIOUSLY DEFINED METRICS -- 
    (same logical meaning as in the subsystem block. thse are the process metric IDs for those.)
    * disk.counters.read
    * disk.counters.wrte
    * disk.bytes.read
    * disk.bytes.write
    * cpu.usage.percent
    * cpu.time.user
    * cpu.time.system


******************** OUTPUT BLOCKS ********************
* OUTPUT_INTERVAL: how often to send stats to the output desinations. same syntax as COLLECT_INTERVAL.
TYPE: graphite
  * METRICS: list, each element is composed of two parts. A name and a value.
	     Name: these are the metric names that will be sent to graphite on the STAT BLOCK specified INTERVAL. 
	     See graphite doc for more info. metric names may contain variables and this is the most common place to use them.
	     Value: this is a numeric value for this metric. you may use the variable for capture metric here to dynamically
	     apply that value to the named metric. example, <time.user> will input the amount of time the cpu spent in user mode.
	     See example section for more detail on exactly how to use these. 
"""
WORK_IN_PROGRESS_MESSAGE = "[systemstats service]: this service is under development and will throw an error on load.\n"
WORK_IN_PROGRESS_MESSAGE += "This error will not affect other running services. you may ignore."
#raise NotImplementedError(WORK_IN_PROGRESS_MESSAGE)

import time
from zope.interface import Interface, Attribute
from twisted.python.failure import Failure
from twisted.internet import defer, task
from twisted.application.service import Service
from droned.logging import logWithContext, err
from droned.models.systemstats import StatBlockLoader
from droned.models.action import AdminAction

#becoming a service provider module
from kitt.interfaces import moduleProvides, IDroneDService
moduleProvides(IDroneDService) #requirement

log = logWithContext(type=SERVICENAME)

class SystemStats(Service):
    writing = defer.succeed(None)
    
    def stop_collect(self,*args):
	log("disabling all metric collection")
	for h in self.handlers:
	    h[1].disable_collect()
	
    def start_collect(self,*args):
	log("enabling metic collection")
	for h in self.handlers:
	    h[1].enable_collect()
	
    def stop_output(self,*args):
	log("disabling all metric outputs")
	for h in self.handlers:
	    h[1].disable_output()
	
    def start_output(self,*args):
	log("enabling all metric outputs")
	for h in self.handlers:
	    h[1].enable_output()
    
    def set_log_level(self,level):
	log("adjusting to %s log level" % level)
	for h in self.handlers:
	    h[1].set_log_level(level)
    
    def setup_actions(self):
	self.action = AdminAction('systemstats')
	self.action.expose("stop_collect", self.stop_collect, (), "stops collecting metrics")
	self.action.expose("start_collect", self.start_collect, (), "starts collecting metrics")
	self.action.expose("stop_output", self.stop_output, (), "stops output of metrics")
	self.action.expose("start_output", self.start_output, (), "starts output of metrics")
	adoc = "sets log level of this service. valid values are info,error,debug [info default]"
	self.action.expose("set_log_level", self.set_log_level,("level",),adoc)
	self.action.buildDoc()
	    
    
    def startService(self):
	self.handlers = []
	stat_handlers = StatBlockLoader.load()
	for STAT in SERVICECONFIG.STATS:
            STAT_BLOCK = STAT['STAT']
            try:
                for sh in stat_handlers:
                    if sh.TYPE == STAT_BLOCK['TYPE']:
                        inst = sh(STAT_BLOCK)
                        self.handlers.append((STAT_BLOCK,inst))
            except:
                f = Failure()
                err("Error while initializing systemstats service.")
        self.setup_actions()
        Service.startService(self)
            
    def stopService(self):
        Service.stopService(self)
        


#module state globals
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
        service = SystemStats()
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
