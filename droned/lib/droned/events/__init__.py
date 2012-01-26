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
from droned.logging import log


def loadAll():
    my_dir = os.path.dirname(__file__)
    for filename in os.listdir(my_dir):
        if not filename.endswith('.py'): continue
        if filename == '__init__.py': continue
        modname = filename[:-3]
        log('Loading event-handler module %s' % modname)
        __import__(__name__ + '.' + modname)
