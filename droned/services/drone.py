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

from kitt.interfaces import moduleProvides, IDroneDService
moduleProvides(IDroneDService) #requirement
from kitt.util import dictwrapper

import os
SERVICENAME = 'drone'
#override in romeo
SERVICECONFIG = dictwrapper({
    'DRONED_SERVER_TIMEOUT': int(60 * 60 * 12),
    'DRONED_WEBROOT': os.path.join(os.path.sep, 'var','lib','droned','WEB_ROOT'),
    'DRONED_PORT': 5500,
    'DRONED_PRIME_TTL': 120,
})

from twisted.python.failure import Failure
from twisted.application import internet
from twisted.web import server, static, resource
from twisted.internet import reactor, defer
import config

from kitt.util import unpackify
from kitt.decorators import deferredAsThread
from kitt import blaster
from droned.logging import logWithContext
from droned.entity import Entity
from droned.clients import cancelTask
import time
import gc

#setup some logging contexts
http_log = logWithContext(type='http', route=SERVICENAME)
server_log = logWithContext(type=SERVICENAME)
gremlin_log = logWithContext(type='gremlin', route=SERVICENAME)

DIGEST_INIT = None
try: #newer versions of python
    import hashlib
    DIGEST_INIT = hashlib.sha1
except ImportError: #python2.4?
    import sha
    DIGEST_INIT = sha.new

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import urllib

# module state globals
parentService = None
service = None

server.version = 'DroneD/twisted' 

#get the droneserver model
from droned.models.server import drone


class Gremlin(resource.Resource):
    """stream serialized data out of the server"""
    @deferredAsThread
    def _serialize_objects(self, request):
        buf = StringIO()
        for obj in gc.get_objects():
            if isinstance(obj, Entity) and obj.serializable and \
                    obj.__class__.isValid(obj):
                try:
                    buf.write(obj.serialize())
                except:
                    gremlin_log(Failure().getTraceback())
        result = buf.getvalue()
        buf.close()
        return result

    def render_GET(self, request):
        Type = "application/x-pickle.python"
        def _render(result):
            request.setHeader("Content-Type", Type)
            request.setHeader("Content-Length", str(len(result)))
            request.setHeader("Pragma", "no-cache")
            request.setHeader("Cache-Control", "no-cache")
            request.write(result)
            request.finish()

        d = self._serialize_objects(request)
        d.addCallback(_render)
        d.addErrback(lambda x: gremlin_log(x.getTraceback()) and x or x)
        request.notifyFinish().addErrback(lambda x: cancelTask(d))
        return server.NOT_DONE_YET
        

class Prime(resource.Resource):
    """Handles Prime Number Allocation"""
    def __init__(self):
        resource.Resource.__init__(self)


    def render_GET(self, request):
        def _render(result):
            request.setHeader("Content-Type", "text/plain")
            request.setHeader("Content-Length", str(len(result)))
            request.setHeader("Pragma", "no-cache")
            request.setHeader("Cache-Control", "no-cache")
            request.write(result)
            request.finish()
            #invalidate the prime after a certain period of time
            try:
                reactor.callLater(
                    config.DRONED_PRIME_TTL,
                    drone.releasePrime, 
                    int(result)
                )
            except: pass

        d = drone.getprime()
        d.addCallback(str) #getprime returns an int
        d.addCallback(_render)
        request.notifyFinish().addErrback(lambda x: cancelTask(d))
        return server.NOT_DONE_YET


