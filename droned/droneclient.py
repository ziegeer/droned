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
import sys
#for some of the shared libs
sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)),'lib'))
try:
  from twisted.internet import epollreactor
  epollreactor.install()
except: pass

from kitt import rsa
default_port = 5500
keyDir = os.environ.get('DRONED_KEY_DIR', '/etc/pki/droned')

from twisted.internet import reactor, defer
from droned.clients.blaster import blast

import time
import getopt

DEBUG = False

class BlasterResult(object):
    """Receives blaster message responses, tracks the total run time and 
       outputs results to the given filedescriptor.  This is the simplest and
       most complete example of how to handle a blaster response.  This
       callable class is effectively a callback chain processor.
    """
    def __init__(self, outfd):
        """Initialized with a filedescriptor.

           outfd: (int) - open filedescriptor
        """
        self.outfd = outfd
        self.returncode = 0


    def started(self):
        """Get the reactor to trigger the time"""
        self.start = time.time()


    def __del__(self):
        """Make sure filedescriptor is closed"""
        if self.outfd:
            try:
                self.outfd.close()
            except: pass


    def write(self, message):
        """Write messages to the provided filedescriptor"""
        try:
            self.outfd.write("%s\n" % message)
        except: pass


    def __call__(self, result):
        """Receives the callback result dictionary and outputs results.

           result: (dict of dict) - top level keys are typically of class 
              'drone.model.server.Server'.  The corresponding value is a
              response dictionary and must contain the following required keys
              ['code','description','server','port'].

           returns dict (result) - output is the same as input
        """
        for var, val in result.items():
            self.write('%(server)s:%(port)s\t-> %(code)d: "%(description)s"' % val)
            if DEBUG and 'stacktrace' in val:
                self.write('Received Stacktrace from %(server)s:\n%(stacktrace)s\n\n' % val)
            self.returncode += abs(val['code']) 

        end = time.time()
        sys.stdout.write("Run Time: %.3f seconds\n" % (end - self.start,))
        #stop the reactor so we can get the return code set
        reactor.stop()
        return result


#########################################
# Old droneblaster code for parsing
#########################################
keyfile = 'local'

def usage(err=None):
  sys.stderr.write("""
        Usage: droneblaster [options] "command"

        Options
                -h host1:port,host2...  Send to the listed hosts
                -f hostFile             Send to the hosts in hostFile
                -o outputFile           Write the results to outputFile
                -k file                 Specify the private key to sign with
                -t seconds              Adjust timeout value (default: 5)
                -p port                 Specify the port (default: 5500)
                -d                      enable debugging output

  """)
  if err: sys.stderr.write(err + '\n\n')
  sys.exit(1)

def parseHosts(data,sep):
  hosts = set()
  for h in data.split(sep):
    h = h.strip()
    if not h: continue
    port = default_port
    if ':' in h: h, port = h.split(':',1)
    hosts.add("%s:%d" % (h,int(port)))
  return list(hosts)

try:
  optList,args = getopt.gnu_getopt(sys.argv[1:],"h:f:t:o:p:k:d")
  opts = dict(optList)
  message = ' '.join(args)
  assert message, "No command specified"
  kwargs = {}
  if '-h' not in opts and '-f' not in opts:
    hosts = ['127.0.0.1']
    keyfile = 'local'
  if '-h' in opts and '-f' in opts: raise Exception, "You cannot specify both -h and -f"

  if '-p' in opts: default_port = int(opts['-p'])
  if '-h' in opts:
    hosts = parseHosts(opts['-h'],',')

  if '-f' in opts:
    data = open(opts['-f'],'r').read()
    hosts = parseHosts(data,'\n')

  if '-o' in opts: sys.stdout = open(opts['-o'],'a')
  if '-t' in opts: kwargs['timeout'] = float(opts['-t'])
  if '-d' in opts:
      kwargs['debug'] = DEBUG = True
      defer.setDebugging(True)
  if '-k' in opts: keyfile = opts['-k']
except Exception, exc:
  usage("Error processing aruments (%s)" % exc)

key = None
for location in (keyfile, os.path.expanduser("~/.dkeys/%s.private" % keyfile), '%s/%s.private' % (keyDir,keyfile)):
  if os.access(location,os.R_OK):
    key = rsa.PrivateKey(location)
    break
if not key:
  sys.stdout.write("Could not find key file! You may not have permission.\n")
  sys.exit(1)

# newer twisted code
sys.stderr = sys.stdout
responseHandler = BlasterResult(sys.stdout)
#inject the callback function as opposed to chaining
kwargs['callback'] = responseHandler
reactor.callWhenRunning(responseHandler.started)
reactor.callWhenRunning(blast, message, hosts, key, **kwargs)
reactor.run()
sys.exit(responseHandler.returncode)
