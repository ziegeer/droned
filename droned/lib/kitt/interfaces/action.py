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

class IDroneModelAction(Interface):
    """I provide a Model to Track Actions and the outcome"""
    completed = Attribute("C{bool}")
    succeeded = Attribute("C{bool}")
    failed = Attribute("C{bool}")
    stale = Attribute("C{bool}")
    startedAt = Attribute("L{time.time}")
    finishedAt = Attribute("L{time.time}")
    description = Attribute("C{str}")
    deferred = Attribute("L{twisted.internet.defer.Deferred}")
    outcome = Attribute("""
        None, L{object}, or L{twisted.python.failure.Failure}""")

    def __init__(description, deferred):
        """Expected constructor signature"""

class IDroneModelAdminAction(Interface):
    """I provide a Model to administratively control DroneD

       This interface was originally designed to deal with
       application management exclusively, but over time it became 
       generic enough to handle almost any administrative scenario.
    """
    exposedMethodInfo = Attribute("C{list}")
    exposedMethods = Attribute("C{dict}")
    action = Attribute("C{str}")

    def __init__(action):
        """Expected constructor signature"""

    def __call__(argstr):
        """Expected to be callable, I parse the argstr and call
           my ``invoke`` method.

           @param argstr C{str} -> 'ping', 'service list', etc ...

           @callback C{dict}
           @errback N/A

           !!Note Failures are converted to dictionaries!!

           @return L{twisted.internet.defer.Deferred} 
        """
        
    def log(message):
        """provides a logging hook

           @param message C{object}
           @return None
        """ 

    def buildDoc():
        """should be called after all methods have been exposed and you
           wish to finalize this model
        """

    def resultContext(template, instance, **context):
        """takes a template and applies the intance and context to format
           a descriptions

           @param template C{str} should accept 'print template % context'

           Optional:
           @param intance L{kitt.interfaces.IDroneModelApplicationInstance}

           #at least the following information should be returned
           @return C{dict} -> {'code': C{int}, 'description': C{str}} or
             L{twisted.python.failure.Failure}
        """

    def invoke(name, args):
        """Invoke Exposed Methods
           @param name C{str} - name of method to invoke
           @param args C{tuple} - arguments to pass to invoked method

           @errback L{droned.errors.DroneCommandFailed}
           @callback C{object}
           @return L{twisted.internet.defer.Deferred}
        """

    def expose(name, method, args, doc):
        """Exposes a method for administrative usage.

           @param name C{str}
           @param method C{callable}
           @param args C{tuple} form ((C{str}), ...) named positional arguments
           @param doc C{str} -> administative documentation .. (ie usage)

           @return None
        """

    def unexpose(self, name):
        """Removes an exposed method

           @param name C{str}

           @return None
        """


__all__ = [
    'IDroneModelAction',
    'IDroneModelAdminAction'
]