class Control(resource.Resource):
    """Handle Remote Commands"""
    def __init__(self):
        resource.Resource.__init__(self)


    def msgBufResponse(self, result):
        """Format results, encode, and respond"""
        response, contentType = result
        try:
            return {
                'response' : urllib.quote(blaster.Serialize().execute(
                    contentType, drone.formatResults(response))),
                'type' : contentType,
                'code' : 200
            }
        except:
            failure = Failure()
            Msg = {
                'code' : 1,
                'description' : failure.getErrorMessage(),
                'stacktrace': failure.getTraceback(),
                'error' : True
            }
            return {
                'response' : urllib.quote(blaster.Serialize().execute(
                        contentType, Msg)),
                'type' : 'text/plain',
                'code' : 500
            }


    @defer.deferredGenerator
    def execute(self, request):
        """interface method to special droned actions"""
        result = None
        contentType = 'application/droned-pickle' #set the default
        try:
            request.content.seek(0, 0)

            BufferedMessage = request.content.read()
            contentType = request.getHeader('content-type')
            host = request.getClientIP()

            if not bool(contentType in blaster.MIMESerialize):
                raise AssertionError("Can't support this content encoding")
            _dict = blaster.Deserialize().execute(contentType,
                    urllib.unquote(BufferedMessage))
            digest = DIGEST_INIT()
            keyID = _dict["key"]
            action = _dict["action"]
            argstr = _dict["argstr"]
            magicStr = _dict["magic"]
            magicNumber = abs(unpackify(magicStr))
            timestamp = _dict["time"]
            signature = _dict["signature"]
            if argstr != "":
                payload = str(magicStr) + str(timestamp) + "%s %s" % \
                    (action,argstr)
            else:
                payload = str(magicStr) + str(timestamp) + "%s" % (action,)
            digest.update(payload)
            assumed = digest.hexdigest()
            trusted = drone.keyRing.publicDecrypt(keyID, signature)
            #check the magic string
            d = drone.validateMessage(magicNumber)
            wfd = defer.waitForDeferred(d)
            yield wfd
            if not wfd.getResult():
                raise AssertionError("Invalid Magic String")
            if magicNumber == 0:
                raise AssertionError("Attempted Zero-Attack, dropping request")
            if trusted != assumed:
                raise AssertionError("Invalid signature: %s != %s" % \
                        (assumed, trusted))
            func = drone.get_action(action)
            if not func:
                raise AssertionError("Action %s, Not actionable" % (action,))
            if argstr != "": #no args hack
                server_log('Executing "%s %s" for %s@%s' % (action, argstr, keyID, host))
            else:
                server_log('Executing "%s" for %s@%s' % (action, keyID, host))
            #get the result of the request as a deferred
            d = defer.maybeDeferred(func, argstr)
            #Format the result of the action
            wfd = defer.waitForDeferred(d)
            yield wfd
            result = wfd.getResult()
        except:
            result = Failure()
        yield (result, contentType) 


    def render_POST(self, request):
        def _render(result):
            data = result.get('response', 'ok')
            request.setHeader("content-type", result.get('type','text/plain'))
            request.setHeader("Pragma", "no-cache")
            request.setHeader("Cache-Control", "no-cache")
            request.setHeader("content-length", str( len( data ) ))
            request.setResponseCode(result.get('code', 200))
            request.write( str(data) )
            request.finish()

        d = self.execute(request)
        d.addBoth(self.msgBufResponse)
        d.addCallback(_render)
        request.notifyFinish().addErrback(lambda x: cancelTask(d))
        return server.NOT_DONE_YET


class DroneSite(server.Site):
    """Implements DroneD logging"""
    def log(self, request):
       """Overrode to use DroneD logging and filter some requests"""
       line = '%s - -"%s" %d %s "%s" "%s"' % (
                request.getClientIP(),
                '%s %s %s' % (self._escape(request.method),
                              self._escape(request.uri),
                              self._escape(request.clientproto)),
                request.code,
                request.sentLength or "-",
                self._escape(request.getHeader("referer") or "-"),
                self._escape(request.getHeader("user-agent") or "-"))

       #filter this junk out otherwise the logs are very chatty
       if ('_command' in line) or ('_getprime' in line) or \
                ('favicon.ico' in line) or ('gremlin' in line):
            return

       http_log(line)


###############################################################################
# Service API Requirements
###############################################################################
def install(_parentService):
    global parentService
    global SERVICECONFIG
    for var, val in SERVICECONFIG.wrapped.items():
        setattr(config, var, val)
    parentService = _parentService

def start():
    global service
    if not running():
        kwargs = {'timeout': 60 * 60 * 12, 'logPath': None}
        try: kwargs.update({'timeout': config.DRONED_SERVER_TIMEOUT})
        except: pass
        dr = static.File(config.DRONED_WEBROOT)

        dr.putChild('_getprime', Prime())
        dr.putChild('_command', Control())
        dr.putChild('gremlin', Gremlin())

        site = DroneSite(dr, **kwargs)
        
        service = internet.TCPServer(config.DRONED_PORT, site)
        service.setName(SERVICENAME)
        service.setServiceParent(parentService)

def stop():
    global service
    if running():
        service.disownServiceParent()
        service.stopService()
        service = None

def running():
    global service
    return bool(service) and service.running



__all__ = ['start','stop','install','running']
