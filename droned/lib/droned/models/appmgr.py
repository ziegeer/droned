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

###############################################################################
# Author: Justin Venus <justin.venus at orbitz dot com>
# Date: 20-04-2011
# Inspired By: Chris M. Davis
#
# Purpose:
#   I am tired of constantly re-implementing the service boiler plate code. So
#   I took some of Chris Davis' great ideas and abstracted them away to some
#   really generic mechanisms that could quickly speedup application container
#   developement and provide a mechanism to hide how complicated some
#   applications are to manage in a an orchistrated manor.  Let's face it some
#   of us have more interesting work to do.
#
#   The other benifit was it gave me an opportunity to overhaul some of DroneD.
#   Which really needed some care after almost 3.5 years of bitrot, yet still
#   managing to automate some 1600+ applications!!!!
###############################################################################

#FIXME, how do we unittest this?


###############################################################################
# Import Definitions
###############################################################################
from kitt.util import getException, crashReport
from kitt.interfaces import implements, IDroneModelAppManager, \
        IDroneModelApplicationEvent, IDroneDApplication
from droned.errors import DroneCommandFailed
from kitt.decorators import *
from twisted.python.failure import Failure
from twisted.internet import defer, threads, reactor
from twisted.internet.task import LoopingCall

#standard imports
import os
import sys
import copy
import time
import types
import signal
import traceback

try: all
except NameError:
    from kitt.util import all

from droned.entity import Entity
from droned.logging import logWithContext, log
from droned.models.event import Event
from droned.models.app import App

class InvalidPlugin(Exception): pass

class ApplicationEvent(Entity):
    """The Extents Eventing For AppManagers"""
    implements(IDroneModelApplicationEvent)
    serializable = False
    reactor = property(lambda s: reactor)

    def __del__(self):
        if self.loop.running: self.loop.stop()
        try: Event.delete(self.event)
        except: pass


#TODO document
    def __init__(self, service, name, callback, **kwargs):
        """
           
        """
        #get ready for python3
        if not hasattr(callback, '__call__'):
            raise AssertionError("%s is not callable" % (callback.__name__,))

        event_name = str(service) + '-' + str(name)
        self.event = Event(event_name)
        self.name = name
        self.loop = None
        self.service = service

        #borderline laziness on my part
        self.log = AppManager(service).log

        self.condition = kwargs.get('condition', None)
        self.recurring = float(kwargs.get('recurring', 0))
        self.silent = kwargs.get('silent', False)

        assert not (self.recurring and self.condition), \
            "recurring and condition args are mutually exclusive"

        self.func = callback.__name__
        if not self.silent:
            self.event.subscribe(self.announce)
        #send data only if we have it, keeps compatibility with legacy api
        self.event.subscribe(lambda x: (hasattr(x, 'params') and x.params) \
            and callback(x) or callback())

        #our event loop is controlled by the Service
        if self.recurring > 0.0:
            self.loop = LoopingCall(self.event.fire)
            self.occurred() #automatically start re-occuring events


    def announce(self, *args, **kargs):
        """Anounce the Occurrence of an Event"""
        self.log("%s event occurred calling %s" % (self.name, self.func))
        return True


    def occurred(self):
        """Check for Occurrence or Start Event Loop"""
        if not self.condition and self.loop and not self.loop.running:
            self.loop.start(self.recurring)
        elif self.condition and self.condition():
            self.event.fire()
            return True
        return False
            

#TODO document
    def trigger(self, data=None, delay=0.0):
        """Trigger an event, the return object can be cancelled"""
        kwargs = {}
        if data:
            kwargs['data'] = data
        return self.reactor.callLater(delay, self.event.fire, **kwargs)

#for exposing actions to the outside world
from droned.models.action import AdminAction

