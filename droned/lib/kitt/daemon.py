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
import pwd

def owndir(USER, DIR):
    """behaves like chown -R $PATHSOMEWHERE and mkdir -p """
    uid,gid = pwd.getpwnam(USER)[2:4]
    try:
        if not os.path.exists(DIR):
            os.makedirs(DIR, mode=0755)
        os.chown(DIR, uid, gid)
        for r, d, f in os.walk(DIR):
            for dir in d:
                try: os.chown(os.path.join(r, dir), uid, gid)
                except: pass
            for file in f:
                try: os.chown(os.path.join(r, file), uid, gid)
                except: pass
    except: pass
