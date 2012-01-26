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

_f = open(os.path.join(WHEREAMI,'lib','romeo','copyright.py'),'w')
_f.write(copyright_module)
_f.close()

if os.environ.get('USE_SETUPTOOLS'):
    from setuptools import setup
    setup_kwargs = dict(zip_safe=0)

else:
    from distutils.core import setup
    setup_kwargs = dict()

setup(
    name='romeo',
    version=VERSION,
    url='https://github.com/OrbitzWorldwide/droned',
    author='Justin Venus',
    author_email='justin.venus@orbitz.com',
    license='Apache Software License 2.0',
    description='Relational Object Mapping of Environmental Organization',
    packages=[
        'romeo',
        'romeo.rules',
        'romeo.grammars',
        'romeo.directives',
    ],
    package_dir={'': 'lib'},
    scripts=glob('bin/*'),
    **setup_kwargs
)
