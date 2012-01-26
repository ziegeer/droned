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

from romeo.entity import Entity
from romeo.foundation import RomeoKeyValue, Environment
import yaml

BUILTIN_SCHEMA = """
%YAML 1.1
---

###############################################################################
# Provide a basic schema
#
# The schema has a few simple rules to follow.  There are a handful of required
# keys and a couple of optional values that the validation will look at.
#
#    REQUIRED KEYS:
#        ROMEO_NAME: 
#             This is the key identifier for a romeo key/value pair
#             it must be a "STRING" (example: 'foo').
#
#        ROMEO_REQUIRED:
#             Tells the validator to throw a fatal error if the ROMEO_NAME is
#             not found in the object mapping.
#
#        ROMEO_SINGLETON:
#             Tells the validator to throw a fatal error if the ROMEO_NAME
#             appears more that "ONE" time per Environment (yaml file).
#
#        ROMEO_TYPE:
#             Tells the validator what the expected 'type' of the value is and
#             raises TypeErrors if an unexpected Type is encountered.  The 
#             object value "null" is accepted reguardless of Type specification.
#             Valid yaml types accepted by the validator are as follows.
#             ( [], {}, '', yes, 0, 0.0, or null )
#
#
#    OPTIONAL KEYS:
#        ROMEO_REQUIRED_KEYS:
#              Applies to ROMEO_TYPE == {}, this tells the validator that a set
#              of keys are requried.  Each key in this list must have a SCHEMA
#              entry and the key must be a ROMEO_NAME identifier.  Validation
#              will fail if the key is missing from the object representation.
# 
#        ROMEO_VALUES:
#              Applies to ROMEO_TYPE == [], this tells the validator that a set
#              of dictionaries is expected that matches a SCHEMA.  The 
#              dictionary must be a SCHEMA definition.
#
# Example uses of each key type are provided in the builtin schema that follows
# below this comment block.
###############################################################################

- ROMEO: &name
    ROMEO_NAME: name
    ROMEO_REQUIRED: yes
    ROMEO_SINGLETON: yes
    ROMEO_TYPE: ''

- ROMEO: &shortname
    ROMEO_NAME: shortname
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: ''

- ROMEO: &fullname
    ROMEO_NAME: fullname
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: ''

- ROMEO: &instances
    ROMEO_NAME: instances
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: 0

- ROMEO: &startup_info
    ROMEO_NAME: startup_info
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: {}
    ROMEO_REQUIRED_KEYS:
        - START_ARGS
        - START_CMD
        - START_ENV

- ROMEO: &shutdown_info
    ROMEO_NAME: shutdown_info
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: {}
    ROMEO_REQUIRED_KEYS:
        - STOP_ARGS
        - STOP_CMD
        - STOP_ENV

- ROMEO: &server
    ROMEO_NAME: server
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: {}
    ROMEO_REQUIRED_KEYS:
        - hostname
        - artifacts

- ROMEO: &hostname
    ROMEO_NAME: hostname
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: ''

- ROMEO: &artifact
    ROMEO_NAME: artifact
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: {}
    ROMEO_REQUIRED_KEYS: 
        - shortname
        - fullname
        - instances
        - startup_info
        - shutdown_info

- ROMEO: &artifacts
    ROMEO_NAME: artifacts
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: []
    ROMEO_VALUES: *artifact

- ROMEO: &START_ENV
    ROMEO_NAME: START_ENV
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: {}

- ROMEO: &STOP_ENV
    ROMEO_NAME: STOP_ENV
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: {}

- ROMEO: &START_ARGS
    ROMEO_NAME: START_ARGS
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: []

- ROMEO: &STOP_ARGS
    ROMEO_NAME: STOP_ARGS
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: []

- ROMEO: &START_CMD
    ROMEO_NAME: START_CMD
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: ''

- ROMEO: &STOP_CMD
    ROMEO_NAME: STOP_CMD
    ROMEO_REQUIRED: no
    ROMEO_SINGLETON: no
    ROMEO_TYPE: ''
"""


class InvalidNode(Exception): pass
class InvalidPolicy(Exception): pass

###############################################################################
# <old_python support=True>
try:
    all
except NameError:
    def all(iterable):
        for element in iterable:
            if not element:
                return False
        return True

try:
    any
except NameError:
    def any(iterable):
        for element in iterable:
            if element:
                return True
        return False
# </old_python>
###############################################################################

