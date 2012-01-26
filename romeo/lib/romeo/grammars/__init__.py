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

#standard library imports
import traceback as _traceback
import types as _types
import sys as _sys
import re as _re
import os as _os
#romeo library imports
from romeo.entity import Entity as _Entity

class NoMatch(Exception): pass

###############################################################################
# Private Class becomes the module 'romeo.grammars' on instantiation
###############################################################################
class _Query(_Entity):
    HANDLERS = property(lambda s: s._handler)
    def __init__(self):
        #where to store the handlers
        self._handler = {}
        #global module data
        self._data = dict( (name,value) for name,value in globals().iteritems() )
        #not so evil
        _sys.modules['grammars'] = self
        #reset the module globals after overriding sys.modules
        for var, val in self._data.iteritems():
            globals()[var] = val
            if var.startswith('_'): continue
            setattr(self, var, val)

    def __getitem__(self, param):
        return self._data.get(param)

    def __setitem__(self, param, value):
        self._data[param] = value

    def __delitem__(self, param):
        if param in self._data:
            del self._data[param]

    def __getattr__(self, param): #compatibility hack
        try:
            return self._data[param]
        except KeyError:
            raise AttributeError("%s has no attribute \"%s\"" % (self, param))

    def __iter__(self):
        for key,value in sorted(self._data.items()):
            yield (key,value)


###############################################################################
# Public Search Method
###############################################################################
def search(querystring):
    """Given a ``querystring`` dispatch it to the appropriate function

       @exception RuntimeError - if lookup function isn't a generator
       @exception NoMatch - if lookup function isn't found for ``querystring``

       @param querystring (string)
       @return callable - called
    """
    for regex,func in _Query._handler.iteritems():
        match = regex.search(querystring)
        if not match: continue
        obj = func(**match.groupdict())
        if not isinstance(obj, _types.GeneratorType):
            raise RuntimeError('Method %s is not a generator!!!' % str(func))
        return obj
    raise NoMatch()

###############################################################################
# Public Decorator Method
###############################################################################
def query(**attrs):
    """Decorator for defining query functions

       ALL Decorated METHODS must be GENERATORS!!!!! If you don't adhere to
       this expect RuntimeErrors to be thrown by ``romeo.grammars.search`` 
       method!! You have been warned.

       ``@query(pattern="^(\?|help) ?(?P<regex>\S+)?", form="? [regex]", 
          help="Display help, optionally filtered")
         def help_function(regex):
             ...
       ``

       @param attrs: - required
           pattern (string) - must work with re.compile
       @param attrs: - optional
           form (string) - example notation for help
           help (string) - human readable explanation

       @return callable
    """
    if 'pattern' not in attrs:
        raise AssertionError("Query functions must have a 'pattern' attribute")
    defaults = {
        'form' : "<unknown form>",
        'help' : '???',
    }

    def apply_attrs(func):
        defaults.update(func.__dict__)
        func.__dict__.update(defaults)
        func.__dict__.update(attrs)
        func.__doc__ = "'%(form)s':\n\t\t%(help)s\n" % func.__dict__
        #register the function and pattern for later dispatching
        _Query._handler[ _re.compile(func.pattern) ] = func
        return func

    return apply_attrs

def get_handlers():
    """returns the query handler dictionary"""
    return _Query.HANDLERS

###############################################################################
# Private Query Loader Method
###############################################################################
def loadAll():
    """this method should only be called by the 'romeo' module"""
    #import all builtin query handlers now
    my_dir = _os.path.dirname(__file__)
    for filename in _os.listdir(my_dir):
        if not filename.endswith('.py'): continue
        if filename == '__init__.py': continue
        modname = filename[:-3]
        try:
            try:
                mod = __import__(__name__ + '.' + modname, fromlist=[modname])
            except TypeError:
                #python2.4 __import__ implementation doesn't accept **kwargs
                mod = __import__(__name__ + '.' + modname, {}, {}, [modname])
        except:
            _traceback.print_exc()
        
_Query = _Query() #hacktastic singleton becomes 'romeo.grammars'
