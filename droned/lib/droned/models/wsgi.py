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
import time,os,sys
import config

from zope.interface import implements, Interface, Attribute

#the below are common imports you may not have need for them all and likely will need additional.
from twisted.python.failure import Failure
from twisted.internet import task
from twisted.internet.task import LoopingCall
from twisted.internet.defer import TimeoutError, deferredGenerator, waitForDeferred, maybeDeferred

#these are typical droned objects. Same as twsited. Common are included but do not reprsent all imports.
from droned.entity import Entity
from droned.logging import log, debug
from droned.models.event import Event

class WsgiBaseModel(Interface):
    def __init__(config):
        '''@param config: (dict) 
              copy of SERVICECONFIG dict passed to droned.service
           @return: WsgiBaseModel instance
        '''
        
    def get_wsgi_handler():
        '''returns a valid handler for WSGI
           requests.
        '''


class Django(Entity):
    serializable = False #must be set to true to serialize
    implements(WsgiBaseModel)
    
    def __init__(self, config):
        '''
        This class handles the appropriate startup of django
        and sets up required path and environment variables
        based on user specified config.
        '''
        
    def get_wsgi_handler(self):
        raise NotImplemented()
        
    

# These come after our class definitions to avoid circular import dependencies
from droned.models.droneserver import DroneD
from droned.management.server import ServerManager