class _NodeValidator(Entity):
    def __init__(self, name):
        self.name = name
        self.policy = {}

    def addPolicy(self, policy):
        self.policy.update(policy)
        #setup type validation
        self.policy['ROMEO_TYPE'] = type(self.policy.get('ROMEO_TYPE'))

    def validate(self, obj):
        """Given a RomeoKeyValue object Validate it against the schema"""
        #test if the type is ok, NoneType is automatically acceptable
        if not isinstance(obj.VALUE, self.policy['ROMEO_TYPE']) and not \
                    isinstance(obj.VALUE, type(None)):
            raise TypeError('%s attribute VALUE does not match schema' % \
                    str(obj))
        check_keys = set(self.policy.get('ROMEO_REQUIRED_KEYS',[]))
        if check_keys:
            #filter the child keys against the expected keys
            keys = check_keys & set([ child.KEY for child in obj.CHILDREN ])
            #make sure the related child keys are present
            if not all([ i in check_keys for i in keys ]):
                raise InvalidNode('%s is missing a required related key' % \
                    str(obj))

        #check that if this singleton key shows up more than once in this env
        if self.policy['ROMEO_SINGLETON']:
            #remember objects can show up in multiple environements defs
            envs = [ related for related in obj.RELATED if \
                    isinstance(related, Environment) ]

            #test to make sure this is a singleton in every environment
            if not all([ len(list(env.searchInstance(self.name))) == 1 for env \
                    in envs ]):
                e = '%s singleton showed up multiple times per Environment' % \
                        (self.name,)
                raise InvalidNode(e)
        #determine if we need to check values
        if self.policy.get('ROMEO_VALUES', False):
            if isinstance(self.policy['ROMEO_VALUES'], dict):
                self._check_dict(obj)
        
    def _check_dict(self, obj, testdict=None):
        if not testdict:
            testdict = self.policy.get('ROMEO_VALUES', {})
        assert isinstance(testdict, dict)
        Type = type(testdict.get('ROMEO_TYPE', None))
        key = testdict.get('ROMEO_NAME', False)
        if not key:
            raise InvalidPolicy('Values must inherit from the schema')
        if not _NodeValidator.exists(key):
            raise InvalidNode('%s invalid schema key %s' % (obj, key))
        try: #thow assertion error when a match is found to stop iteration
            for o in obj.RELATED:
                if o.KEY == key and isinstance(o.VALUE, Type):
                    raise AssertionError('Valid, breaking out')
                for x in o.RELATED:
                    if x.KEY == key and isinstance(x.VALUE, Type):
                        raise AssertionError('Valid, breaking out')
            e = '%s unable to validate relationship %s' % (obj, key)
            raise InvalidNode(e)
        except AssertionError: pass #yay we validated a complex schema!!!


class _Schema(Entity):
    schema = property(lambda s: s._schema)
    required = property(lambda s: s.schema['REQUIRED'])
    optional = property(lambda s: s.schema['OPTIONAL'])
    def __init__(self):
        #romeo schema is inflexible and hardcoded
        self._schema = {
            'REQUIRED': {
                'ROMEO_NAME': str,
                'ROMEO_REQUIRED': bool,
                'ROMEO_SINGLETON': bool,
                'ROMEO_TYPE': [list,dict,str,bool,int,float,type(None)],
            },
            'OPTIONAL': {
                'ROMEO_REQUIRED_KEYS': list,
                'ROMEO_VALUES': dict,
            }
        }

    def loadSchema(self, text=None):
        """Load the given schema and perform basic validation of sanity"""
        if not text:
            text = BUILTIN_SCHEMA
        for dictionary in yaml.load(text):
            for var, val in dictionary.iteritems():
                if not isinstance(val, dict): continue
                if var == 'ROMEO':
                    name = val.get('ROMEO_NAME')
                    node = _NodeValidator(name)
                    node.addPolicy(val)

        #check the policies for sanity
        for obj in _NodeValidator.objects:
            policy = obj.policy.keys()
            if not all(( i in policy for i in self.required.keys() )):
                e = '%s does not adhere to the schema requirements' % \
                        (obj.name,)
                raise InvalidPolicy(e)
            if not obj.policy['ROMEO_TYPE'] in self.required['ROMEO_TYPE']:
                raise TypeError('%s type not exected in schema' % (obj.name,))

    def validate(self):
        """Validate RomeoKeyValue objects against the schema"""
        for obj in RomeoKeyValue.objects:
            if not _NodeValidator.exists(obj.KEY): continue
            _NodeValidator(obj.KEY).validate(obj)

_schema = _Schema()

#public methods bound to private object
validate = _schema.validate
load = _schema.loadSchema
get_schema = lambda: _schema.schema

__all__ = ['validate', 'load', 'get_schema', 'InvalidNode', 'InvalidPolicy']
