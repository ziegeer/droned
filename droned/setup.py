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

import os
import sys
from glob import glob

#FIX FOR RPMBUILD
WHEREAMI = os.path.realpath(os.path.curdir)

_f = open(os.path.join(WHEREAMI,'..','VERSION'),'r')
VERSION = _f.read().strip()
_f.close()

copyright_module = "version = \"" + str(VERSION) + "\""
copyright_module += """
copyright = "Copyright (c) 2006 to the present, Orbitz Worldwide, LLC."
copyright_notice = '''Copyright (c) 2006 to the present, Orbitz Worldwide, LLC.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''
__doc__ = copyright_notice
"""

_f = open(os.path.join(WHEREAMI,'copyright.py'),'w')
_f.write(copyright_module)
_f.close()

#FIXME this is a hack but i need to get this done
if os.path.exists('setup.cfg'):
    from ConfigParser import ConfigParser as _cf

    _config = _cf()
    _config.read('setup.cfg')
    
    _blaster = {
        'executable': sys.executable,
        'script': os.path.join(
                _config.get('install','install-lib'),
                'droneclient.py'
            ),
    }

    _droned = {
        'executable': sys.executable,
        'script': os.path.join(
                _config.get('install','install-lib'),
                'droned-daemon.py'
            ),
    }

    #write the blaster wrapper
    blaster = open(os.path.join('bin','droneblaster'), 'w')
    blaster.write("""#!/bin/sh\nexec %(executable)s %(script)s "$@"\n""" % \
            _blaster)
    blaster.close()

    #write the daemon wrapper
    droned = open(os.path.join('bin','droned'), 'w')
    droned.write("""#!/bin/sh\nexec %(executable)s %(script)s "$@"\n""" % \
            _droned)
    droned.close()


from distutils.core import setup
setup_kwargs = dict()

#build primes file if the user requests it to be changed
if os.environ.get('PRIME_SIZE'):
    import math
    import struct

    def primes(n):
        if n < 4000:
            raise AssertionError('PRIME_SIZE must be greater than 4000 entries')
        s = range(3,n,2)
        mroot = math.sqrt(n)
        half = (n+1)/2
        i = 0
        m = 3
        while m <= mroot:
            if s[i]:
                j = (m * m - 3) / 2
                try: s[j] = 0
                except: pass
                while j < half:
                    try: s[j] = 0
                    except: pass
                    j += m
            i += 1
            m = 2 * i + 3
        [fh.write(struct.pack("!L",n)) for n in s if n]

    fh = open(os.path.join(WHEREAMI, 'primes'),'w')
    primes(int(os.environ.get('PRIME_SIZE')))
    fh.close()

#fix for rpmbuild
doc_files = [ ('doc', [ os.path.join(WHEREAMI, i) for i in glob('doc/*') \
        if os.path.isfile(i)]) ]
_data = [
    'primes'
]
#fix for rpmbuild
extra_files = [ ('.', [ os.path.join(WHEREAMI, i) for i in _data \
        if os.path.isfile(i)]) ]

setup(
    name='droned',
    version=VERSION,
    url='https://github.com/OrbitzWorldwide/droned',
    author='Justin Venus',
    author_email='justin.venus@orbitz.com',
    license='Apache Software License 2.0',
    description='DroneD - Application Service Framework',
    packages=[
        '.',
        'services',
        'lib.droned',
        'lib.droned.applications',
        'lib.droned.responders',
        'lib.droned.clients',
        'lib.droned.models',
        'lib.droned.management',
        'lib.droned.management.dmx',
        'lib.droned.protocols',
        'lib.droned.events',
        'lib.kitt',
        'lib.kitt.proc',
        'lib.kitt.numeric',
        'lib.kitt.interfaces'
    ],
    package_dir={'': ''},
    data_files=doc_files + extra_files,
    scripts=glob('bin/*'),
    **setup_kwargs
)
