from twisted.python import components
from kitt.interfaces import implements
from kitt.decorators import deferredAsThread
from kitt.interfaces.snmptrap import IDroneSNMPTrap, IDroneSNMP
from socket import gethostbyname

class PySNMP(object):
    """I am a configuration object that other objects may use.
       I implement L{IDroneSNMP}.
    """
    implements(IDroneSNMP)
    SNMP_VERSION = None
    #static settings, defaults provided
    hostip = property(lambda s: gethostbyname((s.settings('HOSTIP', s.hostname)))
    trapHost = property(lambda s: s.settings('TRAPHOST','localhost'))
    trapPort = property(lambda s: int(s.settings.get('TRAPPORT',162)))
    community = property(lambda s: s.settings.get('COMMUNITY', 'S10TAR'))
    genericTrapID = property(lambda s: int(s.settings.get('GENERICTRAPID', 6)))
    specificTrapID = property(lambda s: int(s.settings.get('SPECIFICTRAPID',203)))
    oid = property(lambda s: s.settings.get('OID','1.3.6.1.4.1.506'))
    varBind = property(lambda s: s.settings.get('VARBIND',{
        'HOST': s.oid+'.3.8',
        'CLASSNUM': s.oid+'.3.6',
        'SEVERITY': s.oid+'.3.2',
        'TYPE': s.oid+'.3.3',
        'ALERTKEY': s.oid+'.3.1',
        'SUMMARY': s.oid+'.3.9',
        'EXPIRE': s.oid+'.3.7',
        'OTHERINFO': s.oid+'.3.18'
    }))

    def __init__(self, settings, **kwargs):
        self.settings = settings
        #trap specific settings
        self.hostname = str()
        self.classNum = int()
        self.severity = int()
        self.alertType = int()
        self.alertKey = str()
        self.summary = str()
        self.expire = int()
        self.otherInfo = str()
        self.__dict__.update(kwargs)


class AdaptToPySNMPv3(object):
    """I implement L{IDroneSNMPTrap} for PySNMPv3
       through component delegation.
    """
    SNMP_VERSION = "2c"
    implements(IDroneSNMPTrap)

    def __getattr__(self, attribute):
        """the price of delegation"""
        try: return object.__getattr__(self, attribute)
        except AttributeError:
            return self._original.__getattr__(attribute)

    def __init__(self, original):
        self._original = original

    @deferredAsThread
    def send(self):
        #pysnmp v3 trap initialization
        self._version = alpha.protoVersions[alpha.protoVersionId1]
        self._message = self._version.Message()
        self._message.apiAlphaSetCommunity(self.community)
        self._message.apiAlphaSetPdu(self._version.TrapPdu())

        self._message.apiAlphaGetPdu().apiAlphaSetAgentAddr(self.hostip)

        if self._message.apiAlphaGetProtoVersionId() == alpha.protoVersionId1:
            self._message.apiAlphaGetPdu().apiAlphaSetEnterprise(self.oid)
            self._message.apiAlphaGetPdu().apiAlphaSetGenericTrap(self.genericTrapID)
            self._message.apiAlphaGetPdu().apiAlphaSetSpecificTrap(self.specificTrapID)


        #setup mib object information
        self._message.apiAlphaGetPdu().apiAlphaSetVarBindList(
            (self.varBind['HOST'], self._version.OctetString(self.hostname)),
            (self.varBind['CLASSNUM'], self._version.Integer(self.classNum)),
            (self.varBind['SEVERITY'], self._version.Integer(self.severity)),
            (self.varBind['TYPE'], self._version.Integer(self.alertType)),
            (self.varBind['ALERTKEY'], self._version.OctetString(self.alertKey)),
            (self.varBind['SUMMARY'], self._version.OctetString(self.summary)),
            (self.varBind['EXPIRE'], self._version.Integer(self.expire)),
            (self.varBind['OTHERINFO'], self._version.OctetString(self.otherInfo))
        )
        #send the snmp trap now
        manager = Manager()
        manager.send(self._message.berEncode(), (self.trapHost, self.trapPort))


class AdaptToPySNMPv4(object):
    """I implement L{IDroneSNMPTrap} for PySNMPv4
       through component delegation.
    """
    SNMP_VERSION = "2c"
    implements(IDroneSNMPTrap)

    def __getattr__(self, attribute):
        """the price of delegation"""
        try: return object.__getattr__(self, attribute)
        except AttributeError:
            return self._original.__getattr__(attribute)

    @staticmethod
    def octet_string_2_tuple(octet):
        if type(octet) is tuple: return octet
        return tuple([int(i) for i in v.split(".")])

    def __init__(self, original):
        self._original = original
        #convert the varbinds from octet strings to tuples
        varbinds = {}
        for var, val in self.varBind.items():
            varbinds[var] = self.octet_string_2_tuple(val)
        self.settings['VARBIND'] = varbinds
        #lastly update the OID from octet string to tuple
        self.settings['OID'] = self.octet_string_2_tuple(self.oid)

    @deferredAsThread
    def send(self):
        #pysnmp v4 trap initialization
        self._version = api.protoModules[api.protoVersion1]
        self._trapPDU = self._version.TrapPDU()

        self._version.apiTrapPDU.setDefaults(self._trapPDU)
        self._version.apiTrapPDU.setAgentAddr(self._trapPDU, self.hostip)
        self._version.apiTrapPDU.setEnterprise(self._trapPDU, self.oid)
        self._version.apiTrapPDU.setGenericTrap(self._trapPDU, self.genericTrapID)
        self._version.apiTrapPDU.setSpecificTrap(self._trapPDU, self.specificTrapID)

        #setup mib object information
        self._version.apiTrapPDU.setVarBinds(
            self._trapPDU,
            (
                (self.varBind['HOST'], self._version.OctetString(self.hostname),),
                (self.varBind['CLASSNUM'], self._version.Integer(self.classNum),),
                (self.varBind['SEVERITY'], self._version.Integer(self.severity),),
                (self.varBind['TYPE'], self._version.Integer(self.alertType),),
                (self.varBind['ALERTKEY'], self._version.OctetString(self.alertKey),),
                (self.varBind['SUMMARY'], self._version.OctetString(self.summary),),
                (self.varBind['EXPIRE'], self._version.Integer(self.expire),),
                (self.varBind['OTHERINFO'], self._version.OctetString(self.otherInfo),),
            )
        )

        #send the snmp trap now
        trapMsg = self._version.Message()
        self._version.apiMessage.setDefaults(trapMsg)
        self._version.apiMessage.setCommunity(trapMsg, self.community)
        self._version.apiMessage.setPDU(trapMsg, self._trapPDU)

        transportDispatcher = AsynsockDispatcher()
        transportDispatcher.registerTransport(
            udp.domainName, udp.UdpSocketTransport().openClientMode()
        )
        transportDispatcher.sendMessage(
            encoder.encode(trapMsg),
            udp.domainName, 
            (self.trapHost, self.trapPort)
        )
        transportDispatcher.runDispatcher()
        transportDispatcher.closeDispatcher()


###############################################################################
# PySNMP import insanity
###############################################################################
version = 0
try:
    from pysnmp.version import getVersion as _snmpVersion
    version = _snmpVersion()[0]
except ImportError: pass
try:
    import pysnmp as _pysnmp
    version = _pysnmp.majorVersionId
except ImportError: pass
version = int(version)

#Try to figure out our version of pysnmp as the API isn't exactly guaranteed
if version == 0:
    import warnings
    warnings.warn("No pysnmp implementation could be found")
elif version == 3:
    #version 3 is the longest supported
    from pysnmp.mapping.udp.role import Manager
    from pysnmp.proto.api import alpha
    #adapt the configuration object to version 3 of pysnmp
    components.registerAdapter(
        AdaptToPySNMPv3, 
        PySNMP, 
        IDroneSNMPTrap
    )
elif version == 4:
    from pysnmp.carrier.asynsock.dispatch import AsynsockDispatcher
    from pysnmp.carrier.asynsock.dgram import udp
    from pyasn1.codec.ber import encoder #why isn't this in the pysnmp package?
    from pysnmp.proto import api
    #adapt the configuration object to version 4 of pysnmp
    components.registerAdapter(
        AdaptToPySNMPv4, 
        PySNMP, 
        IDroneSNMPTrap
    )
else:
    raise NotImplemented("PYSNMPv%d support is not implemented yet!!!" % \
            (version,))

###############################################################################
# PySNMP MetaClass Component Adapter
###############################################################################
class AdaptPySnmpAtInstantiation(type):
    """metaclass to adapt to the right implementation of pysnmp on first import
    """
    def __init__(klass, name, bases, members):
        super(AdaptPySnmpAtInstantiation, klass).__init__(name, bases, members)

    def __call__(klass, *args, **kwargs):
        instance = klass.__new__(klass, *args, **kwargs)
        instance.__init__(*args, **kwargs)
        #set the pysnmp_version from the module
        instance.pysnmp_version = version
        return IDroneSNMPTrap(instance) #adapters kick ass

#apply the adapter metaclass
PySNMPTrap = AdaptPySnmpAtInstantiation('PySNMP', (PySNMP,), {})
###############################################################################
# Data
###############################################################################

#Alert Types
PROBLEM = 1
RESOLUTION = 2
#Alert Severities
CLEAR = 0
INFO = 1
WARNING = 2
MINOR = 3
MAJOR = 4
CRITICAL = 5

__all__ = [
    'PySNMP',
    'PySNMPTrap',
    'PROBLEM',
    'RESOLUTION',
    'CLEAR',
    'INFO',
    'WARNING',
    'MINOR',
    'MAJOR',
    'CRITICAL',
]
