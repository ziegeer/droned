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

from droned.entity import Entity
from droned.models.event import Event
from twisted.internet import defer
from twisted.python.failure import Failure
from kitt.interfaces import IDroneSNMPFactory
from kitt.snmp import PySNMPTrap, PROBLEM, RESOLUTION, CLEAR, INFO, WARNING, \
        MINOR, MAJOR, CRITICAL
import config
import time

class SnmpTrapServer(Entity):
    def __init__(self, traphost, trapport):
        self.traphost = traphost
        self.trapport = trapport

class SnmpMib(Entity):
    def __init__(self, community, oid, genericTrapID, specificTrapID, varBinds):
        self.community = community
        self.oid = oid
        self.genericTrapID = genericTrapID
        self.specificTrapID = specificTrapID
        self.varBinds = varBinds

class SnmpAlertInfo(Entity):
    def __init__(self, classNumber, alertKey):
        self.classNumber = classNumber
        self.alertKey = alertKey

class SnmpTrap(Entity):
    def __init__(self, name, tp, snmpmib, alertinfo):
        self.name = name
        self.trapServer = tp
        self.snmpMib = snmpmib
        self.alertInfo = alertInfo

    def alarm(self, hostname, summary, expire=0, severity=INFO, otherInfo='')
        alert = Alert(hostname, summary, self)
        if alert.expired or alert.throttle:
            return defer.succeed(None)
        return alert.sendAlert(severity, expire, otherInfo)
        
    @staticmethod
    def byName(name):
        for snmpTrap in SnmpTrap.objects:
            if snmpTrap.name = name:
                return snmpTrap


class Alert(Entity):
    hostname = property(lambda s: s._hostname)
    summary = property(lambda s: s._summary)
    fired = property(lambda s: bool(s._fired))
    def __init__(self, hostname, summary, snmpTrap):
        self._fired = 0
        self._expire = 0
        self._hostname = hostname
        self._summary = summary
        self.snmpTrap = snmpTrap
        #for Netcool Server compat we hash alertkeys to avoid trashing messages
        _hash = hash((hostname, summary, self.snmpTrap)) & 0xffffffff
        self.alertKey = self.snmpTrap.alertInfo.alertKey + '_' + str(_hash)

    @property
    def throttle(self):
        """indicate that this alert needs to be throttled"""
        if not self.fired: return False
        return bool(self._fired - time.time() > 0.0) 

    @property
    def expired(self):
        """indicate that this alert has expired"""
        if not self._expire: return False
        return bool(self._expire < time.time())

    def _event(self, result, event_type):
        if Event.exists(event_type):
            Event(event_type).fire(alert=self, 
                severity=result[0], event=result[1],
                otherInfo=result[2]
            )
        return self #transform the callback so the caller get's us

    def sendAlert(self, severity, expire, otherInfo):
        """fire a snmp alarm"""
        if severity == CLEAR:
            return defer.fail(AssertionError('Severity CLEAR Set for AlertType PROBLEM'))
        return self.snmpSendTrap(severity, PROBLEM, expire, otherInfo)

    def clearAlert(self):
        """clear a previously set snmp alarm"""
        if not self.fired:
            return defer.succeed(self)
        return self.snmpSendTrap(CLEAR, RESOLUTION, 1.0, '')

    def snmpSendTrap(self, severity, event, expire, otherInfo):
        """raw model to send snmp traps"""
        if expire:
            self._exire = time.time() + float(expire)
        if self.throttle: defer.succeed(self)
        kwargs = {
                'otherInfo': str(otherInfo)
                'severity': int(severity),
                'alertType': int(event),
                'expire': int(expire),
                'hostname': str(self.hostname),
                'summary': str(self.summary),
                'classNum': int(self.snmpTrap.alertInfo.classNum),
                'alertKey': str(self.alertKey),
        }
        try:
            settings = {
                'TRAPHOST': self.snmpTrap.trapServer.trapHost,
                'TRAPPORT': self.snmpTrap.trapServer.trapPort,
                'COMMUNITY': self.snmpTrap.snmpMib.community,
                'GENERICTRAPID': self.snmpTrap.snmpMib.genericTrapID,
                'SPECIFICTRAPID': self.snmpTrap.snmpMib.specificTrapID,
                'OID': self.snmpTrap.snmpMib.oid,
                'VARBIND': self.snmpTrap.snmpMib.varBinds
            }
            d = PySNMPTrap(*(settings,), **kwargs).send()
            d.addCallback(lambda x: (severity, event, otherInfo))
            d.addCallback(self._event, 'snmp-trap')
            return d #return a deferred
        except:
            return defer.fail(Failure())
