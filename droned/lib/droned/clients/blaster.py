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

from twisted.internet import defer
from twisted.python.failure import Failure
from twisted.web.client import getPage
from twisted.internet.error import ConnectError, DNSLookupError
from droned.errors import DroneCommandFailed

from kitt.blaster import Serialize, DIGEST_INIT, packify, Deserialize
import time, urllib, traceback

DEFAULT_TIMEOUT = 120.0

__author__ = 'Justin Venus <justin.venus@orbitz.com>'

#public method
def blast(command, clientList, keyObj, **kwargs):
    """Public Method to send messages to a DroneD Client.

       command:    String
       clientList: List
       keyName:    String
       timeout:    number
       callback:   function(dict)

       returns deferred

         This function will send a blaster protocol command to all servers
         and execute all callback function that accepts one parameter. The
         one callback parameter is a dictionary response to the supplied
         command action.
    """

    Debug = kwargs.pop('debug', False)

    #create the callable class
    blaster = DroneBlaster(clientList, debug=Debug)

    callback = kwargs.pop('callback',None)
    if 'timeout' not in kwargs:
        kwargs['timeout'] = DEFAULT_TIMEOUT

    #call our magic messaging class
    d = blaster(command, keyObj, **kwargs)

    #so help me, i hate sanitizing every little thing
    if callback and hasattr(callback, '__call__'):
        d.addCallback(callback)
    return d

#we don't want to use models in clients b/c droneblaster would have to
#evaluate romeo config unnecessarily.
class _Server(object):
    hostname = property(lambda s: s.data['hostname'])
    port = property(lambda s: int(s.data.get('port', 5500)))
    prime = property(lambda s: 'http://%s:%d/_getprime' % (s.hostname,s.port))
    command = property(lambda s: 'http://%s:%d/_command' % (s.hostname,s.port))
    def __init__(self, host):
        self.data = dict(zip(['hostname','port'], host.split(':')))
        self.currentFailure = None
        self.connectFailure = None


class DroneBlaster(object):
    """This class hides the complexity of sending a blaster message
       to many clients simultaneously.  This is a callable Class.
    """
    def __init__(self, serverList, debug=False):
        self.debug = debug
        self.servers = list(map(_Server, serverList))


    def startSession(self):
        """Starts our blaster session by collecting primes"""
        template = """http://%(hostname)s:%(port)d/_getprime"""

        #callable deferred session mananger
        session = GroupSession(self.servers, debug=self.debug)
        session.addBoth(session)

        #allowing up to 5.0 seconds for the prime
        kwargs = {
            'timeout' : 5.0,
            'method' : 'GET'
        }

        events = []
        for server in self.servers:
            d = self.httpCall(server.prime, **kwargs)
            d.addCallback(session.mergeKey, server)
            d.addErrback(session.failedClient, server)
            events.append(d)

        #nom nom nom
        d = defer.DeferredList(events, consumeErrors=False)
        d.chainDeferred(session) #this is the magic sauce
        return session
 

    def finishSession(self, servers, payload, **kwargs):
        """finishes up by sending the payload to healthy clients and then
           we collect and retrieve the results
        """
        template = """http://%(hostname)s:%(port)d/_command"""

        #callable deferred session mananger
        session = GroupSession(servers, debug=self.debug)
        session.addBoth(lambda x: session(x, valueCheck=False))

        #sets the server specific settings here
        kwargs.update(
            {
                'method' : 'POST',
                'postdata' : payload,
                'headers' : {
                    'Content-type': session.MIME,
                },
            }
        )

        events = []
        for server in servers:
            d = self.httpCall(server.command, **kwargs)
            d.addCallback(session.collectResults, server)
            d.addErrback(session.failedClient, server)
            events.append(d)

        #nom nom nom
        d = defer.DeferredList(events, consumeErrors=False)
        d.chainDeferred(session) #this is the magic sauce
        return session


    @staticmethod
    def httpCall(*args, **kwargs):
        """Download a web page as a string.

           Download a page. Return a deferred, which will callback with a
           page (as a string) or errback with a description of the error.

           See twisted.web.client.HTTPClientFactory to see what extra args
           can be passed.
        """
        url = args[0] #first arg is the url
        contextFactory = kwargs.pop('contextFactory', None)
        return getPage(url, contextFactory, *args[1:], **kwargs)


    #inlineCallback is only available on python2.5+
    @defer.deferredGenerator
    def __call__(self, command, key, **proto_kwargs):
        """Implements the blaster client protocol.

           command:    String
           keyName:    String
           timeout:    number

           returns deferred

           This function will send a blaster protocol command to all servers
           and execute all callback function that accepts one parameter. The
           one callback parameter is a dictionary response to the supplied
           command action.
        """
        message = None
        result = None
        resultContext = {}
        #get the prime numbers
        try:
            wfd = defer.waitForDeferred(self.startSession())
            yield wfd
            result = wfd.getResult()
        except Exception, exc:
            if isinstance(exc, DroneCommandFailed):
                resultContext.update(exc.resultContext)
            else:
                traceback.print_exc()

        if isinstance(result, dict) and 'object' in result:
            #create the message payload
            message = result['object'].groupMessage(command, key)
            #track the clients that aren't working
            resultContext.update(result['failedClients'])

            #out of the clients that we can contact, send the command payload
            wfd = defer.waitForDeferred(self.finishSession(
                    result['readyClients'].keys(), message, **proto_kwargs)
            )
            yield wfd
            #reset result for the next test
            result = None
            try:
                result = wfd.getResult()
            except Exception, exc:
                if isinstance(exc, DroneCommandFailed):
                    resultContext.update(exc.resultContext)
                else:
                    traceback.print_exc()

        if isinstance(result, dict) and 'object' in result:
            resultContext.update(result['failedClients'])
            resultContext.update(result['readyClients'])

        yield resultContext


