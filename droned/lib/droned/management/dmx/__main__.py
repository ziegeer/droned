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

__doc__ = """Daemon Maker eXtraordinaire - aka DMX an application wrapper"""
__author__ = """Justin Venus <justin.venus@orbitz.com>"""

#setup for daemonizing other processes
if __name__ == '__main__':
    import os
    import sys
  
    #find out where we are on the filesystem
    DIRECTORY = os.path.abspath(os.path.dirname(__file__))
    #cool, now setup the droned/kitt lib paths
    sys.path.insert(0,os.path.abspath(os.path.join(DIRECTORY,'..','..','..')))

    #could probably use some lovin!!!
    unforkedPid = os.getpid()
    childProcessPid = 0
    
    from twisted.internet import protocol, defer
    from twisted.python.log import FileLogObserver, textFromEventDict
    from twisted.python.util import untilConcludes
    import signal
  
    DEFAULT_REACTORS = {
        'Linux': 'epoll',
        'FreeBSD': 'kqueue',
        'SunOS': 'select',
    }
  
    #helper to get the best reactor
    def set_reactor():
        import platform
        REACTORNAME = DEFAULT_REACTORS.get(platform.system(), 'select')
        #get the reactor in here
        if REACTORNAME == 'kqueue':
            from twisted.internet import kqreactor
            kqreactor.install()
        elif REACTORNAME == 'epoll':
            from twisted.internet import epollreactor
            epollreactor.install()
        elif REACTORNAME == 'poll':
            from twisted.internet import pollreactor
            pollreactor.install()
        else: #select is the default
            from twisted.internet import selectreactor
            selectreactor.install()
  
        from twisted.internet import reactor
        set_reactor = lambda: reactor
        return reactor
  
  
    class ManagedLogger(FileLogObserver):
        """overriding emit to preserve original logs"""
        timeFormat = "" #destroy formatting
  
        def emit(self, eventDict):
            """ah, logs should be pretty much as the app intended"""
            text = textFromEventDict(eventDict)
            if text is None: return
            text.replace("\n", "\n\t")
            untilConcludes(self.write, text)
            untilConcludes(self.flush)  # Hoorj!
  
  
    class DaemonProtocol(protocol.ProcessProtocol):
        """we need to track your app and help you log it's information"""
        def __init__(self, name, label, r, deferred, **kwargs):
            self.deferred = deferred #callback deferred is always last
            self.reactor = r
            out = {
                'type': '%s-%s_out' % (name, label)
            }
            err = {
                'type': '%s-%s_err' % (name, label)
            }
            self.name = name
            self.label = label
            #setup application logging
            import droned.logging
            self.log_stdout = droned.logging.logWithContext(**out)
            self.log_stderr = droned.logging.logWithContext(**err)
             
        def inConnectionLost(self):
            """inConnectionLost! stdin is closed! (we probably did it)"""
            pass
  
        def errReceived(self, data):
            """write the error message"""
            self.log_stderr(str(data))
  
        def outReceived(self, data):
            """write the out message"""
            self.log_stdout(str(data))
  
        def outConnectionLost(self):
            """outConnectionLost! The child closed their stdout!"""
            pass
  
        def errConnectionLost(self):
            """errConnectionLost! The child closed their stderr."""
            pass
  
        def connectionMade(self):
            """Process is running, we close STDIN"""
            self.transport.closeStdin() # close stdin
            global childProcessPid
            global unforkedPid
            x = unforkedPid
            unforkedPid = 0
            #kill the intermediarry pid to let droned move on
            if x: self.reactor.callLater(2.0, os.kill, x, signal.SIGTERM)
            #see twisted.internet.interfaces.IProcessTransport
            childProcessPid = self.transport.pid
            sys.stdout.write('%s [%s] running with pid %d\n' % \
                    (self.name, self.label, childProcessPid))
  
        def processExited(self, reason):
            """our process has exited, time to shutdown."""
            sys.stdout.write('%s has exited' % (self.name,))
            if not self.deferred.called:
                self.deferred.errback(reason)
            global unforkedPid
            global childProcessPid
            childProcessPid = 0
            if unforkedPid: os.kill(unforkedPid, signal.SIGTERM)
  
        processEnded = processExited
  
  
    class DaemonWrapper(object):
        """we take care of your application in a race free way."""
        SIGNALS = dict((k, v) for v, k in signal.__dict__.iteritems() if \
                v.startswith('SIG') and not v.startswith('SIG_'))
        def __init__(self, r, name, label, cmd, args, env):
            self.reactor = r
            self.name = name
            self.label = label
            self.fqcmd = cmd
            self.args = args
            self.env = env
            self.exitCode = 0
            self.deferred = defer.succeed(None)
            import droned.logging
            self.log = droned.logging.logWithContext(type='dmx')
  
        def routeSignal(self, signum, frame):
            """send signals we receive to the wrapped process"""
            if signum == signal.SIGTERM:
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                #make sure we get stopped
                self.reactor.callLater(120, self.reactor.stop)
            global childProcessPid
            if childProcessPid:
                self.log('Sending %s to PID: %d' % \
                        (self.SIGNALS[signum], childProcessPid)) 
                try: os.kill(childProcessPid, signum)
                except:
                    droned.logging.err('when sending %s to pid %d' % \
                            (self.SIGNALS[signum],childProcessPid))
  
        def processResult(self, result):
            """try to get the exit code"""
            #give a moment for propagation 
            self.reactor.callLater(3.0, self.reactor.stop) 
            return result
  
        def running(self):
            """called when the reactor is running"""
            #signals go to the new child, need to do this once the reactor is
            #running to override it's default signal handlers.
            for signum, signame in self.SIGNALS.items():
                if signame in ('SIGKILL',): continue
                try: signal.signal(signum, self.routeSignal)
                except RuntimeError: pass #tried to set an invalid signal
            from droned.clients import command
            self.log('Starting %s [%s]' % (self.name, self.label))
            pargs = (self.name, self.label, self.reactor)
            pkwargs = {}
            global usetty
            global path
            self.deferred = command(self.fqcmd, self.args, self.env, 
                path, usetty, {0:'w',1:'r',2:'r'}, DaemonProtocol, 
                *pargs, **pkwargs
            )
            self.deferred.addBoth(self.processResult)
            return self.deferred
  
  
    env = os.environ.copy() #copy the environment settings
    args = tuple(sys.argv[1:]) #get all args after the original caller
  
  
    #needed for log routing
    logdir = env.pop('DRONED_LOGDIR', os.path.join(os.path.sep, 'tmp'))
    name = env.pop('DRONED_APPLICATION', 'app')
    label = env.pop('DRONED_LABEL', '0')
    usetty = bool(env.pop('DRONED_USE_TTY', '0'))
    path = env.pop('DRONED_PATH', os.path.sep)
    #try to make sure the log dir is clean and organized
    if name not in logdir:
        t = os.path.join(logdir, name, label)
        try:
            if not os.path.exists(t):
                os.makedirs(t, mode=0755)
            logdir = t
        except: pass
  
  
    #we only need to fork once b/c spawn in droned took care of the second fork
    if args and os.path.exists(args[0]):
        try: os.setsid() #be a leader
        except: pass #when debugging ie (running outside of twistd) this fails
        if os.fork() == 0:
            os.chdir(os.path.sep) #be nice
            os.umask(0) #be pure
            #should go back to the original protocol
