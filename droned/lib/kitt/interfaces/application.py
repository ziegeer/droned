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

class IDroneDApplication(Interface):
    """Core Application Interface that plugins must implement"""
    name = Attribute("C{str} name of the application")

    def recoverInstance(occurance):
        """Recover Crashed Instances of the Application.
           this method should be subscribed to Event('instance-crashed')

           @param occurance: (object)
           @return defer.Deferred()
        """

    def getInstance(label):
        """
           @param label: string which identifies an app instance

           @return: object that represents the instance
        """

    def startInstance(label):
        """
           @param label: string which identifies an app instance

           Return a L{twisted.internet.defer.Deferred} that will
           result in a dictionary with the key 'pid' as ${int}
           or a Failure describing the problem.
        """

    def stopInstance(label):
        """
           @param label: string which identifies an app instance

           @return L{twisted.internet.defer.Deferred}
        """

    def statusInstance(label):
        """
           @param label: string which identifies an app instance

           @return: dictionary describing the status of the app instance
        """

###############################################################################
# DroneD Model Description 
###############################################################################
class IDroneModelApp(Interface):
    """Model Describing An Application"""
    name = Attribute("Declare the name of the app")
    shouldRunOn = Attribute("""
        set of L{kitt.interfaces.IDroneModelServer} this 
        L{kitt.interfaces.IDroneModelApp} provider runs on""")
    managedOn = Attribute("""
        provide an iterable of what L{kitt.interfaces.IDroneModelServer} run 
        this ${kitt.interfaces.IDroneModelApp} provider""")
    configuredOn = Attribute("""
        provide an iterable of what L{kitt.interfaces.IDroneModelServer} have 
        an L{kitt.interfaces.IDroneModelAppInstance} provider configured""")
    appversions = Attribute("""
        provide an iterable of known L{kitt.interfaces.IDroneModelAppVersion} 
        providers""")
    appinstances = Attribute("""
        provide an iterabe of known L{kitt.interfaces.IDroneModelAppInstance} 
        providers""")
    localappinstances = Attribute("""
        provide an iterabe of local 
        L{kitt.interfaces.IDroneModelAppInstance} providers""")
    runningInstances = Attribute("""
        provide an iterable of running 
        L{kitt.interfaces.IDroneModelAppInstance} providers""")
    localrunningInstances = Attribute("""
        provide an iterable of local running 
        L{kitt.interfaces.IDroneModelAppInstance} providers""")
    
    def runsOn(server):
        """declare this L{kitt.interfaces.IDroneModelServer} runs this 
           L{kitt.interfaces.IDroneModelApp} provider
        """

    def doesNotRunOn(server):
        """declare this L{kitt.interfaces.IDroneModelServer} provider does not 
           run this L{kitt.interfaces.IDroneModelApp} provider
        """

class IDroneModelAppVersion(Interface):
    """Model Describing An Application Version"""
    description = Attribute("Describes the Application and Version")
    app = Attribute("L{kitt.interfaces.IDroneModelApp} provider")
    version = Attribute("L{twisted.python.versions.Version}")

    def makeVersion(version):
        """take a version object and return a L{twisted.python.versions.Version}"""
  
 
class IDroneModelAppInstance(Interface):
    """Model Describing an Application Instance"""
    #in the constructor
    appversion = Attribute("L{kitt.interfaces.IDroneModelAppVersion} provider")
    app = Attribute("L{kitt.interfaces.IDroneModelApp} provider")
    server = Attribute("L{kitt.interfaces.IDroneModelServer} provider")
    shouldBeRunning = Attribute("C{bool}")
    label = Attribute("C{str}")
    context = Attribute("C{dict} Contains arbitrary information, is not persistant")
    info = Attribute("""
        C{dict} Contains information about the 
        L{kitt.interfaces.IDroneModelAppInstance} provider, this attribute is 
        persistant""")
    version = Attribute("L{twisted.python.versions.Version}")
    #as class instance properties
    crashed = Attribute("is the instance crashed")
    state = Attribute("""
        describe the application state; 'not running', 'crashed', or 'up'""")
    description = Attribute("description of the application instance")
    localInstall = Attribute("""
        state whether or not the L{kitt.interfaces.IDroneModelAppInstance} 
        provider is on this L{kitt.interfaces.IDroneModelServer} provider""")
    pid = Attribute("Process ID if running")
    running = Attribute("""
        state if this L{kitt.interfaces.IDroneModelAppInstance} provider 
        is running""")
    process = Attribute("L{kitt.interfaces.IDroneModelAppProcess} provider")
    enabled = Attribute("""
        whether or not this L{kitt.interfaces.IDroneModelAppProcess} provider
        is enabled""")

    def enabler(occurrence):
        """allow this instance to be dis/enabled

           @param occurrence should contain an attibute of 
              L{kitt.interfaces.IDroneModelAppInstance} provider

           should modify the state of ``enabled`` attribute of this
           L{kitt.interfaces.IDroneModelAppInstance} provider
           @return None
        """

    def updateInfo(info):
        """Apply new information to the attribute ``info`` of this
           L{kitt.interfaces.IDroneModelAppInstance} provider

           @param info C{dict}
           @return None
        """

    def start():
        """Start my Application

           @return L{twisted.internet.defer.Deferred}
        """

    def stop():
        """Stop my Application

           @return L{twisted.internet.defer.Deferred}
        """

    def restart():
        """Restart my Application

           @return L{twisted.internet.defer.Deferred}
        """

