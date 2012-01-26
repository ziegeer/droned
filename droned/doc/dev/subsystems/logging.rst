The Logging Subsystem
*********************

DroneD's logging system is pretty simple. All of it is defined in the
``droned.logging`` module. Basically there are several different
*types* of log messages, and a separate log file for each type.

Adding a new log type is as simple as adding your new type to the ``LOG_TYPES``
defined in the ``droned.logging`` module, then you can simply start
logging messages with the new type specified like so::

  from droned.logging import log

  log("Hello there!", type='greeting')

Seems pretty straightforward. But who wants to keep typing ``type='greeting'``
all the time? I sure don't. So there is the ``logWithContext`` function for
convenience::

  from droned.logging import logWithContext

  log = logWithContext(type='greeting')
  log("Hello there!")

Same effect, but less typing in the long run. So what else can you pass to the
``log`` function other than ``type``? Really whatever you want, the point is to
simply put in whatever metadata seems relevant, and as the emitter of log events
you should not really care how they get used. But what happens to your log
events (ie. messages with context paramters) you ask? They get handled by
the ``droned.logging`` module. If you can come up with something useful to
do with them then simply implement it yourself. For example, every log event
that has ``excessive=True`` will be dropped unless ``config.EXCESSIVE_LOGGING``
is enabled. Another feature is that any log event with ``error=True`` will get
a stacktrace logged along with it (if an exception was just recently thrown).
Whatever you think up, implement it in ``droned.logging`` and start using
it. That's pretty much all there is to it at this point.
