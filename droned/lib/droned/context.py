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

noDefault = object()

from kitt.interfaces import IEntityContext, implements

class EntityContext(object):
    """Abstract base class for representing context about an Entity with
       read-only metadata transparently mixed in as "special keys".
       Subclasses must override entityAttr and specialKeys attributes and
       for each specialKey a get_<key> method must be implemented.
    """

    implements(IEntityContext)
    entityAttr = None
    specialKeys = []

    def __init__(self, entity):
        #Verify that the subclass conforms to the API
        assert self.entityAttr is not None
        for key in self.specialKeys:
            assert hasattr(self, 'get_' + key)

        setattr(self, self.entityAttr, entity)
        self.data = {}

    def __getitem__(self, key):
        if key in self.specialKeys:
            accessor = getattr(self, 'get_' + key)
            return accessor()

        if key in self.data:
            return self.data[key]
        else:
            entity = getattr(self, self.entityAttr)
            raise KeyError("\"%s\" is not in the %s context" % (key, entity))

    def __setitem__(self, key, value):
        if key in self.specialKeys:
            raise KeyError("Cannot override special key \"%s\"" % key)
        self.data[key] = value

    def __delitem__(self, key):
        if key in self.specialKeys:
            raise KeyError("Cannot delete special key \"%s\"" % key)
        del self.data[key]

    def __contains__(self, key):
        return key in self.data or key in self.specialKeys

    def __iter__(self):
        for key in self.specialKeys:
            yield key
        for key in self.data:
            yield key

    def get(self, key, default=noDefault):
        try:
            return self[key]
        except KeyError:
            if default == noDefault:
                raise
            else:
                return default

    def pop(self, key, default=noDefault):
        try:
            return self.data.pop(key)
        except KeyError:
            if default == noDefault:
                raise
            else:
                return default

    def keys(self):
        return list(self)

    def values(self):
        return [ self[key] for key in self ]

    def items(self):
        return [ (key, self[key]) for key in self ]

    def update(self, otherDict):
        return self.data.update(otherDict)

    def clear(self):
        return self.data.clear()

    def copy(self):
        return dict( self.items() )

    def __repr__(self):
        return repr( self.copy() )
