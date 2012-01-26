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

DIGEST_INIT = None
try: #newer interpretors
    import hashlib
    DIGEST_INIT = hashlib.sha1
except ImportError:
    import sha #python2.4
    DIGEST_INIT = sha.new
assert DIGEST_INIT is not None, "No Library Available to Handle SHA1"

try:
    import simplejson as json
except ImportError:
    try: import json
    except: json = None


_MIMESerialize = {
    'application/droned-pickle' : 'pickle'
}
#if json is supported add it to the serializable mime dict
if json: 
    _MIMESerialize['application/droned-json'] = 'json'

#export what we support
MIMESerialize = _MIMESerialize

try:
    import cPickle as pickle
except ImportError:
    import pickle

import struct

def packify(n):
    s = ''
    while True:
        i = n & 255
        n >>= 8
        s += struct.pack("!B",i)
        if not n: return s


###############################################################################
# Start Serialize/Deserialize helpers
###############################################################################
class _serial(object):
    mimes = MIMESerialize
    def __init__(self):
        if self.__class__ is _serial:
            raise Exception("You may not instantiate this class!!!")


    @staticmethod
    def supported():
        """return supported mimes"""
        return _serial.mimes.keys()


    def execute(self, mimetype, data):
        function =  getattr(self, self.mimes[mimetype]+'_function')
        return function(data)


class Serialize(_serial):
    """Base Serialize Class"""
    def execute(self, mimetype, data):
        assert type(data) is dict, "input must be a dictionary"
        return _serial.execute(self, mimetype, data)


    def json_function(self, Dict):
        return json.dumps( Dict )


    def pickle_function(self, Dict):
        return pickle.dumps( Dict )


class Deserialize(_serial):
    """Base Deserialize Class"""
    def execute(self, mimetype, data):
        assert type(data) is str, "input must be a string"
        return _serial.execute(self, mimetype, data)


    def json_function(self, String):
        return json.loads(String)


    def pickle_function(self, String):
        return pickle.loads(String)


__all__ = ['Deserialize', 'Serialize', 'packify', 'MIMESerialize', 'DIGEST_INIT']