#NOTE droned protocol will look for this on stdout
            sys.stdout.write('Daemon Pid: %d' % (os.getpid(),))
            sys.stderr.flush()
            sys.stdout.flush()
            import droned.logging
            sys.stdout = droned.logging.StdioKabob(0)
            sys.stderr = droned.logging.StdioKabob(1)
  
            maxfd = 4096 #maybe high
            try:
                import resource # Resource usage information.
                maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
                if (maxfd == resource.RLIM_INFINITY):
                    maxfd = 4096 #maybe high
            except: pass
  
            # Iterate through and close all file descriptors.
            for fd in range(0, maxfd):
                try: os.close(fd)
                except OSError: pass #ignore
            os.open(
                hasattr(os, "devnull") and os.devnull or "/dev/null",
                os.O_RDWR
            )
            os.dup2(0, 1)
            os.dup2(0, 2)
            #create logging contexts
            loggers = [
                '%s-%s_out' % (name, label),
                '%s-%s_err' % (name, label),
            ]
            #defaults for logging are pretty good
            droned.logging.logToDir(directory=logdir)
  
            #setup logging
            reactor = set_reactor()
            #preserve application logging, but mixin daily rotation
            droned.logging.logToDir(
                directory=logdir,
                LOG_TYPE=tuple(loggers),
                OBSERVER=ManagedLogger
            )
            #create our wrapper
            dmx = DaemonWrapper(reactor, name, label, args[0], args[1:], env)
  
            def killGroup():
                 """kill everybody"""
                 dmx.log('terminating process group')
                 signal.signal(signal.SIGTERM, signal.SIG_IGN)
                 os.kill(-os.getpgid(os.getpid()), signal.SIGTERM)
  
            reactor.addSystemEventTrigger('before', 'shutdown', killGroup)
            reactor.callWhenRunning(dmx.running)
            reactor.run() #run until killed
            sys.exit(dmx.exitCode)
        else:
            #this is the parent that will exit to make app a daemon
            reactor = set_reactor()
            #sit and wait for the child to terminate us
            reactor.callLater(120, sys.exit, 1)
            reactor.run()
            sys.exit(0)
    sys.exit(255)

