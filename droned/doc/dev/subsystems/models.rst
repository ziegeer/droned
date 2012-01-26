The Models Subsystem
********************

DroneD's object model is perhaps the most important component of the entire
system. Without a doubt, it is absolutely necessary to get comfortable with
how models are defined and how they are used. It all starts with the
:mod:`droned.entity` module. This module defines two important classes:
``ParameterizedSingleton`` and ``Entity``. First we'll cover
``ParameterizedSingleton``.

``ParameterizedSingleton`` is not a regular class, it is a *metaclass*.
A metaclass is simply something that can be used to *create classes*, the
same way that a class is used to *create objects*. This distinction is a bit
subtle because in Python, classes are first-class objects. Metaclasses are
often very confusing at first so I will try to ease the pain a little bit.
For a more thorough explanation of Python's implementation of metaclasses you
should read http://www.python.org/download/releases/2.2/descrintro/


A Subtle Problem
================
Consider the following example class we'll try to use to model market stocks::

  class Stock(object):
    price = None

    def __init__(self, tickerSymbol):
      self.tickerSymbol = tickerSymbol

    def updatePrice(self, price):
      self.price = price

Simple enough, but it turns out there is a mis-match between the way our
``Stock`` class models stocks and how we actually think of stocks in the
real world. This can be made clear by an example::

  x = Stock("OWW")
  x.updatePrice(42)
  y = Stock("OWW")
  y.updatePrice(24)

  x.tickerSymbol == y.tickerSymbol # True
  x is y # False
  x.price == y.price # False

If you look at that code and think *"There's nothing wrong there"* then you're
thinking too much like a programmer. Look at what the code *means* as a model
of the real world. It basically is saying there are two different OWW stocks
with different prices. But we know that this doesn't make sense because there
can only be one OWW stock and it can only have one price at any given point in
time. The problem is that the notion of an object's *identity* is different in
the real world than it is in the world of our program. At this point you are
probably asking, *"What the hell is he getting at?"* to which I must reply,
*"You'll see."*.

The most common ways of dealing with this problem are to either:

* pass references to the original *OWW* Stock object to any parts of your
  program that needs it
* to create some sort of global data structure that allows different parts
  of the program to lookup the same object given the same information (ie.
  a dict to lookup ``Stock`` objects by their ticker symbol).

This works fine but it is far from a general solution and one of the first
things I realized when I started writing droned was that I had a lot of
different types of objects that needed this same sort of mechanism. So I
created ``ParameterizedSingleton``.


Parameterized Singletons
========================
A *singleton* is an object that there can inherently be only one of. This is
useful for things like connection pools or configuration managers. When you
have a singleton class, every time you instantiate it you get back the same
instance. In our case however, what we want is to get the same instance
whenever we instantiate our class with the *same parameters*. Basically, this
is what we want::

  Stock("OWW") is Stock("OWW") # We want this to be True

If you're still wondering *why* we want this behavior, here's a quick
justification.

#. It's very convenient to not have to look up objects or pass them around
#. It eliminates a lot of boiler-plate code
#. This *mere convenience* actually allows you to think of your objects as
   *nouns* and expressions about them become more *english-like*.

The last point is my personal favorite, and if you spend any amount of time
reading the droned code you will begin to see why. So that is *why*
we want this functionality, using ``ParameterizedSingleton`` as a metaclass is
*how* we get it. The code is fairly simple, but probably confusing if you
aren't familiar with how Python creates objects. To learn more read the
documented I linked to before about metaclasses.


The Entity Class
================
``Entity`` is the base class of all model classes used in DroneD. Since
``Entity`` uses ``ParameterizedSingleton`` as its metaclass, all model classes
inhert the ``ParameterizedSingleton`` functionality. This means that whenever
you write a model class **you must pick your constructor arguments carefully**.
The constructor arguments *must* be all of the information that uniquely
identifies instances of your class. So for example if you were writing a Person
class, a good constructor argument would be something like their social
security number (because it uniquely identifies a person). If you wanted to
make the assumption that all people have unique names, then the constructor
args could be ``(firstName, lastName)``. But you should **never** allow other
information that is not strictly necessary to *identify* the object in the
constructor args. So for example you would not allow *age* to be a constructor
argument. In our ``Stock`` example above, ``tickerSymbol`` is a good
constructor argument, whereas ``price`` would not be.

That said, the purpose of the ``Entity`` class is to give all model objects
some common behaviors. In particular, ``Entity`` provides a serialization
interface that allows models to be serialized by the Journal service.


Model Conventions
=================
As you read through model code, you'll notice I make extensive use of
*property descriptors*. To the uninitiated these are basically methods
that appear to be plain old attributes and they are invoked when you
look them up as attributes. Technically this only saves you from typing
a pair of parenthesis (though they have fancier uses than this) but this reason
alone turns out to be quite nice as your code looks much more readable and
english-like.

One important descriptor that is inherited by all classes that use
``ParameterizedSingleton`` is the *objects* descriptor. For example,
the following code would print the hostname of every ``Server`` that
droned knows of::

  from droned.models.server import Server
  for server in Server.objects:
    print server.hostname

You'll see that one used a lot. Another common use for properties is to
dynamically calculate related objects. For example, every ``App`` is supposed
to run on a certain set of servers, so each ``App`` object maintains a
``shouldRunOn`` attribute that is a set of ``Server`` objects. Given this
we can also determine what apps should run on a given ``Server`` without having
to maintain a separate data structure. The ``Server`` class simply has a
``apps`` property that enumerates ``App.objects`` and picks out the ones that
have the given server in their ``shouldRunOn`` set. Here's a snippet to
clarify::

  class Server(Entity):
    appinstances = property( lambda self: (i for i in AppInstance.objects if i.server is self) )
    apps = property( lambda self: (a for a in App.objects if self in a.shouldRunOn) )

Here we see two property descriptors, ``appinstances`` which dynamically
enumerates all of the ``AppInstance`` objects that exist on a given
``Server`` as well as ``apps`` which enumerates all of the
``App`` objects that are *supposed to* run on the server. You might think
that all that dynamic calculation would be expensive but it turns out by
using generator expressions that the cost is minimized and it turns out to
be rather inexpensive. Not to mention that you do not have to keep a bunch of
different data structures in sync, which would require a lot more code and be
subject to all sorts of potential issues. It is also very nice to be able to
say things like ``(i for i in AppInstance.objects if i.app in myServer.apps)``
rather than something like
``(i for i in AppInstance.getObjects() if i.app in myServer.getApps())``.
Most of this stuff really is purely aesthetic, but I firmly believe that
aesthetic quality is a good reflection of substantive quality, at least when it
comes to code.
