Twisted Reactor Basics
======================

The Reactor
-----------
Twisted is basically one great big I/O event loop, called *the reactor*.
If you have ever used the ``select`` or ``poll`` system calls, or have
done any amount of GUI programming then you should be familiar with this
concept. If not, I would recommend getting some degree of familiarity with
it before diving right into Twisted.

Twisted programs are generally single threaded, and with two minor exceptions
[#f1]_ droned is completely single threaded. Much like other non-threaded
concurrency techniques this leads to much safer and often better code than
you would end up with by using threads. Twisted achieves very high performance
and scalability by leveraging the ``epoll`` [#f2]_ system call.


Friends Don't Let Friends Write Blocking Code
---------------------------------------------
Generally there are only 2 reasons for code to block.

1. You want to ``sleep`` for some arbitrary interval
2. You need to perform an I/O operation (like writing to a socket or file)

For the first case Twisted has a very simple and useful function::

	from twisted.internet import reactor
	reactor.callLater(delay, function, *args, **kwargs)

This waits ``delay`` seconds (can be a float) and then calls
``function(*args,**kwargs)``. Pretty simple.

The second case is harder to generalize about because it depends on your
situation. There are really two ways to handle a blocking I/O operation.

First, if the operation is simple and you don't care what happens when it
completes then you can use the following function to do the operation
in a separate thread::

	from twisted.internet import reactor
	reactor.callInThread(function, *args, **kwargs)

Which calls ``function(*args, **kwargs)`` in its own thread. However, if you
*do* care about the result you can use this instead::

	from twisted.internet import threads
	deferredResult = threads.deferToThread(function, *args, **kwargs)
	deferredResult.addCallback(doSomethingWithTheResult)

This functionality is less frequently needed because when you care about
the result you usually use Twisted's more natural facilities. Which brings us
to our second situation.

The natural way to do I/O in Twisted is to use *non-blocking* files and
sockets. Usually that means you have to do a lot of low-level system
calls and error checking and crap like that but fortunately this is Twisted's
raison d'etre.

.. warning::
   It is **highly** recommended that you avoid using threads except when doing
   simple I/O. Python's *Global Interpreter Lock* (aka. the GIL) heavily
   penalizes performance because only one thread is allowed to execute
   code at any given time. Doing I/O is OK though because Python is smart
   enough to allow I/O to occur without acquiring the GIL.


Twisted To The Rescue
---------------------
Twisted provides some very handy interfaces that abstract the underlying
dirty work of non-blocking network code. One thing that the Twisted docs
don't do a very good job of explaining (in my opinion) is how connections
get established and handled. Generally it works like this for clients:

#. You instantiate a ``twisted.internet.protocol.ClientFactory`` (or some
   subclass thereof)
#. You give that ClientFactory a Protocol class
   (example: ``myFactory.protocol = MyProtocol``)
#. You tell Twisted to connect to some *host:port* using your factory
   (example: ``reactor.connectTCP(host, port, factory)``)
#. The reactor tries to establish the connection for you
#. If it succeeds, it asks your factory for a protocol instance.
   If it fails, it tells your factory that it failed to connect and the factory
   then either attempts to reconnect (if its a ReconnectingClientFactory) or
   does nothing (this is a behavior you often override by making your own
   ClientFactory subclass).
#. Assuming the connection succeeded, the reactor simply calls event handlers
   on the Protocol instance it got from your factory such as ``connectionMade``,
   ``dataReceived``, or ``connectionLost``. Your Protocol class defines what to
   do with these events and maintains the state of the connection. The protocol
   object can send data to the remote side by calling
   ``self.transport.write(data)`` or disconnect by calling
   ``self.transport.loseConnection()``. Those operations will never block.

That's pretty much it. For servers the process is very similar:

#. You instantiate a ``twisted.internet.protocol.Factory`` (or some subclass
   thereof)
#. You give that Factory a Protocol class
   (example: ``myFactory.protocol = MyProtocol``)
#. You tell Twisted to listen on a port using your factory
   (example: ``reactor.listenTCP(port, factory)``
#. When the reactor accepts a connection on your listening port, it asks your
   factory for a Protocol instance
#. The reactor then calls event handlers on the protocol object the same way it
   does for clients.


After reading this I highly recommend reading the Twisted docs because they
will probably make more sense and will show you a lot of handy techniques
and short-cuts. Here are some brief examples of how droned uses Twisted's
client facilities.

* For a custom client protocol implementation, look at
  ``droned.protocols.gremlin.GremlinProtocol``
* For a super simple HTTP client, look at
  ``droned.models.release.Release.download()``.

Now go read the
`Twisted docs <http://twistedmatrix.com/projects/core/documentation/howto/index.html>`_.


.. [#f1] Due to restrictions of the WSGI standard, droned's internal
         webapp, Nexus, handles requests in their own threads. This is
         largely a non-issue for concurrency problems as Twisted provides
         some very good facilities for ensuring that all the "real work"
         always occurs in the main thread, which avoids the need for locking
         throughout the entire code base. The other exception is for local
         filesystem writes like those done by the Journal service. These
         operations have no side-effects and thus are thread-safe, plus
         using a separate thread purely for I/O actually increases performance
         in general (despite the dreaded GIL).

.. [#f2] This system call is only available on Linux 2.6 kernels and later.
         In the off chance it is required to run droned on something other
         than Linux, Twisted allows you to simply use a different reactor
         implementation underneath without changing any of your application
         code.