#FIXME required attributes are missing
class IDroneModelAppManager(Interface):
    """Model that manages L{kitt.interfaces.IDroneDApplication} provider Plugins"""

    def log(message, label):
        """logs messages

           @return None
        """

    def start():
        """called when the plugin is ready, exposes methods, and starts an eventloop

           @return None
        """

    def stop():
        """called when the plugin is ready to be torn down, unexposes methods, and
           stops the eventloop

           @return None
        """

    def conditionalEvents():
        """check if conditions have been met to call ``fire`` on a
           L{kitt.interfaces.IDroneModelApplicationEvent} provider

           @return None
        """

    def registerEvent(name, callback, **kwargs):
        """calls ``subscribe`` method of 
           L{kitt.interfaces.IDroneModelApplicationEvent} provider

           @param name C{str} name of the event
           @param callback C{callable}

           Optional: see L{kitt.interfaces.IDroneModelApplicationEvent} 
           @return None
        """

    def triggerEvent(name, data, delay):
        """trigger an L{kitt.interfaces.IDroneModelApplicationEvent}
           @param data L{object}
           @param delay C{int|float}

           @return None
        """

    def disableEvent(name):
        """prevent a condition or re-ocurring event from firing

           @return None
        """

    def enableEvent(name):
        """allow a condition or re-ocurring event to fire

           @return None
        """

    def expose(name, method, args, doc, **kwargs):
        """register a method by name to L{kitt.interfaces.IDroneModelDroneServer}
           this is bound to a L{kitt.interfaces.IDroneAdminAction}

             @param name C{str}
             @param method C{callable}
             @param args C{tuple}
             @param doc C{str}

           Optional:
             @param INSTANCED C{bool}  - sets the instanceOperator decorator for
                                         administrator's ease of use.
             @param BUSYLOCK C{bool}   - sets the synchronizedDeferred decorator
                                         for this L{IDroneModelAppManager}.
             @param GLOBALLOCK C{bool} - sets the synchronizedDeferred decorator for
                                         synchronizing all L{IDroneModelAppManager}.
           @return None
        """
        
    def unexpose(name, blacklist):
        """unregister a method by name or block registration of the named method

           @param name C{str} name of method to unexpose
           @param blacklist C{bool} whether or not to blacklist the method
           @return None
        """

    def rebuildHelp():
        """rebuilds the help documentation for exposed methods

           @return None
        """

    def addInstance(label):
        """creates a new L{kitt.interfaces.IDroneModelAppInstance} provider
           works through L{kitt.interfaces.IDroneDApplication} provider

           @param lable C{str}
           @return None
        """

    def removeInstance(label):
        """deletes a L{kitt.interfaces.IDroneModelAppInstance} provider
           works through L{kitt.interfaces.IDroneDApplication} provider

           @param lable C{str}
           @return None
        """

    def enableInstance(label):
        """enables L{kitt.interfaces.IDroneModelAppInstance} provider

           @param lable C{str}
           @return None
        """

    def disableInstance(label):
        """disables L{kitt.interfaces.IDroneModelAppInstance} provider

           @param lable C{str}
           @return None
        """

    def startInstance(label):
        """starts application via L{kitt.interfaces.IDroneDApplication} provider

           @param lable C{str}
           @return C{dict}
        """

    def stopInstance(label):
        """stops application via L{kitt.interfaces.IDroneDApplication} provider

           @param lable C{str}
           @return C{dict}
        """

    def statusInstance(label):
        """reports the status of the application via 
           L{kitt.interfaces.IDroneDApplication} provider

           @param lable C{str}
           @return C{dict}
        """

    def instanceOperation(func):
        """decorates methods to make 'all' or '*' iterate through all possible
           instances of a method.

           @param func C{callable}
           @return C{callable}
        """

class IDroneModelApplicationEvent(Interface):
    """fine grained eventing"""
    event = Attribute("L{IDroneModelEvent} provider")
    name = Attribute("C{str} name of the event")
    service = Attribute("C{str} name of the L{IDroneAppManager} provider")
    condition = Attribute("C{bool}")
    recurring = Attribute("C{float}")
    silent = Attribute("C{bool}")
    func = Attribute("C{callable} called when condition or deadline is met")

    def trigger(data, delay):
        """fires the event out of band reguardless of condition or deadline 
           state.

           @param data C{object}
           @param delay C{float}

           @return None
        """

__all__ = [
    'IDroneModelApplicationEvent',
    'IDroneDApplication',
    'IDroneModelAppInstance',
    'IDroneModelAppVersion',
    'IDroneModelApp',
    'IDroneModelAppManager'
]
