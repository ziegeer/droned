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

import os, re
from types import FunctionType
from droned.logging import log, err
from droned.errors import ServiceNotAvailable
import config
import services

try: #handle abstaction to service config
    jabber_service = services.getService('jabber')
    jabber_config = jabber_service.SERVICECONFIG
except ServiceNotAvailable:
    jabber_service = None
    jabber_config = None

#holds the responders
responders = {}

def loadAll():
    """loads all of the responders"""
    responders.clear()
    my_dir = os.path.dirname(__file__)
    for filename in os.listdir(my_dir):
        if not filename.endswith('.py'): continue
        if filename == '__init__.py': continue
        modname = filename[:-3]
        log('Loading responder module %s' % modname)
        try:
            #python2.4 __import__ implementation doesn't accept **kwargs
            mod = __import__(__name__ + '.' + modname, {}, {}, [modname])
        except:
            err('skipping responder module %s due to errors' % modname)
            continue
        for name,obj in vars(mod).items():
            if getattr(obj, 'is_responder', False) and hasattr(obj, 'pattern'):
                try:
                    responders[ re.compile(obj.pattern) ] = obj
                    obj.module = modname
                except:
                    err("Failed to compile pattern \"%s\" for %s" % (obj.pattern, obj))
                    raise


def responder(**attrs):
    """Decorator for defining responder functions"""
    if not 'pattern' in attrs:
        raise AssertionError("Responders must have a 'pattern' attribute")
    defaults = {
        'is_responder' : True,
        'form' : "<unknown form>",
        'help' : '???',
        'context_key' : None,
#NOTE default policy is that all responders require authorization 
        'auth_required' : True,
    }

    def apply_attrs(func):
        defaults.update(func.__dict__)
        func.__dict__.update(defaults)
        func.__dict__.update(attrs)
        func.__doc__ = "``%(form)s``  --  %(help)s" % func.__dict__
        return func

    return apply_attrs


def dispatch(conversation, message):
    """dispatches the conversation"""
    required_context_keys = set()

    for regex,func in responders.items():
        match = regex.search(message)
        if not match: continue
        if func.context_key and func.context_key not in conversation.context:
            required_context_keys.add(func.context_key)
            continue
        # Access control implementation
        if func.auth_required and not conversation.authorized:
            err = "You are not authorized to run that command, please ask "
            err += "your environment administrator "
            err += "(%s) " % jabber_config.DEPUTY
            err += "for authorization. If you would like me to ask them to "
            err += "grant you authorization, say "
            err += "<b>auth request</b>"
            conversation.say(err)
            return

        try:
            return func(conversation, **match.groupdict())
        except AlreadyAskingQuestion:
            conversation.say(
                "I need to ask you a question but I have already asked you one. " \
                "Please answer it first. I can always <b>repeat</b> it for you. " \
                "You can also tell me to <b>nevermind</b> that question."
            )
            return

    # This is kind of hacky and feels out of place...
    # but it prevents a lot of duplicated code.
    if required_context_keys:
        if 'subject' in required_context_keys:
            required_context_keys.remove('subject')
            required_context_keys |= set(['app','server'])
        keys = ' or '.join('<b>%s</b>' % k for k in required_context_keys)
        conversation.say("Please tell me what %s you're talking about." % keys)
        return

    raise NoMatch()


class NoMatch(Exception): pass


# Avoid import circularities
from droned.models.conversation import AlreadyAskingQuestion

__all__ = [
    'dispatch',
    'loadAll',
    'responder',
    'responders',
    'jabber_service',
    'jabber_config',
    'NoMatch'
]
