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

import romeo #avoid import circularites, reference everything from the top object

@romeo.grammars.query(pattern="^select (?P<parameter>.+)", form="select <key>",
help="returns a list of objects with the given key")
def select_parameter(parameter):
    for obj in romeo.foundation.RomeoKeyValue.search(parameter):
        yield obj

@romeo.grammars.query(pattern="^select (?P<key>.+) where (?P<key2>.+) is (?P<value>.+)",
form="select key1 where key2 is value",
help="look for the object where a known key value pair exists")
def compound_select(key, key2, value):
    if romeo.foundation.RomeoKeyValue.exists(key2, value):
        test = romeo.foundation.RomeoKeyValue(key2, value)
        for obj in romeo.foundation.RomeoKeyValue.objects:
            if obj.KEY != key: continue
            if not test.isRelated(obj): continue
            yield obj

@romeo.grammars.query(pattern="^my (?P<parameter>.+)", form="my <key>",
help="return object matching the parameter belonging to %s" % (romeo.MYHOSTNAME,))
def my_parameter(parameter):
    me = romeo.whoami()
    if me:
        for child in me.CHILDREN:
            if child.KEY != parameter: continue
            yield child
