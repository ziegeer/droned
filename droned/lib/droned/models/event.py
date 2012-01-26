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
import traceback
from twisted.internet.defer import Deferred
from twisted.python.failure import Failure
from droned.entity import Entity
from droned.logging import logWithContext, err
import config

log = logWithContext(type='events')


class Event(Entity):
  enabled = True

  def __init__(self, name):
    self.name = name
    self.subscribers = set()

  def fire(self, **params):
    if not self.enabled: return
    occurrence = Occurrence(self, **params)
    if config.DEBUG_EVENTS:
      params = ', '.join("%s=%s" % i for i in params.items())
      log('%s.fire(%s)' % (self, params))
    for obj in list(self.subscribers):
      try:
        if isinstance(obj, Deferred):
          if not obj.called:
            obj.callback(occurrence)
          self.subscribers.remove(obj)
        else:
          obj(occurrence)
      except:
        log('%s.fire() subscriber %s raised an exception' % (self, obj), error=True, failure=Failure())
        err()

  def enable(self):
    self.enabled = True

  def disable(self):
    self.enabled = False

  def subscribe(self, obj):
    self.subscribers.add(obj)
    return obj

  def unsubscribe(self, obj):
    self.subscribers.discard(obj)


class Occurrence(object):
  def __init__(self, event, **params):
    self.__dict__.update(params)
    self.event = event
    self.name = event.name
    self.params = params


#Pre-create known events
known_events = (
  'jabber-online',
  'jabber-offline',
  'journal-error',
  'server-broken',
  'server-fixed',
  'installation-found',
  'installation-lost',
  'app-anomaly-found',
  'app-anomaly-lost',
  'app-servers-change',
  'instance-found',
  'instance-lost',
  'instance-started',
  'instance-stopped',
  'instance-crashed',
  'instance-enabled',
  'instance-disabled',
  'service-started',
  'service-stopped',
  'scab-found',
  'scab-lost',
  'new-major-release',
  'new-release-version',
  'release-change',
)
map(Event, known_events)
