The Services Subsystem
**********************

DroneD is largely a reactive application, meaning that it doesn't
*do anything* on it's own in general. It usually is responding to some
outside stimulus or directive. The exception to this however is for
certain activities such as maintaining its jabber connectivity or regularly
persisting its environment model to disk. This is what services are generally
used for.


The Service API
===============
While Twisted comes with a mechanism for writing services, it is kind of
clunky and mostly suited to network services. So I decided to write my own
service system, and ultimately it is very very simple.

A service is not a class or an object in any direct way, it is simply a
module in the ``droned.services`` sub-package that exposes the following
functions:

* ``install(rootService)`` - Where *rootService* is the root Twisted service.
  This is useful when you want to write a service that actually *is* a Twisted
  service. This includes the Nexus webapp and Manhole SSH server. You have to
  also write a line in ``droned-daemon.py`` that calls this. While not all
  services actually *need* an install function to do anything useful, some do
  and I figured it is best to keep the API consistent.
* ``start()`` - When this is called you should start your service. What that
  means exactly depends on your service. You have to write some code to
  actually call this. I like to use the  ``AUTOSTART_SERVICES`` list from the
  config and put something like this in   my ``install`` function:
  ``if 'myservice' in config.AUTOSTART_SERVICES: start()``
* ``stop()`` - When this is called you should stop your service. So far I have
  not actually used this but I figure its a good idea to at least support it.
* ``running()`` - Should return True if your service is running, False otherwise.


To see some example services... just read their code. They are generally very
simple. The most complicated would be the Jabber service, and still it's
"service code" is very minimal.
