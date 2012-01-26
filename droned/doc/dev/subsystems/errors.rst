DroneD Errors
*****************

This isn't really subsystem per se, but I couldn't think of anywhere else
in the documentation to cover it. The ``droned.errors`` module defines
several custom exceptions. These are typically used to encapsulate failures
that should have some known data associated with them. For example, the
``DroneCommandFailed`` exception has a ``resultContext`` attribute because
all droned commands return a *resultContext*, even the ones that fail. This
allows you to catch an exception from a failed droned command and pluck out
the raw *resultContext* that caused it. The other exceptions currently defined
are geared towards other high-level operations such as verifying or promoting a
release. You should really just read the ``droned.errors`` module because
it is only like 30 lines of code.