###############################################################################
# Public Class Definition
###############################################################################
class AppManager(Entity):
    """This is a generic application container service.  It's sole
       purpose is to provide an abstraction to the application plugin.
       Think of this as an application service container.
    """
    implements(IDroneModelAppManager)
    serializable = True
    #global container lock
    globalLock = defer.DeferredLock()
    running = property(lambda s: hasattr(s, '_task') and s._task.running)
    model = property(lambda s: IDroneDApplication(s)) #late plugin lookup
    action = property(lambda s: AdminAction(s.name))
    invoke = property(lambda s: s.action.invoke)
    resultContext = property(lambda s: s.action.resultContext)
    exposedMethodInfo = property(lambda s: s.action.exposedMethodInfo)
    exposedMethods = property(lambda s: s.action.exposedMethods)
    instances = property(lambda s: App(s.name).localappinstances)
    labels = property(lambda s: ( i.label for i in s.instances ))
    #whether or not the application service should discover apps for us
    discover = property(lambda s: not all([i.running for i in s.instances]))

    def __init__(self, name):
        self.name = name
        #this is for user defined storage
        self.applicationContext = {}
        #allow the models to block methods from registering
        self.blockedMethods = set()
        #create a local lock
        self.busy = defer.DeferredLock()
        #track events
        self.events = {}


    def log(self, message, label=None):
        """route logging messages to the application log and allow for custom 
           labeling to be applied
           @param message: (string)
           @param label: (string) or (None)

           @return None
        """
        info = self.name
        if label: info += ',%(label)s' % locals()
        logWithContext(type=info, route='application')(message)


    def __getstate__(self):
        """used to serialize the application model"""
        return {
            'name': self.name,
            'applicationContext': self.applicationContext
        }


    @staticmethod
    def construct(state):
        """rebuild the model with context

           @param state: (dict)

           return AppManger(state['name'])
        """
        manager = AppManager(state['name'])
        manager.applicationContext = state['applicationContext']
        return manager


    def start(self):
        """This is used by service binding to start"""
        if self.running:
            raise AssertionError('already running')

        #not only is this a safety, but makes sure the model is bound
        #donot ever remove this, otherwise first run won't automatically
        #create appinstances or any other models.
                                 #should be self, but make sure we avoid a race 
        if self.model.service != AppManager(self.name):
            raise InvalidPlugin('Plugin for %s is invalid' % (self.name,))

        self.action.log = self.log #override default logging
        #create default exposed methods, the model can override any of these
        self.expose('add',self.addInstance,('instance',),
                    "Configure the specified instance", BUSYLOCK=True)
        self.expose('remove',self.removeInstance,('instance',),
                    "Unconfigure the specified instance", BUSYLOCK=True)
        self.expose('start',self.startInstance,('instance',),
                    "Start the instance", BUSYLOCK=True, INSTANCED=True)
        self.expose('stop',self.stopInstance,('instance',),
                    "Stop the instance",BUSYLOCK=True,INSTANCED=True)
        self.expose('status',self.statusInstance,('instance',),
                    "Status the instance",INSTANCED=True)
        self.expose('enable',self.enableInstance,('instance',),
                    "Enable the instance",INSTANCED=True)
        self.expose('disable',self.disableInstance,('instance',),
                    "Disable the instance",INSTANCED=True)
        self.expose('debug',self.debug,('bool',),
                    "Turn application container debugging on or off")
        self.expose('labels', lambda: self.resultContext(
                    '\n'.join(sorted(self.labels)), None, 
                    **{'labels': sorted(self.labels)}),(),
                    "lists all application instance labels")

        #build our documentation
        self.rebuildHelpDoc()

        #check conditional events
        self._task = LoopingCall(self.conditionalEvents)
        self._task.start(1.0)


    def conditionalEvents(self):
        """check the status of conditional events"""
        if self.busy.locked: return #skip conditional event processing while busy
        for appevent in self.events.values():
            if not appevent.condition: continue
            appevent.occurred()


    def registerEvent(self, name, callback, **kwargs):
        """Interface to Register Service Events"""
        #the self parameter will help ensure this event is unique to the service
        self.events[name] = ApplicationEvent(self.name, name, callback, **kwargs)


    def triggerEvent(self,name,data=None,delay=0.0):
        """Interface to trigger an out of band service event"""
        assert name in self.events, "No such event '%s'" % (name,)
        return self.events[name].trigger(data, delay)


    def disableEvent(self,name):
        """Interface to disable a previously registered service event"""
        assert name in self.events, "No such event '%s'" % (name,)
        self.events[name].event.disable()


    def enableEvent(self, name):
        """Interface to enable a previously disabled registered service event
        """
        assert name in self.events, "No such event '%s'" % (name,)
        self.events[name].event.enable()


    def stop(self):
        """This is used by service binding to stop"""
        try:
            if not self.running:
                raise AssertionError('not running')
            self._task.stop()
            #clear the event dictionary and delete events
            while self.events:
                name, appevent = self.events.popitem()
                if appevent.loop and appevent.loop.running:
                    appevent.loop.stop()
                ApplicationEvent.delete(appevent)
        except:
            self.debugReport()
        #remove this appmanager's actions
        AdminAction.delete(self.action)

    ###########################################################################
    # This part of the class exposes the Model API to outside world
    ###########################################################################

    @synchronizedDeferred(globalLock)
    def unexpose(self, name, blacklist=True):
        """Removes an exposed method, probably not a good idea to expose"""
        #add method to blocked list
        if blacklist:
            self.blockedMethods.add(name)
        if name in self.exposedMethods:
            del self.exposedMethods[name]
            info = None
            found = False
            for info in self.exposedMethodInfo:
                (n,a,d) = info
                if n == name:
                    found == True
                    break
            if info and found:
                self.exposedMethodInfo.remove(info)


    def rebuildHelpDoc(self):
        """rebuild exposed method documentation"""
        self.action.buildDoc()

    @synchronizedDeferred(globalLock)
    def expose(self, name, method, args, doc, **kwargs):
        """Wraps the models exposed methods for gremlin and make methods
           available via blaster protocol for action invocation.

           expose(self, name, method, methodSignature, description, **kwargs)

             name: (string)         - This is the action parameter to expose
             method: (callable)     - This is the function name to call
             args: (tuple)          - layout for parsing args
             description: (string)  - Help Documentation to expose

             kwargs:
                 INSTANCED: (bool)  - sets the instanceOperator decorator for
                                      administrator's ease of use.
                 BUSYLOCK: (bool)   - sets the synchronizedDeferred decorator
                                      for this AppManager.
                 GLOBALLOCK: (bool) - sets the synchronizedDeferred decorator
                                      for synchronizing all AppManagers.
        """
        if name in self.blockedMethods:
            return #method was blocked by the model, probably
        #allow models to override the defaults and print a warning
        if name in self.exposedMethods:
            self.log('Warning method "%s" is already exposed' % (name,))
            return
        #These decorators must be applied in a specific order of precedence
        requireInstance = kwargs.pop('INSTANCED',False)
        requireBusyLock = kwargs.pop('BUSYLOCK',False)
        requireGlobalLock = kwargs.pop('GLOBALLOCK',False)

        #applying decorators at runtime
        if requireBusyLock or requireGlobalLock or requireInstance:
            #ordering is critical
            if requireInstance:
                 #this bizarre decorator is used b/c we need instance info.
                 method = self.instanceOperation(method)
            if requireBusyLock:
                sync = synchronizedDeferred(self.busy)
                method = sync(method)
            if requireGlobalLock:
                sync = synchronizedDeferred(self.globalLock)
                method = sync(method)

        self.exposedMethodInfo.append( (name,args,doc) )
        self.exposedMethods[name] = method



    ###########################################################################
    # This part of the class is for Generic actions that all apps perform
    ###########################################################################
