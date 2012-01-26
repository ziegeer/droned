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
import socket as _socket
import glob as _glob
import yaml as _yaml
import copy as _copy
import sys as _sys
import os as _os
import re as _re

#don't be evil by overriding this
try:
    MYHOSTNAME = _socket.getfqdn()
    #add more failures to the tuple as they are discovered
    assert MYHOSTNAME not in ('localhost','localhost.localdomain',\
        'localhost6.localdomain6','localhost6')
    #i believe this should be exactly == 3 and will wait on a bug report to 
    #resolve that question.
    assert len(MYHOSTNAME.split('.')) >= 3
except AssertionError:
    MYHOSTNAME = _socket.gethostname()
    e = """
ROMEO could not reliably determine the fully qualified name of this machine.
ROMEO is using the hostname ``%(MYHOSTNAME)s`` for configuration resolution.

If you are sure this machine's hostname is resolvable in DNS check
nsswitch.conf or similar convention if you have a strange OS.


  $ grep ^hosts: /etc/nsswitch.conf

  #you should have ``dns`` listed in the result.
  hosts:      dns files mdns4_minimal [NOTFOUND=return]


set the environment variable `ROMEO_IGNORE_FQDN` to suppress this warning.
    """ % locals()
    if 'ROMEO_IGNORE_FQDN' not in _os.environ:
        import warnings as _warnings
        _warnings.warn(e)
        

class EnvironmentalError(Exception): pass
class IdentityCrisis(Exception): pass

###############################################################################
# Public Methods
###############################################################################
    
def reload(datadir=None):
    """Re/load Romeo data files parse them and create object
       relationships if required

       @param datadir (string) - directory
       @return None
    """
    from romeo.directives import Preprocessor
    if not datadir:
        datadir = _os.getenv('ROMEO_DATA','/etc/hostdb')
    pp = Preprocessor(datadir)
    for f in _glob.glob('%s/*.yaml' % (datadir,)):
        try:
            fd = open(f, 'r')
            outstr = pp.pre_process(fd,f)
            fd.close()
            rd = _copy.deepcopy(_yaml.load(outstr))
            rd.append({'FILENAME': f})
            pp.post_process(rd,f)
            foundation.RomeoKeyValue('ENVIRONMENT', rd)
        except: _traceback.print_exc()
    pp.shutdown()
    Preprocessor.delete(pp) #invalidate the Entity now

def listEnvironments():
    """List all known Romeo Environments.

       @return list of romeo.foundation.KeyValue instances
    """
    x = set()
    for node in foundation.RomeoKeyValue.objects:
        if not node.ROOTNODE: continue
        x.add(node)
    return list(x)

def getEnvironment(name):
    """Get an environment with the given ```name``` attribute in
       it's romeo configuration file.

       @param name (string)
       @return romeo.foundation.KeyValue instance
    """
    for node in foundation.RomeoKeyValue.search('NAME', value=name):
        for obj in node.ANCESTORS:
            if not obj.ROOTNODE: continue
            if not obj.isRelated(node): continue
            return obj
    raise EnvironmentalError('no environment %s' % (name,))

def whoami(hostname=MYHOSTNAME):
    """Given a hostname return the Romeo object"""
    try:
        for host in foundation.RomeoKeyValue.search('HOSTNAME', value=hostname):
            for ancestor in host.ANCESTORS:
                if ancestor.KEY != 'SERVER': continue
                return ancestor
    except IndexError: pass
    raise IdentityCrisis('you appear to be having an identity crisis')


###############################################################################
# Avoid importation circularites
###############################################################################
#internal library packages
import entity
import foundation
import grammars
#FIXME in flux
#import rules

###############################################################################
# Private Class becomes 'romeo' module on instantiation
###############################################################################
class _Romeo(entity.Entity):
    def __init__(self):
        self._data = dict( (name,value) for name,value in globals().iteritems() )
        #this isn't as evil as it seems
        _sys.modules['romeo'] = self
        #reset the module globals after overriding sys.modules
        for var, val in self._data.iteritems():
            globals()[var] = val
            if var.startswith('_'): continue
            setattr(self, var, val)
        #load the grammar query rules
        self.grammars.loadAll()
#FIXME
        #load the validation rules
#        self.rules.load()
        #validate the configuration
#        self.rules.validate()

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

_Romeo = _Romeo() #hacktastic singleton becomes 'romeo' module
