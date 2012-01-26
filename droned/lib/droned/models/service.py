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

#DEPRECATED - this file needs to be removed


class ServiceDependencyInfo(object):
  "Encapsulates dependency relationships between AppVersion installInfos and ServiceInfos"
  defined = property( lambda self: bool(self.applicableServers) )

  def __init__(self, appversion):
    self.appversion = appversion
    self.applicableServers = set()
    self.provided = set()
    self.required = set()
    self.conflicts = {}

  def __getstate__(self):
    return {
      'applicableServers' : [s.hostname for s in self.applicableServers],
      'provided' : self.provided,
      'required' : self.required,
    }

  def __setstate__(self, state):
    self.applicableServers = set( Server(hostname) for hostname in state['applicableServers'] )
    self.provided = state['provided']
    self.required = state['required']

  def update(self, server, installInfo): #ignoring conflicting info for now...
    if 'requires' in installInfo and 'provides' in installInfo:
      self.required |= set( ServiceInfo(rawInfo) for rawInfo in installInfo['requires'] )
      self.provided |= set( ServiceInfo(rawInfo) for rawInfo in installInfo['provides'] )
      self.applicableServers.add(server)
    elif not installInfo.get('springWired'):
      self.applicableServers.add(server)

  def dependsOn(self, other):
    for requiredService in self.required:
      for providedService in other.provided:
        if requiredService == providedService:
          return True
    return False


class ServiceInfo:
  def __init__(self,rawInfo):
    if len(rawInfo) == 4:
      self.hostCode = rawInfo.pop(1)
    else:
      self.hostCode = None
    self.lookupServers = LookupServerSet(rawInfo[0])
    self.name = rawInfo[1]
    self.version = ServiceVersion(rawInfo[2])

  def __hash__(self):
    return (int((hash(self.lookupServers) +
            hash(self.name) +
            hash(self.version)) % sys.maxint))

  def __eq__(self,other):
    return (type(self) == type(other) and
            self.lookupServers == other.lookupServers and
#           (None in (self.hostCode,other.hostCode) or self.hostCode == other.hostCode) and 
            self.name == other.name and
            self.version == other.version)

  def __str__(self):
    return 'ServiceInfo(%s-%s[%s] on %s)' % (self.name,self.version,self.hostCode,self.lookupServers)
  __repr__ = __str__


class LookupServerSet(frozenset):
  def __init__(self,urls):
    self.urls = map(self.__normalize,urls)
    frozenset.__init__(self,self.urls)

  def __normalize(self,url):
    return url.lower().strip().rstrip('/')

  def __eq__(self,other):
    return bool(self & other)

  def __str__(self):
    return ','.join(self)
  __repr__ = __str__


class ServiceVersion:
  def __init__(self,version):
    self.version = tuple(version)
    self.major = version[0]
    self.minor = version[1]
    self.patch = version[2]

  def __hash__(self):
    return hash(self.version)

  def __eq__(self,other):
    return self.major == other.major

  def __str__(self):
    return '%d.%d.%d' % self.version
  __repr__ = __str__


# Avoid import circularities
from droned.models.server import Server