#FIXME is this really needed?
    def debug(self, var):
        """Enable or Disable application model debugging.  You should extend
           this if you know how to enable application debugging in your custom
           'application model'.

           returns deferred - already called
        """
        #assume blaster which is string based, sent the message
        var = str(var) #for safety
        a = var.lower()
        context = {'code' : 0}
        template = '[%(application)s] Debug '
        try:
            if a == 'true':
                self.model.debug = True
                defer.setDebugging(True)
                template += 'Enabled'
            elif a == 'false':
                self.model.debug = False
                defer.setDebugging(False)
                template += 'Disabled'
            else:
                raise TypeError('input must be a bool, True/False')
        except Exception, exc:
            template += str(exc)
            context['code'] = 1
        return defer.succeed(self.resultContext(template,None,**context))
        

    def addInstance(self, label):
        """Add a new instance of this application

           @param label: (string)

           returns deferred - already called
        """
        thisInst = self.model.addInstance(label)
        template = '[%(application)s,%(label)s] Added Instance'
        return defer.succeed(self.resultContext(template,thisInst)) 


    def removeInstance(self, label):
        """Remove an instance of this application

           @param label: (string)

           returns deferred - already called
        """
        try:
            self.model.delInstance(self, label)
            template = '[%(application)s,'+label+'] Removed Instance'
            return defer.succeed(self.resultContext(template, None)) 
        except:
            failure = Failure()
            template = '[%(application)s,%(label)s] Does Not Exists'
            context = {'error': failure} 
            return defer.fail(DroneCommandFailed(self.resultContext(template, 
                None, **context))
            )


    def enableInstance(self, label):
        """Enable Automatic restart of this application instance

           @param label: (string)

           returns deferred - already called
        """
        thisInst = self.model.getInstance(label)
        thisInst.enabled = True
        template = '%s is enabled.' % thisInst.description
        return defer.succeed(self.resultContext(template,thisInst)) 


    def disableInstance(self, label):
        """Disable Automatic restart of this application instance

           @param label: (string)

           returns deferred - already called
        """
        thisInst = self.model.getInstance(label)
        thisInst.enabled = False
        template = '%s is disabled.' % thisInst.description
        return defer.succeed(self.resultContext(template,thisInst)) 


    @defer.deferredGenerator
    def _start_stop_common(self, label, action):
        result = {}
        try:
            function = getattr(self.model, action)
            d = defer.maybeDeferred(function, label)
            wfd = defer.waitForDeferred(d)
            yield wfd
            result = wfd.getResult()
            #take this time to update the instance
            if isinstance(result, dict):
                thisInst = self.model.getInstance(label)
                thisInst.updateInfo(result) 
        except:
            failure = Failure()
            if failure.check(DroneCommandFailed):
                result = failure.value.resultContext
            else:
                #log the error, allowing for debugging
                self.debugReport()
                #be nice and return something to the end user
                template = "%s: %s" % (getException(failure), failure.getErrorMessage())
                context = {'error':failure,'code':-2}
                result = self.resultContext(template, None, **context)
            #finally wrap the failure into a known type
            result = Failure(DroneCommandFailed(result))
        #AppInstances need a moment to be updated
        d = defer.Deferred()
        reactor.callLater(1.0, d.callback, None)
        wfd = defer.waitForDeferred(d)
        yield wfd
        wfd.getResult()
        yield result
 

    @defer.deferredGenerator
    def startInstance(self, label):
        """Starts an application instance by label

           @param label: (string)

           @fires Event('instance-started')

           return defer.Deferred()
        """
        template = '[%(application)s,%(label)s] %(description)s'
        context = {
            'description': 'Failed to Start',
            'code': 254
        }
        result = {}
        thisInst = None
        try:
            if self.model.getInstance(label).running:
                context.update(self.model.statusInstance(label))
                raise DroneCommandFailed(context)

            d = self._start_stop_common(label, 'startInstance')
            wfd = defer.waitForDeferred(d)
            yield wfd
            result = wfd.getResult()

            d = self.statusInstance(label)
            wfd = defer.waitForDeferred(d)
            yield wfd
            result.update(wfd.getResult())
            #refresh the instance as it can change
            thisInst = self.model.getInstance(label)
            if isinstance(result, dict):
                context.update(result)
            elif isinstance(result, DroneCommandFailed):
                context.update(result.resultContext)
            if thisInst.running:
                Event('instance-started').fire(instance=thisInst)
                context['code'] = 0
                raise AssertionError('ignore')
            raise DroneCommandFailed(context)
        except AssertionError:
            #update the instance model
            wfd = defer.waitForDeferred(self.statusInstance(label))
            yield wfd
            result = wfd.getResult()
        except:
            thisInst = self.model.getInstance(label)
            failure = Failure()
            if failure.check(DroneCommandFailed):
                template = '%(description)s'
                context = failure.value.resultContext
            else:
                #log the error, allowing for debugging
                self.debugReport()
                #be nice and return something to the end user
                temp = "%s: %s" % (getException(failure), failure.getErrorMessage())
                context = {'error': failure, 'code': 253, 'description': temp}
            result = self.resultContext(template, thisInst, **context)
        try:
            thisInst = self.model.getInstance(label)
            thisInst.shouldBeRunning = True
        except: pass
        yield result


    @defer.deferredGenerator
    def stopInstance(self, label):
        """Stops an application instance by label

           @param label: (string)

           @fires Event('instance-stopped')

           return defer.Deferred()
        """
        result = {}
        template = '[%(application)s,%(label)s] %(description)s'
        context = {'code': 254}
        thisInst = None
        try:
            thisInst = self.model.getInstance(label)
            thisInst.shouldBeRunning = False
            if not thisInst.running:
                context.update(self.model.statusInstance(label))
                raise DroneCommandFailed(context)
            pid = thisInst.process.pid 
            self.log("Trying to shutdown %d gracefully" % (pid,))

            def failed(result):
                """attempting to be consistant"""
                self.log("Failed to shutdown process gracefully")
                return result

            def success(result):
                """attempting to be consistant"""
                self.log("process %d gracefully shutdown" % (pid,))
                return result

            d = self._start_stop_common(label, 'stopInstance')
            d.addCallback(success)
            d.addErrback(failed)
            d.addErrback(self._killInstance, thisInst)
            wfd = defer.waitForDeferred(d)
            yield wfd
            #refresh the instance as it can change
            thisInst = self.model.getInstance(label)
            result = wfd.getResult()
            if isinstance(result, dict):
                context.update(result)
            elif isinstance(result, DroneCommandFailed):
                context.update(result.resultContext)
            if not thisInst.running:
                context['code'] = 0
                Event('instance-stopped').fire(instance=thisInst)
                raise AssertionError('ignore me')
            raise DroneCommandFailed(context)
        except AssertionError:
            #update the instance model
            wfd = defer.waitForDeferred(self.statusInstance(label))
            yield wfd
            result = wfd.getResult()
            result['code'] = context['code']
        except:
            failure = Failure()
            if failure.check(DroneCommandFailed):
                context = failure.value.resultContext
                template = '%(description)s'
            else:
                temp = "%s: %s" % (getException(failure), failure.getErrorMessage())
                context = {'error': failure, 'code': 253, 'description': temp}
            result = self.resultContext(template, thisInst, **context)
        try:
            thisInst = self.model.getInstance(label)
            thisInst.shouldBeRunning = False
        except: pass
        yield result


    def statusInstance(self, label):
        """Status an instance of an application

           @param label: (string)

           @return deferred - already called
        """
        result = self.model.statusInstance(label)
        thisInst = self.model.getInstance(label)
        template = '%(description)s'       
        return defer.succeed(self.resultContext(template, thisInst, **result))


    @safe(None)
    def debugReport(self, FromDeferred=False):
        """Friendly Debug Reporting in the Logs

           handles instances of twisted.python.failure.Failure
           
           This method is callback chain safe
        """
        if isinstance(FromDeferred, Failure):
            try: FromDeferred.raiseException()
            except: pass #just need the current exception in sys.exc_info
            crashReport('Service [%s]: Caught unhandled exception' % \
                    (self.name,), self)
        #assume this can be part of a callback chain
        return FromDeferred


    ###########################################################################
    # Per instance decorator method
    ###########################################################################
    def instanceOperation(self, func):
        """Method decorator for Instances of an Application handles dynamic
           methods that have been added to the model and exposed.  This felt
           bizarre when implementing, but it really makes life easy while
           exposing methods.

           @param func: callable()

           return defer.Deferred()
        """
        def decorator(*args, **kwargs):
            knownlabels = sorted(self.labels)
            if not hasattr(func, '__call__'):
                raise AssertionError('%s is not callable' % (func.__name__,))
            if not args:
                #allow not using labels if there is only one label
                if len(knownlabels) == 1:
                    args = (knownlabels[0],)
                else:
                    return self.resultContext(
                        "[%(application)s] No instance specified!", error=True)
            @defer.deferredGenerator
            def handleDeferreds(labels):
                """Remember last yield is the return value, don't use return"""
                results = {}
                descriptions = []
                ret = {}
                code = 0
                for l in labels:
                    try:
                        d = defer.maybeDeferred(func, l, *args[1:], **kwargs)
                        wfd = defer.waitForDeferred(d)
                        yield wfd
                        ret = wfd.getResult()
                    except:
                        failure = Failure()
                        des = "%s: %s" % \
                                (getException(failure),failure.getErrorMessage())
                        if failure.check(DroneCommandFailed):
                            result[l] = failure.value.resultContext
                            if 'description' not in result[l]:
                                result[l]['description'] = des
                            result[l]['stacktrace'] = failure.getTraceback()
                            result[l]['error'] = True
                            if 'code' not in result[l]:
                                result[l]['code'] = 1
                        else:
                            ret = {
                                'description': des,
                                'code': 1,
                                'error': True,
                                'stacktrace': failure.getTraceback()
                            }
                    if not ret: #NoneType detection
                        ret = {'description' : str(ret), 'code' : 0}
                    if 'code' in ret:
                        code += abs(ret['code'])
                    results[l] = ret
                    try:
                        descriptions.append(results[l]['description'])
                    except:
                       self.debugReport()
                results['code'] = code
                try:
                    results['description'] = '\n'.join(descriptions)
                except:
                    results['description'] = None
                if len(labels) == 0:
                    Label = labels[0]
                else:
                    Label = None
                ret = self.resultContext('%(description)s',label=Label,**results) 
                yield ret

            label = args[0]
            if label == 'all' or label == '*':
                return handleDeferreds(knownlabels)

            if label not in knownlabels:
                return self.resultContext(
                        "Unknown %(application)s instance '%(label)s'",
                        label=label,error='unknown instance')
            #singular case
            result = handleDeferreds([label])
            return result
        return decorator


    @defer.deferredGenerator
    def _killInstance(self, result, instanceRef):
        """Last resort to stop your process"""
        bagOfTricks = [
            (lambda: os.kill(instanceRef.process.pid, signal.SIGTERM),'forcefully'),
            (lambda: os.kill(instanceRef.process.pid, signal.SIGKILL),'viciously'),
        ]
        #trap the failure and set a default message
        if isinstance(result, Failure):
            result.trap(Exception)
            result = 'Not Running'

        #give the protocol handler and OS a moment to do their thing
        d = defer.Deferred()
        reactor.callLater(0.2, d.callback, None)
        wfd = defer.waitForDeferred(d)
        yield wfd
        wfd.getResult()
                
        if instanceRef.running:
            pid = instanceRef.process.pid
            #ninja's need tricks too
            for kung, fu in bagOfTricks:
                d = defer.Deferred()
                try:
                    self.log("Trying to shutdown %d %s" % (pid,fu))
                    kung()
                    x = defer.Deferred()
                    #wait for the OS to reap the PID
                    reactor.callLater(5.0, x.callback, None)
                    wfd = defer.waitForDeferred(x)
                    yield wfd
                    wfd.getResult()
                    #check for the pid
                    if instanceRef.running:
                        self.log("Failed to shutdown process %s" % (fu,))
                    else:
                        result = "process %d %s shutdown" % (pid, fu)
                except Exception, exc:
                    self.log("%s while trying to %s shutdown process %d: %s" % \
                          (getException(), fu, pid, exc))

                if not instanceRef.running: break
                reactor.callLater(10, d.callback, None)
                wfd = defer.waitForDeferred(d)
                yield wfd
                wfd.getResult() 

        #true or false, in this case False == 0 and that is good
        code = int(instanceRef.running)
        if code:
            result = "PID %d is still running even though I tried to kill it." \
                    % (instanceRef.process.pid,)
        self.log(result)

        if not isinstance(result, dict):
            #create a response
            template = "%(description)s"
            context = {
                'description': result,
                'code': code,
                'error': not code
            }

            #build a nice result context
            result = self.resultContext(template, instanceRef, **context)
        yield result


#avoid circularities
#from droned.applications import ApplicationPlugin
#export the bare minimum
__all__ = ['AppManager','AdminAction']
