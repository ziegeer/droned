from romeo.entity import Entity as _Entity
from romeo.entity import InValidEntity as _InValidEntity
from romeo.entity import namespace as _namespace

__doc__ = """
The entire purpose of this library package is to give us
a mechanism to distinguish droned models from romeo data
configuration objects.  So in the event romeo supports 
serialization of configuration droned doesn't duplicate
the effort via the journal service.
"""
#nothing is currently using the namespace, but that doesn't mean
#that we won't have a use for it in the future.
namespace = _namespace
#wrap over these for the journal service's benifit
InValidEntity = _InValidEntity #so we can catch original exceptions
#wrapped so we can determine droned models from romeo data objects
#because now we have different modules to distinguish ourselves
#from the data configuration objects.
class Entity(_Entity): pass

__all__ = ['Entity', 'InValidEntity']
