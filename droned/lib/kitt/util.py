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

import sys, os, socket, threading, struct, traceback, time
from twisted.python.failure import Failure

class ClassLoader(object):
    '''A simple and generic class loader to be subclassed by more specific loaders.
       This loader only handles the simple case where you have defined classes of a
       certain zope interface in the same module file as the class loader.
       If your module has classes of a certain interafce type you can use
       this loader to allow importing classes to dynamically load them.
       Set the class variable interface_type to the zope interface class you 
       wish to load.
       
       "developer usage": 
         from kitt.util import ClassLoader
         from foo.bar import BarLoader
         class FooLoader(ClassLoader): #in module foo as an example
           interface_type = IFoo
           subloaders = []
          
          FooLoader.add_subloader(BarLoader) 
           
       "user usage":
       from foo import MyLoader
       classes = FooLoader.load() #class of type IFoo and IBar 
       
       #1 zope interface class to load classes of this type.
       #2 this variable must be recreated on subclasses to get a new reference
          to an empty list. Otherwise you may polute another class' loaders.
        
    '''
    
    interface_type = None #1
    subloaders = [] #2
    
    @classmethod
    def load(cls,acc=None):
        if type(acc) == list: out = acc
        else: out = []
        mm = sys.modules[cls.__module__]
        if not hasattr(cls.interface_type,"implementedBy"): return out
        for k in dir(mm):
            try:
                v = getattr(mm,k)
                if cls.interface_type.implementedBy(v):
                    out.append(v)
            except: pass
        for loader in cls.subloaders: loader.load(out)
        return out
    
    @classmethod 
    def add_subloader(cls,loader):
        '''add a child loader to this loader. All classes from all children
           will be returned from the load() call.
        '''
        gaurd = hasattr(loader,"load") and hasattr(loader,"add_subloader")
        if gaurd: cls.subloaders.append(loader)
#make sure we don't leak references
ClassLoader = type(
    'ClassLoader', 
    (ClassLoader,), 
    {'interface_type': None, 'subloaders': list()}
)        


def getException(failure=None):
  'gets the last exception raised by the interpretor'
  info = sys.exc_info()[0]
  if failure and isinstance(failure, Failure):
      try: return failure.value.__class__.__name__
      except: pass
  if not info: return
  return info.__name__

portsLock = threading.Lock() #Damn non-reentrant generators
regenPorts = lambda: set(range(20000,65536))
portsIterator = regenPorts()

def getAvailablePort():
  'finds an available tcp port for later assignment'
  global portsIterator
  portsLock.acquire()
  for port in portsIterator:
    s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    try:
      s.bind(('',port))
    except:
      continue
    s.close()
    portsIterator.remove(port)
    portsLock.release()
    return port
  portsIterator = regenPorts()
  portsLock.release()
  return getAvailablePort()

def unpackify(s):
  'Unpacks the magic number from a DroneD message'
  n = 0
  while True:
    n += struct.unpack("!B",s[-1])[0]
    s = s[:-1]
    if not s: return n
    n <<= 8

class dictwrapper(object):
  """
  A neat dictionary wrapper written by Chris Brinley.

  makes a dictionary feel more natural.

  usage:

    a = { 'foo' : 'bar' }
    x = dictwrapper( a )
    print x.foo
    >>> 'bar'
    x.baz = '1'
    print x.wrapped
    >>> { 'foo' : 'bar', 'baz' : '1' }

  neat!!!
  """
  def __init__(self,inputDict=None):
    if not inputDict: inputDict = {}
    if inputDict.__class__ == dictwrapper: inputDict = inputDict.wrapped
    object.__setattr__(self, "wrapped", inputDict)
  def __getattr__(self,key):
    if key in self.wrapped: return self.wrapped[key]
    elif hasattr(self.wrapped,key): return  getattr(self.wrapped,key)
    else: return None
  def __setattr__(self,key,value):
    if hasattr(self.wrapped,key):
      raise AttributeError("%s object has no attribute %s" % (self.__class__,key) )
    self.wrapped[key] = value
  def __getitem__(self,key):
    if type(key) == slice: return self.__getslice__(key)
    return self.wrapped[key]
  def __setitem__(self,key,value):
    self.wrapped[key] = value
  def __contains__(self,key):
    return key in self.wrapped
  def __iter__(self):
    for k in self.wrapped: yield k
  def __getslice__(self,_slice):
    ret = []
    for k in self.wrapped:
      if _slice.start and _slice.stop:
        if k.startswith(_slice.start) and k.endswith(_slice.stop): ret.append(k)
      elif _slice.start and not _slice.stop:
        if k.startswith(_slice.start): ret.append(k)
      elif not _slice.start and _slice.stop:
        if k.endswith(_slice.stop): ret.append(k)
      else: ret.append(k)
    outvals = []
    for k in ret:
      if _slice.step: outvals.append( (k,self.wrapped[k]) )
      else: outvals.append(self.wrapped[k])
    return outvals


def crashReport(header, obj=None):
    """Tell the user what happened during an unhandled exception"""
    sys.stdout.write('\n')
    sys.stdout.write('############################# EXCEPTION REPORT START\n')
    sys.stdout.write('%s\n' % header)
    sys.stdout.write('Date/Time  : %s\n' % str(time.asctime()))
    sys.stdout.write('Class      : %s\n' % str(obj.__class__))
    sys.stdout.write('Exception  : %s\n' % str(sys.exc_info()[0]))
    sys.stdout.write('Description: %s\n' % str(sys.exc_info()[1]))
    sys.stdout.write('Trace      :\n\n')
    traceback.print_tb(sys.exc_info()[2], file=sys.stdout)
    sys.stdout.write('\n############################# EXCEPTION REPORT END\n')
    sys.stdout.write('\n')

class LazinessException(Exception): pass
class ImpossibilityException(Exception): pass

#python2.4 support
try: all
except NameError:
    def all(iterable):
        for element in iterable:
            if not element:
                return False
        return True

try: any
except NameError:
    def any(iterable):
        for element in iterable:
            if element:
                return True
        return False