class GroupSession(defer.Deferred):
    """This class implements blaster group message coordination for
       both prime initialization and message response aggregation.
    """
    MIME='application/droned-pickle'

    def __init__(self, servers, debug=False):
        numClients = len(servers)
        assert numClients > 0
        #all the twisted goodies
        defer.Deferred.__init__(self)
        self.debug = debug
        self.value = 1
        self.remaining = numClients
        self.servers = dict()
        self.failed = dict()


    def mergeKey(self, p, server):
        """Merge all keys into one group key"""
        p = int(p) #convert string to int, or throw a type error
        assert type(p) is int and p > 2, "Invalid key" #FIXME for python3
        self.value *= p
        self.remaining -= 1
        self.servers.update({server : None})
        return self.value


    def failedClient(self, failure, server):
        """Track Failed Clients"""
        #turn this failure upside down and make it a success!!
        result = { server : {
                'server' : server.hostname,
                'port' : server.port,
                'description' : str(failure.getErrorMessage()),
                'stacktrace' : failure.getTraceback(),
                'error' : True,
                'code' : -1,
            }
        }

        #update the server and droned models
        server.currentFailure = failure
        if failure.check(ConnectError, DNSLookupError, defer.TimeoutError):
            server.connectFailure = failure

        self.failed.update(result)
        #i don't care why it failed, just stop it from propogating!!!
        failure.trap(Exception)

        self.remaining -= 1
        return result


    def collectResults(self, result, server):
        """collect the results from client messages"""
        data = { server : {
                'server' : server.hostname,
                'port' : server.port,
                'error' : False,
                'description' : str(None),
                'code' : 0
            }
        }

        proto = Deserialize()
        data[server].update(**proto.execute(self.MIME, urllib.unquote(result)))
        self.servers.update(data)

        self.remaining -= 1
        return data


    def groupMessage(self, command, signatureKey):
        """Given a command string and signature create a signed payload"""
        digest = DIGEST_INIT()
        keyID = signatureKey.id

        magicStr = packify(self.value)
        timestamp = int(time.time())
        payload = str(magicStr) + str(timestamp) + str(command)

        digest.update(payload)
        signature = signatureKey.encrypt(digest.hexdigest())

        if '.' in signatureKey.id:
            keyID = signatureKey.id.split('.',1)[0]

        args = command.split()
        action = args.pop(0)
        argstr = ""

        if args:
            argstr = " ".join(args)

        #group payload
        msgDict = {
            'action' : action,
            'argstr' : argstr,
            'magic' : magicStr,
            'time' : timestamp,
            'key' : keyID,
            'signature' : signature,
        }

        proto = Serialize()
        return urllib.quote(proto.execute(self.MIME, msgDict))


    def __call__(self, result, valueCheck=True):
        """our callbacks have been triggered!!!"""
        if self.remaining != 0:
            raise AssertionError("Found a Terrible Bug")
        if self.value == 1 and valueCheck:
            response = {}
            for category in [self.failed, self.servers]:
                for server, info in category.items():
                    context = {
                        'description' : 'Client Completely Failed Task',
                        'error' : True,
                        'code' : -4,
                        'server' : server.hostname,
                        'port' : server.port,
                    }
                    if isinstance(info, dict):
                        context.update(**info)
                    response.update({server: context})
            return Failure(DroneCommandFailed(response))
        else:
            #hand back a useful set of data to the callbacks
            data = {
                'object' : self,
                'failedClients' : self.failed,
                'readyClients' : self.servers
            }
            return data



#publicly available methods
__all__ = ['blast','DroneBlaster']
