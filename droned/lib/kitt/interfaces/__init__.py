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

__doc__ = """Provides zope interface definitions for the rest of DroneD"""

import os
my_dir = os.path.dirname(__file__)

INTERFACES = set()

#load all of the interface definitions
for filename in sorted(os.listdir(my_dir)):
    if not filename.endswith('.py'): continue
    if filename == '__init__.py': continue
    modname = filename[:-3]
    mod = None
    interface = None

    try:
        mod = __import__(__name__ + '.' + modname, {}, {}, [modname])
    except:
        continue #skip further checks

    if not mod: continue #fix for sphinx documentation

    if not hasattr(mod, '__all__'):
        continue #we won't just blindly import

    for interface in mod.__all__:
        globals()[interface] = vars(mod)[interface]
        INTERFACES.add(interface)


#for convenience, these are bought in as well
from zope.interface import implements, moduleProvides, implementer
from twisted.python import components

__all__ = list(set([
    'components',
    'implementer',
    'implements',
    'moduleProvides'
]) | INTERFACES)

#clean up
del INTERFACES
del interface
del filename
del modname
del my_dir
del mod
del os
