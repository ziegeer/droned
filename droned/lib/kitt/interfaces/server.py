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

class IDroneModelServer(Interface):
    """Model of a Server"""
    connectFailure = Attribute("L{twisted.python.failure.Failure} or None") 
    appinstances = Attribute("""
        iterator of L{kitt.interfaces.IDroneModelAppInstance} providers.""")
    apps = Attribute("iterator of L{kitt.interfaces.IDroneModelApp} providers")
    unreachable = Attribute("C{bool}")
    installedApps = Attribute("C{set} #not currently used, but planned")
    listed = Attribute("C{bool}")
    manager = Attribute("L{droned.management.server.ServerManager}")
    droned = Attribute("L{kitt.interfaces.IDroneModelDroneD}")

    def startPolling():
        """start polling this server"""

    def stopPolling():
        """stop polling this server"""

    def byName(name):
        """return L{IDroneModelServer} provider by name"""

class IDroneModelDroneServer(Interface):
    """Model of the Command Dispatcher Interface"""
    keyRing = Attribute("C{dict} of L{kitt.rsa.privateKeys}")
    lock = Attribute("L{twisted.internet.defer.DeferredLock}")
    builtins = Attribute("C{dict} builtin actionable methods")
    server = Attribute("L{kitt.interfaces.IDroneModelServer}")

    def getprime():
        """get a prime number from the prime list

           @callback C{int}
           @return L{defer.Deferred}
        """

#THOUGHTS this may not make sense to have here
    def validateMessage(magicNumber):
        """used to validate remote commands

           @param magicNumber C{int}
           @return C{bool}
        """

    def releasePrime(prime):
        """release prime back into the prime pool for later use

           @callback C{NoneType}
           @return L{defer.Deferred}
        """

    def formatResults(response):
        """take a variety of input types for ``response``
           and returns a C{dict}.

           @param response C{dict|tuple|str} or 
             L{droned.errors.DroneCommandFailed|twisted.python.failure.Failure}

           @return C{dict} -> {'code': C{int}, 'description': C{str}}
        """
        
class IDroneModelDroneD(Interface):
    """Model of working with a DroneD"""
    age = Attribute("L{time.time}")
    stale = Attribute("C{bool}")
    polling = Attribute("C{bool}")
    currentFailure = Attribute("L{twisted.python.failure.Failure} or None")
    server = Attribute("L{kitt.interfaces.IDroneModleServer} provider")
    port = Attribute("C{int}")

    def sendCommand(command, keyObj, **kwargs):
        """send a droneblaster command to this DroneD Server

             @param command C{str}
             @param keyObj L{kitt.rsa.privateKey}

           Optional:
             see L{droned.client.blaster.DroneBlaster}

           @return L{twisted.internet.defer.Deferred}
        """

    def startPolling():
        """start polling this droned"""

    def stopPolling():
        """start polling this droned"""

    def poll():
        """poll this droned"""

__all__ = [
    'IDroneModelServer',
    'IDroneModelDroneServer',
]
