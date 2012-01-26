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

class IEntityContext(Interface):
    """Abstract base class for representing context about an Entity with
       read-only metadata transparently mixed in as "special keys".
       Subclasses must override entityAttr and specialKeys attributes and
       for each specialKey a get_<key> method must be implemented.

       Think of this as a glorified dictionary.
    """
    entityAttr = Attribute("C{str}")
    specialKeys = Attribute("C{list} of ${str}")

    def get(key, default):
        """see C{dict}.get"""

    def pop(key, default):
        """see C{dict}.pop"""

    def keys():
        """see C{dict}.keys"""

    def values():
        """see C{dict}.values"""

    def items():
        """see C{dict}.items"""

    def update(otherDict):
        """see C{dict}.update"""

    def clear():
        """see C{dict}.clear"""

    def copy():
        """see C{dict}.copy"""


class IConversationContext(IEntityContext):
    """I provide contextual information about a conversation."""
    def get_conversation():
        """@return L{IDroneModelConversation} provider"""

    def get_buddy():
        """@return C{str}"""

#FIXME support agent interface doesn't exist
    def get_agent():
        """@return L{IDroneModelSupportAgent} provider"""

    def get_issue():
        """@return L{IDroneModelIssue} provider"""

#FIXME sop interface and code doesn't exit
    def get_sop():
        """@return L{IDroneModelSop} provider"""


__all__ = [
    'IEntityContext',
    'IConversationContext'
]
