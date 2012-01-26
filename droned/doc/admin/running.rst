******************
Running DroneD
******************


Command-line Options
====================
DroneD is launched by executing the ``droned-daemon.py`` script. Here
is its usage statement::

    Usage: droned-daemon.py [options]
    Options:
      -n, --nodaemon   don't daemonize, don't use default umask of 0.
          --stop       Stop a running Drone Daemon.
          --config=    Use configuration from file, overrides commandline
          --deadline=  Maximum time to wait for droned to shutdown. [default: 10]
          --debug=     Don't install signal handlers and turn on debuggging
                       [default: False]
      -g, --gid=       The gid to run as. [default: nobody]
          --homedir=   Location to use as a home directory [default:
                       /var/lib/droned/home]
          --hostdb=    The directory to providing ROMEO configuration. [default:
                       /etc/hostdb]
          --journal=   Location to write system history [default:
                       /var/lib/droned/journal]
          --logdir=    Location to write system logs [default: /var/log/droned]
          --maxfd=     Maximum File Descriptors to use. [default: 1024]
          --pidfile=   Name of the pidfile. [default: /var/run/droned.pid]
          --port=      The command and control port [default: 5500]. Must be an int
                       between 0 and 65535.
      -r, --reactor=   Which reactor to use. [default: epoll]
      -u, --uid=       The uid to run as. [default: nobody]
          --umask=     The (octal) file creation mask to apply. [default: 0]
          --wait=      Maximum time to wait for droned to daemonize. [default: 60]
          --webdir=    Location to use as a webroot directory [default:
                       /var/lib/droned/web]
          --version    droned version
          --help       Display this help and exit.

To simply start droned, run it with no arguments. However if another
droned instance is already running (if ``droned.pid`` exists)  you will
receive an error. To kill the running droned simply run
``./droned-daemon.py --stop``.

The ``--debug`` option causes droned to run in the foreground (instead of
daemonizing) and also causes all log output to be printed to standard out
instead of to the usual log files.

The ``--logdir`` option allows you to specify an alternative directory in
which to write log files. The default is ``log/``.


Doing a Journal Rollback
========================
DroneD stores journal entries (snapshots of its environment model) in
the ``journal/`` directory. Each file is named ``TIMESTAMP.pickle`` where
*TIMESTAMP* is a UNIX epoch time representing the point in time at which the
snapshot was taken.

When droned starts up, it reads the *latest* entry. So in order to rollback
to a previous point in time, simply move the entries that occurred after that
point in time out of the journal directory and restart droned.

Be mindful however that droned may write a new journal entry at any
moment so it is good to double-check the journal directory after shutting
down droned but before starting it back up.

.. note:: Journal entries are intended to be completely portable and
          transferrable to other droned installations, even if
          they are for a different version of droned.

