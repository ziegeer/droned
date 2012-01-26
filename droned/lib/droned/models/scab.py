from droned.entity import Entity
from droned.models.event import Event
import config

class Scab(Entity):
    """Track Processes that Don't have an AppManager"""
    localInstall = property(lambda s: bool(s.server.hostname == config.HOSTNAME))
    pid = property(lambda s: s.running and s.process.pid or 0)
    inode = property(lambda s: s.running and s.process.inode or 0)
    ppid = property(lambda s: s.running and s.process.ppid or 0)
    memory = property(lambda s: s.running and s.process.memory or 0)
    fd_count = property(lambda s: s.running and s.process.fd_count or 0)
    stats = property(lambda s: s.running and s.process.stats or {})
    threads = property(lambda s: s.running and s.process.threads or 0)
    executable = property(lambda s: s.running and s.process.executable or None)
    environ = property(lambda s: s.running and s.process.environ or {})
    cmdline = property(lambda s: s.running and s.process.cmdline or [])
    
    def __del__(self):
        Event('scab-lost').unsubscribe(self._cleanup)
    
    def __init__(self, server, pid):
        self.server = server
        self.process = AppProcess(server, pid)
        self.context = {} #extra information about the scab
        Event('scab-lost').subscribe(self._cleanup)
        Event('scab-found').fire(scab=self)
        
    def _cleanup(self, occurrence):
        try:
            if occurrence.scab == self:
                Scab.delete(self)
        except: pass

    @property
    def running(self):
        try:
            assert AppProcess.isValid(self.process) 
            assert not self.process.managed
            assert self.process.running
            return True #made it this far, must be running
        except:
            self.process = None
        return False
    
    def assimilate(selfs, appname, appversion, applabel):
        """attempt to manage an unmanaged process"""
        if self.running:
            ai = AppInstance(self.server, AppVersion(App(appname), appversion), applabel)
            if ai.running: return False#this instance is already running
            ai.updateInfo({'pid': self.process.pid})
            if ai.running and ai.pid == self.process.pid:
                Event('scab-lost').fire(scab=self)
                return True
        return False
        
from droned.models.app import AppProcess, AppInstance, AppVersion, App
