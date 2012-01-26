from kitt.interfaces import IDroneDApplication, implements
from droned.applications import ApplicationPlugin
from droned.models.app import AppVersion
from droned.models.event import Event
from kitt.decorators import debugCall, safe
from droned.logging import err

try: import rpm
except: rpm = None

class RPMApplication(ApplicationPlugin):
    """I am a standard RPM Application Plugin.  I should work for standard
       rpm'd installations given you romeo config shortname is the same as
       the name of your rpm.
    """
    
    SEARCH_DELAY = 5.0 #override in romeo
    implements(IDroneDApplication)

    def __init__(self, *args, **kwargs):
        Event('instance-found').subscribe(self._check_version)

    @safe(None)
    def _check_version(self, occurrence):
        ai = occurrence.instance
        if ai.app.name == self.name:
            return self._updateVersion(None, ai.label)

    def _updateVersion(self, result, label):
        thisInst = self.getInstance(label)
        try:
            ts = rpm.TransactionSet()
            mi = ts.dbMatch('name', self.name)
            for h in mi:
                if not h: break
                version = AppVersion.makeVersion(self.name, h['version'])
                if version > thisInst.appversion:
                    thisInst.version = version
        except:
            err('exception while setting version')
        return result

    def startInstance(self, label):
        """I query the RPM DB and make sure the version is up to date"""
        d = ApplicationPlugin.startInstance(self, label)
        d.addCallback(self._updateVersion, label)
        return d #return the deferable object

#you don't have the necessary language bindings
if rpm: __all__ = ['RPMApplication']
