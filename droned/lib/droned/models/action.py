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

import sys
import time
import types
import traceback
from twisted.python.failure import Failure
from twisted.internet import reactor, defer
from droned.entity import Entity
from droned.errors import DroneCommandFailed, FormatError
from droned.logging import logWithContext
from kitt.util import getException
from kitt.interfaces import implements, IDroneModelAction, \
        IDroneModelAdminAction
import config


class Action(Entity):
    implements(IDroneModelAction)
    completed = property(lambda self: self.deferred.called)
    succeeded = property(lambda self: self.completed and not \
            isinstance(self.outcome,Failure) )
    failed = property(lambda self: self.completed and not self.succeeded)
    stale = property(lambda self: self.finishedAt and \
            time.time() - self.finishedAt > config.ACTION_EXPIRATION_TIME)
    finishedAt = None
    outcome = None

    def __init__(self, description, deferred):
        self.description = description
        self.deferred = deferred
        self.startedAt = time.time()
        self.context = {}
        deferred.addBoth(self.__finish)

    def __finish(self, outcome):
        self.outcome = outcome
        self.finishedAt = time.time()
        reactor.callLater(config.ACTION_EXPIRATION_TIME, Action.delete, self)
        return outcome


class AdminAction(Entity):
    """Slick interface to invoke exposed methods via blaster protocol

       Requirement: droned.services.drone must be running to access methods
       that are exposed via this interface, this is configurable in DroneD's
       config.py settings.

       Developer Notes:
           how to use this interface ...

           1) instantiate with the name of the "action" you wish to expose
           2) expose methods see AdminAction.expose
           3) build documentation ... call AdminAction.buildDoc

       Examples:
           code:
               foo = AdminAction('bar')
               foo.expose('baz', lambda: 'hello world' (), 'example of AdminAction')
               foo.buildDoc()

           admin:
               #shell: << droneblaster bar ### or ### droneblaster help bar
               #shell: >> 127.0.0.1:5500  -> -4: "Usage: bar <command> [options]
               #shell: >> 
               #shell: >>     foo         example of AdminAction
               #shell: >> "
               #shell: >> Run Time: 0.019 seconds

               INVOCATION
               #shell: << droneblaster bar foo
               #shell: >> 127.0.0.1:5500  -> 0: "hello world"
               #shell: >> Run Time: 0.017 seconds
    """
    implements(IDroneModelAdminAction)
    serializable = False
    def __init__(self, action):
        self.action = action
        self.exposedMethodInfo = []
        self.exposedMethods = {}


    def log(self, message):
        """where to send logging information"""
        logWithContext(type=self.action, route='console')(str(message))


    def buildDoc(self):
        """You might need this, so it is provided. Rebuilds help <action>"""
        self.__doc__ = "Usage: %s <command> [options]\n\n" % (self.action,)
        for name,args,doc in self.exposedMethodInfo:
            argStr = ' '.join(['<'+arg+'>' for arg in args])
            self.__doc__ += "  %s %s\t%s\n" % (name,argStr,doc)


    #FIXME, document this better and clean it up
    def resultContext(self, template, instance=None, **context):
        """Creates a dict containg relevant contextual information about a 
           result.  You can override this method and tailor it to your liking.
           We typically use this to pass verbose structured data to a master
           DroneD controller (not provided with DroneD core) so that it may
           quickly make decisions based on the result of it's previous command
           and control activities.

           IF you set 'error' in the **context this will raise a server error
           at the remote end. This can be good or bad depending on your outlook
           on exceptions.  Consider this your only warning.

           return dict
        """
        if 'application' not in context:
            context['application'] = self.action
        failure = context.pop('error', False)
        if isinstance(failure, Failure):
            if 'description' not in context:
                context['description'] = '[%s] %s: %s' % \
                        (self.action, getException(failure), failure.getErrorMessage())
            if 'code' not in context:
                context['code'] = -2
            context['error'] = True
            context['stacktrace'] = failure.getTraceback()
            self.log('Result context during exception\n%(stacktrace)s' % context)
            return context #failed so bad we need to shortcut out
        else:
            context['error'] = bool(failure)
        if instance: #this was made for AppManager's
            if hasattr(instance, 'version'):
                context['version'] = instance.version
            if hasattr(instance, 'label'):
                context['label'] = instance.label
            if hasattr(instance, 'running'):
                context['running'] = instance.running
        try: #fail-safe in case someone is a bonehead
            context['description'] = template % context
        except:
            failure = Failure()
            context['description'] = '[%s] %s: %s' % \
                    (self.action, getException(failure), failure.getErrorMessage())
            context['stacktrace'] = failure.getTraceback()
            if 'code' not in context:
                context['code'] = -2
        #be nice to blaster api and the remote client
        context.update({'code' : context.get('code',0) })
        return context


    def invoke(self, name, args):
        """Invoke Exposed Methods
           @param name (str) - name of method to invoke
           @param args (tuple) - arguments to pass to invoked method

           @return (defer.Deferred)
        """
        if name not in self.exposedMethods:
            return defer.fail(DroneCommandFailed(self.resultContext(
                "[%(application)s] Unknown method '%(method)s'", method=name, 
                error='unknown method'))
            )
        try:
            #our own form of maybeDeferred
            d = self.exposedMethods[name](*args)
            if isinstance(d, defer.Deferred):
                action = Action(' '.join([str(i) for i in \
                        (self.action, name) + tuple(args)]), d)
                return action.deferred
            elif isinstance(d, DroneCommandFailed):
                return defer.fail(d)
            elif isinstance(d, dict):
                return defer.succeed(d)
            elif isinstance(d, type(None)):
                #this just feels dirty
                return defer.succeed(d)
            elif isinstance(d, Failure):
                d.raiseException() #sigh
            #probably from a triggerred Event callback
            elif type(d) == types.InstanceType:
                return defer.succeed(None)
            return defer.fail(FormatError("Result is not formatted correctly you " + \
                 "must return self.resultContext or DroneCommandFailed." + \
                 "\nResult: <%s>" % (str(d),)))
        except:
            failure = Failure()
            if failure.check(DroneCommandFailed):
                template = "[%(application)s] %(description)s"
                context = failure.value.resultContext
                if not 'description' in context:
                    context['description'] = failure.getErrorMessage()
            else:
                template = "[%(application)s] " + "%s: %s" % (getException(failure),
                        failure.getErrorMessage())
                context = {'error': True, 'code':-2, 'stacktrace': failure.getTraceback()}
            return defer.fail(DroneCommandFailed(self.resultContext(template, 
                None, **context))
            )


    @defer.deferredGenerator
    def __call__(self, argstr):
        args = argstr.split()
        resultContext = None
        if not args: #return command usage
            methods = {}
            for name,args,doc in self.exposedMethodInfo:
                methods[name] = {'args' : args, 'doc' : doc}
            resultContext = dict(description=self.__doc__, methods=methods)
            yield resultContext
        else:
            method = args.pop(0)
            try:
                wfd = defer.waitForDeferred(
                        self.invoke(method,args)
                )
                yield wfd
                resultContext = wfd.getResult()
            except:
                failure = Failure()
                if failure.check(DroneCommandFailed):
                    resultContext = failure.value.resultContext
                else:
                    #be nice and return something to the end user
                    template = "[%(application)s] "
                    template += "%s: %s" % (getException(failure), failure.getErrorMessage())
                    context = {'error': True, 'code': -2, 'stacktrace': failure.getTraceback()}
                    resultContext = self.resultContext(template, None, 
                        **context
                    )
                    
            yield resultContext


    def expose(self, name, method, args, doc):
        """Exposes a method in 'self.action name *args' to the class
           droned.services.drone.DroneServer for remote invocation over
           the blaster protocol

           @param name: (string)
           @param method: (callable)
           @param args: tuple((string), ...) -> named positional arguments
           @param doc: (string) -> administative documentation .. (ie usage)

           @return None
        """
        if name in self.exposedMethods:
            raise AttributeError('method %s is already reserved in %s' % \
                    (name, str(self)))
        self.exposedMethodInfo.append( (name,args,doc) )
        self.exposedMethods[name] = method


    def unexpose(self, name):
        """Removes an exposed method

           @param name: (string)

           @return None
        """
        #check the method dictionary first
        if name in self.exposedMethods:
            del self.exposedMethods[name]
        info = None #locally scoped
        try: #make sure the documentation is up to date
            for info in self.exposedMethodInfo:
                if info[0] != name: continue
                raise StopIteration('Found Method')
        except StopIteration:
            self.exposedMethodInfo.remove(info)


    @staticmethod
    def byName(action):
        for obj in AdminAction.objects:
            if obj.action == action:
                return obj
        return None
