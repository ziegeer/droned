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


from droned.entity import Entity
from kitt.decorators import raises
class InvalidIntervalException(Exception):pass

class Interval(Entity):
    serializable = False
    TIMESPANS = {
      "s" : 1,
      "m" : 60,
      "h" : 3600,
      "d" : 86400,
      "w" : 604800,
      "y" : 31536000,
    }
    
    @raises(InvalidIntervalException)
    def __init__(self,timestr):
        self.timestr = timestr
        self.seconds = self.convert(timestr)
        
    def convert(self,timestr):
        span_type = timestr[-1]
        if span_type not in timestr:
            raise InvalidIntervalException("%s does not contain a valid time string." % timestr)
        mult = self.TIMESPANS[span_type]
        time_base = float(timestr[:-1])
        return time_base * mult 
        
# These come after our class definitions to avoid circular import dependencies
from droned.models.droneserver import DroneD
from droned.management.server import ServerManager