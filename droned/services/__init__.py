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

#global service container
EXPORTED_SERVICES = {}

def loadAll():
    """Loads all DroneD Services that adhere to the Interface Definition
       of IDroneDService. The resulting dictionary will return in the form
       of {"SERVICENAME": "MODULE", ...}

       :Note technically this is a private method, because the server will
       hide it from you.

       @return (dict)
    """
    from kitt.interfaces import IDroneDService
    from twisted.python.log import err
    from twisted.python.failure import Failure
    import warnings
    import config
    import os

    global EXPORTED_SERVICES

    my_dir = os.path.dirname(__file__)

    for filename in os.listdir(my_dir):
        if not filename.endswith('.py'): continue
        if filename == '__init__.py': continue
        modname = filename[:-3]
        mod = None

        try:
            mod = __import__(__name__ + '.' + modname, {}, {}, [modname])
        except:
            err(Failure(), 'Exception Caught Importing Service module %s' % \
                    (modname,))
            continue #skip further checks

        if not mod: continue #fix for sphinx documentation
        #prefer module level interfaces first and foremost
        try:
            if IDroneDService.providedBy(mod):
                EXPORTED_SERVICES[mod.SERVICENAME] = mod
                continue #module level interfaces are considered singleton services
        except TypeError: pass
        except:
            err(Failure(), 'Exception Caught Validating Module Interface %s' % \
                    (name,))
        #see if any classes implement the desired interfaces
        for name,obj in vars(mod).items():
            try:
                if IDroneDService.implementedBy(obj):
                    EXPORTED_SERVICES[obj.SERVICENAME] = obj() #instantiate now
                    warnings.warn('loaded %s' % name)
                else:
                    warnings.warn('%s from %s does not provide ' + \
                            'IDroneDService Interface' % \
                            (name,modname))
            except TypeError: pass
            except:
                err(Failure(), 'Exception Caught Validating Interface %s' % \
                        (name,))

    #apply romeo configuration to all services
    for name, obj in EXPORTED_SERVICES.items():
        try: obj.SERVICECONFIG.wrapped.update(config.SERVICES.get(name, {}))
        except:
            err(Failure(), 'Exception Caught Setting Configuration %s' % \
                    (modname,))

    return EXPORTED_SERVICES


def getService(name):
    """Get the Service Objects"""
    global EXPORTED_SERVICES
    if name not in EXPORTED_SERVICES:
        from droned.errors import ServiceNotAvailable
        raise ServiceNotAvailable(name)
    return EXPORTED_SERVICES[name]


def listServices():
    """list the services by name that DroneD is providing"""
    global EXPORTED_SERVICES
    return EXPORTED_SERVICES.keys()
