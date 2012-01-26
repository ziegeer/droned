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


from entity import Entity
#avoid reference leaks
import copy

__doc__ = """
Foundational library used by ROMEO to determine relationships
"""

__author__ = "Justin Venus <justin.venus@orbitz.com>"

def _processKeyValues(adict):
    """inspect dictionaries and lists to determine if relationships exist"""
    pending = [adict]
    pendlis = []

    def do_seq(seq):
        for dd in seq:
            if isinstance(dd, dict):
                pending.append(dd)
            elif isinstance(dd, (list, tuple)):
                pendlis.append(dd)

    while pending or pendlis:
        while pending:
            d = pending.pop()
            for key, val in d.iteritems():
                yield RomeoKeyValue(key, val) #we may throw duplicates, but it is ok
            do_seq(d.itervalues())
        while pendlis:
            l = pendlis.pop()
            do_seq(l)

#only used to test values in RomeoKeyValue ``search``
class EmptyValue(Entity):
    def __init__(self):
        self.name = None
null = EmptyValue()

class RomeoKeyValue(Entity):
    """Relational Key Value Pair Storage Object"""
    KEY = property(lambda s: s._key)
    VALUE = property(lambda s: s._value)
    CHILDREN = property(lambda s: (i for i in s._children))
    ANCESTORS = property(lambda s: (i for i in s._ancestors))
    RELATED = property(lambda s: (i for i in s._ancestors | s._children))
    ROOTNODE = property(lambda s: not bool(s._ancestors))
    BRANCHNODE = property(lambda s: not s.ROOTNODE)

    def __init__(self, key, value):
        self._key = key
        self._value = value
        #storage for nodes above and below us
        self._children = set()
        self._ancestors = set()

        #we need to inspect our values and discover decendants
        for obj in _processKeyValues({key: value}):
             if obj is self: continue #skip dumb relationship to self
             self._children.add(obj)
             obj.add_ancestor(self)

    def keys(self):
        """return all of the keys of my children"""
        x = set([self.KEY])
        for obj in self.CHILDREN:
            x.add(obj.KEY)
        return sorted(list(x))

    def get(self, key, default=None):
        """get the value from this oject or a child object

           @key (string)
           @default (object | None)

           @return (object | list of objects)
        """
        returnList = set()
        if self.KEY == key:
            return self.VALUE
        for obj in self.CHILDREN:
            if obj.KEY != key: continue
            returnList.add(obj)
        if not returnList:
            return default
        #this condition should not happen often
        if len(returnList) > 1:
            return list(returnList)
        else:
            return list(returnList)[0] 

    def iteritems(self):
        """iterate over the child objects

           @yield (RomeoKeyValue().KEY, RomeoKeyValue())
        """
        seen = set([self]) #just in case
        yield (self.KEY, self)
        for obj in self.CHILDREN:
            if obj in seen: continue
            yield (obj.KEY, obj)
            seen.add(obj)

    def add_ancestor(self, obj):
        """Only used by RomeoKeyValue __init__"""
        assert isinstance(obj, RomeoKeyValue)
        self._ancestors.add(obj)
        for child in self.CHILDREN:
            child.add_ancestor(obj)

    def isRelated(self, obj):
        """Test if the provided object is related to this instance
           either directly or through a shared relationship with
           another object.

           @param obj (instance RomeoKeyValue)
           @return bool
        """
        #easiest, case direct relationship
        if bool(obj in self._children | self._ancestors):
            return True
        #since this isn't a binary tree structure we have to look
        #for similarities and related top objects, avoid ROOTNODE
        objList = [obj]
        seen = set() #deduplicate and prevent infinite recursion
        while objList: #expensive relationship search
            x = objList.pop()
            for foo in x.RELATED:
                if foo in seen: continue
                else: seen.add(foo)
                if foo.isChild(self) and foo.isChild(obj):
                    if foo.ROOTNODE: #too ambiguous
                        continue #look for a better relationship
                    return True #found a common ancestor
                #further inspect object relationships
                if foo.isAncestor(self):
                    objList.append(foo)
        return False
                
    def isChild(self, obj):
        """Test if the provided object is a child of this instance

           @param obj (instance RomeoKeyValue)
           @return bool
        """
        return bool(obj in self._children)

    def isAncestor(self, obj):
        """Test if the provided object is an ancestor to this instance

           @param obj (instance RomeoKeyValue)
           @return bool
        """
        return bool(obj in self._ancestors)

    @staticmethod
    def search(key, value=null):
        if not isinstance(value, EmptyValue):
            if RomeoKeyValue.exists(key, value):
                yield RomeoKeyValue(key, value)
            return #escape after exact search
        seen = set() #avoid duplicates due to inter relationships
        for obj in RomeoKeyValue.objects:
            if not RomeoKeyValue.isValid(obj): continue
            for var, val in obj.iteritems():
                if var != key: continue
                if val in seen: continue
                yield val 
                seen.add(val) #deduplicate results @expense of memory
        del seen #force garbage collection

__all__ = ['RomeoKeyValue']
