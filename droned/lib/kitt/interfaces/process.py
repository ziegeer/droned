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

from zope.interface import Interface, Attribute

class IKittProcModule(Interface):
    """proc modules must implement the following methods"""
    def listProcesses():
        """returns a list of pid's"""

    def findProcesses(s):
        """Finds Process ID by pattern

           #typically the result is as follows
           @return dict {int(pid): re.complile(s).search(LiveProcess(int(pid)).cmdline)}
        """

    def findThreadIds(s):
        """Finds Threads ID by pattern
           @return set([int(pid),])
        """

    def isRunning(pid):
        """is a given process id running, returns Boolean"""

    def cpuStats():
        """Returns a dictionary of cpu stats
           Note: stats will be platform specific
        """

    def cpuTotalTime():
        """Returns Total CPU Time Used in seconds"""


class IKittProcess(Interface):
    """Minimum Interface Definition of a Process"""
    running = Attribute("bool")
    inode = Attribute("int inode of the process")
    pid = Attribute("int process id > 1")
    ppid = Attribute("int parent process id >= 1")
    exe = Attribute("str or None")
    cmdline = Attribute("list of str's")
    memory = Attribute("int number of bytes in use")
    fd_count = Attribute("int number of file descriptors in use >= 3")
    stats = Attribute("dict of stats os dependant")
    environ = Attribute("dict of Environmental Variables")
    threads = Attribute("int of thread count >= 1")
    uid = Attribute("int user id >=0 (root is 0)")
    gid = Attribute("int group id >=0 (root is 0)")

    def __init__(pid):
        """
           @param pid (int) - Process ID
        """

    def isRunning():
        """Check if the process is running
           @return (bool)
        """

    def getEnv():
        """Return the process' ENVIRONMENT Variables
           @return (dict)
        """

    def getFD():
        """Return the process' file descriptors
           @return (dict)
        """

    def getTasks():
        """Returns the process' tasks/threads
           @return (set)
        """

    def getStats():
        """Returns various stats about the process
           this will be platform specific.
           @return (dict)
        """

    def memUsage():
        """Returns the amount of memory used in bytes
           @return (int)
        """

    def waitForDeath(timeout, delay):
        """wait for process to die

           @param timeout (float)
           @param delay (float)
           @return (bool)
        """

class IKittLiveProcess(IKittProcess):
    """Minimum Interface Definition of a LiveProcess"""
    def cpuUsage():
        """Returns the sys and user utilization
           @return (dict)
        """

class IKittProcessSnapshot(IKittProcess):
    """Minimum Interface Definition of a ProcessSnapshot"""
    def update():
        """Update the snapshot
           @return (NoneType)
        """


class IKittNullProcess(IKittProcess):
    """Minimum Interface Definition of a NullProcess"""
    pass

class IKittRemoteProcess(IKittProcess):
    """Minimum Interface Definition of a NullProcess"""
    def updateProcess(infoDict):
        """Update the remote process
           @param infoDict (dict)
           @return (NoneType)
        """

###############################################################################
# DroneD Model Description 
###############################################################################
class IDroneModelAppProcess(Interface):
    """Model of Processes that DroneD may want to interact with"""
    created = Attribute("when was the object created")
    managed = Attribute("is this process managed")
    localInstall = Attribute("is this process local or remote")
    process = Attribute("""
        L{IKittRemoteProcess}, L{IKittLiveProcess}, or L{IKittNullProcess}""")
    running = Attribute("is the process running")
    pid = Attribute("Process ID")
    ppid = Attribute("Parent Process ID")
    inode = Attribute("Inode of the Process")
    memory = Attribute("memory used by the process")
    fd_count = Attribute("open file descriptor count")
    environ = Attribute("environmental settings from the process")
    stats = Attribute("collection of process stats")
    threads = Attribute("number of threads in use")
    executable = Attribute("the executable of the process")
    cmdline = Attribute("commandline arguments that spawned the process")

    def updateProcess(dictionary):
        """Updates information about a remote process"""

__all__ = [
    'IKittProcModule',
    'IKittProcess',
    'IKittLiveProcess',
    'IKittProcessSnapshot',
    'IKittNullProcess',
    'IKittRemoteProcess',
    'IDroneModelAppProcess',
]
