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
from droned.entity import Entity
from kitt.decorators import deferredAsThread

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

class GremlinClient(object):
    template = property(lambda s: \
            "http://%(hostname)s:%(port)d/gremlin" % vars(s))
    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = int(port)

    @deferredAsThread
    def _deserialize(self, fd):
        while True:
            try:
                obj = Entity.deserialize(fd)
            except EOFError:
                fd.close()
                break
            except AttributeError:
                fd.close()
                break

    @defer.deferredGenerator
    def __call__(self, extra='', timeout=5.0):
        result = None
        try:
            url = self.template + str(extra)
            d = self.httpCall(url, method='GET', timeout=timeout)
            d.addCallback(StringIO)
            wfd = defer.waitForDeferred(d)
            yield wfd
            d = self._deserialize(wfd.getResult())
            wfd = defer.waitForDeferred(d)
            yield wfd
            result = wfd.getResult() 
        except:
            result = Failure()
        yield result

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
