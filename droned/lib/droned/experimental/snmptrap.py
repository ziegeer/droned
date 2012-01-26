from zope.interface import Attribute, Interface

class IDroneSNMP(Interface):
    SNMP_VERSION = Attribute("str usually 1, 2c, or 3")
    #snmp trap server settings
    hostip = Attribute("this machines ip address")
    trapHost = Attribute("ip or hostname of snmp trap server to send traps too")
    trapPort = Attribute("port to connect to on snmp trap server usually 162")
    community = Attribute("Community name of the SNMP agent (defined on the agent)")
    genericTrapID = Attribute("Cold Start, Link Up, Enterprise, etc.")
    specificTrapID = Attribute("When Generic is set to Enterprise a specific trap ID s identified ")
    oid = Attribute("Object Identifiers uniquely identify manged objects in a MIB hierarchy")
    varBind = Attribute("should be a dictionary of varbind info")
    #snmp trap info settings
    hostname = Attribute("(str) hostname")
    classNum = Attribute("(int) Class Identifier")
    severity = Attribute("(int) Clear, Info, Warning, Minor, Major, or Critical")
    alertType = Attribute("(int) Problem or Resolution")
    alertKey = Attribute("(str) Identifier for the Alarm")
    summary = Attribute("(str) Why are you sending this message")
    expire = Attribute("(int) how long should this alarm exist before automatically expiring")
    otherInfo = Attribute("(str) User defined")


class IDroneSNMPTrap(IDroneSNMP):
    def send():
        """send the snmp trap to the remote traphost

           @return L{twisted.internet.defer.Deferred}
        """

__all__ = ['IDroneSNMP', 'IDroneSNMPTrap']
