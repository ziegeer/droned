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

class IDroneModelEvent(Interface):
    subscribers = Attribute("C{set} contains all subscribed callbacks")
    name = Attribute("C{str} name of the event")
    enabled = Attribute("C{bool} dis/allows event firing")

    def fire(**params):
        """fires event to all subscribers which will receive a copy of
           of L{kitt.interfaces.IDroneEventOccurrence} provider.
        """

    def subscribe(obj):
        """subscribe to this event

           @param obj C{callable}
           @return obj
        """

    def unsubscribe(obj):
        """unsubscribe from this event

           @param obj C{callable}
           @return None
        """

    def enable():
        """allow this event to fire"""


    def disable():
        """prevents this event from firing"""


class IDroneEventOccurrence(Interface):
    """I get passed to subscribers of L{kitt.interfaces.IDroneModelEvent}
       providers.
    """
    event = Attribute("L{kitt.interfaces.IDroneModelEvent} provider")
    name = Attribute("C{str} Name of the original event")
    params = Attribute("C{dict} data passed when the event fired")

    def __init__(event, **params):
        """the constructor is tightly tied to the
           L{kitt.interfaces.IDroneModelEvent} provider that instantiated it

           @param event L{kitt.interfaces.IDroneModelEvent} provider
           @param params **C{dict} 

           !!Note about params!!
           should update the interanal __dict__ attribute as well as becoming
           the attribute ``params``, until further notice legacy code expects 
           this behavior.
       """

__all__ = [
    'IDroneModelEvent',
    'IDroneEventOccurrence'
]
