Twisted Deferreds
=================
One of the most important things to understand and be comfortable with before
working extensively with Twisted is ``Deferred`` objects. They may look a
little confusing at first but they really are very simple beasts and they
will make you wish they were a standard feature of Python.


Why Deferreds Exist
-------------------
Say you want to fetch a web page and parse it? Twisted has a wonderful method
for doing this::

	from twisted.web.client import getPage
	result = getPage("http://www.orbitz.com/")

That's it. If you don't already love Twisted you should by the end of this
page. But at this point you should be asking this question:

*If Twisted is single-threaded and non-blocking, how does it fetch a web page
without blocking my code that calls getPage()?*

Excellent question. The answer is, it doesn't block you because ``getPage()``
returns *immediately*, even before the connection to *orbitz.com* has been
established. So your next question should be:

*If it returns a result before it even connects to orbitz.com, then what does
it return?*

Ding-ding-ding! A ``Deferred`` object! As you might guess, a ``Deferred``
object is used to indicate a *pending result* from some operation that would
otherwise block. This is not specific to the ``getPage()`` function but as
you will see deferreds permeate the entire Twisted framework. So the next
question you might be asking would be:

*I just want to download a web page, what am I supposed to do with a Deferred
object?*

Simple, just tell it what to do with the result once it becomes available. This
is done by adding *callbacks* to the ``Deferred``. There are two different types
of callbacks: regular *callbacks* and *errbacks*. An *errback* is simply a
callback that gets called when the operation fails (like if we could not
connect to *orbitz.com* for some reason). Here is a complete example::

	from twisted.web.client import getPage
	deferredResult = getPage("http://www.orbitz.com/")
	deferredResult.addCallback(parseIt)
	deferredResult.addErrback(printError)

Where ``parseIt()`` and ``printError()`` are some functions you write. When
Twisted successfully fetches the page it will call your ``parseIt()``
function with a single argument, the result of the operation. In this
case that is the HTML content of *orbitz.com*. If the operation failed
Twisted will call your ``printError()`` function with a single argument,
a ``twisted.python.failure.Failure`` object. Don't worry about ``Failure``
objects too much just yet, they are merely asynchronous-friendly wrappers for
plain old Exceptions.

At this point I would recommend reading the following Twisted docs, in order:

* http://twistedmatrix.com/projects/core/documentation/howto/async.html
* http://twistedmatrix.com/projects/core/documentation/howto/defer.html
* http://twistedmatrix.com/projects/core/documentation/howto/gendefer.html
* http://twistedmatrix.com/projects/core/documentation/howto/deferredindepth.html

This is a lot to read, especially for such a simple concept. But it is useful
to ingrain this stuff in your brain as much as possible so the first time
you try to hack on droned you will have a good idea of when you should be
using a ``Deferred`` and how to deal with them coming from other code.


Some Pointers For Using Deferreds
---------------------------------
#. Never call ``someDeferred.callback(result)`` unless **you created**
   ``someDeferred``. The rule of thumb is that the deferred's creator is the one
   who calls it.
#. If you do call ``someDeferred.callback(result)`` it is *always wise* to
   check ``if someDeferred.called: ...`` first. You never know if an exception
   occurred in the processing chain somewhere and the deferred has already
   started calling errbacks. Calling ``.callback()`` on a deferred that has
   already been called will raise an Exception and is often tricky to debug.
#. Remember that the return value of your callback functions will get passed
   to the *next* callback function in the callback chain. If you don't return
   anything explicitly, your callback will return ``None``. As a rule of thumb,
   return the result you were given unless you have a reason to do otherwise.
#. If an exception occurs in any callback function then the *next errback* will
   get called with a ``Failure`` that wraps the exception.
#. You should **never ever ever** let errors go unhandled in your callback
   chains. This means you should *always* have either an *errback* or an
   *except block* that catches potential exceptions.

Enjoy using Twisted!
