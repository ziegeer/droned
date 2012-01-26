The Events Subsystem
********************

DroneD is an event-driven program from two perspectives. First it is built
on Twisted which is an inherently event-driven development framework. However
Twisted only deals with I/O events and low-level stuff like that. DroneD
has its own eventing mechanism defined in the ``droned.events``
sub-package. Basically events are instances of the ``Event`` model (which is
an Entity subclass, so remember it acts like a ParameterizedSingleton) and
the constructor arg is the event name.

Unlike most other languages where the occurance of some event is called
"the event", droned distinguishes between "the event in general" and
occurances of the event. Take javascript for example, when a user clicks
their mouse on some widget a "mouseclick" event is created. Whereas droned
would create an *occurrance* of the general mouseclick event like this::

  from droned.models.event import Event
  Event("mouseclick").fire(x=100, y=200, widget=someWidget)

This is telling the *mouseclick* Event to create an occurance of itself. The
reason is that it makes for a really convenient interface, anyone who wants
to receive *mouseclick* events can simply do this::

  def myFunction(occurance):
    print occurrance.params

  Event("mouseclick").subscribe(myFunction)

So the *mouseclick* Event not only provides a means to create occurrances
but also a means to capture occurrances by subscribing to the event. This is
different than most other eventing systems which typically have some sort of
*Eventable* interface or base class that objects have to conform to in order
to emit events and users have to find the objects who will generate the events
they are interested in in order to capture them. DroneD's model is a little
simpler in my humble opinion. Events don't "come from somewhere" by default,
though you can easily specify the event source as an argument when you fire
the event. This is a little more dynamic and hence more flexible than the
approach which requires events to have a source. Another dynamic aspect of
droned's eventing system is that when an event is fired arbitrary data
can be passed along with the event in the form of *event parameters*. This can
be seen in the example above where ``Event("mouseclick").fire`` is called
with the parameters ``x=100, y=200, widget=someWidget``. What parameters
get passed will depend on the situation and in general I simply rely on
conventions rather than strict requirements (ie. "mouseclick events
*should always* provide an x, y, and widget parameters but they don't
necessarily *have to*). This is the cost of being highly dynamic. Notice
that the event parameters are accessible to event handling functions by
looking at the ``occurrance.params`` dictionary.

Since objects derived from ``Entity`` only exist after they have been
instantiated at least once, I have chosen to explicitly create each
Event object ahead of time in the ``droned.models.event`` module. This
makes it safe to assume that ``Event.objects`` will give you *all* the events
used in droned rather than merely those which have already been used at
least once. In the future I would recommend keeping with this practice so any
time you create a new type of event, create an instance of it in this module.

To see a list of all the events that droned has, look at the module I just
mentioned. To see what event parameters they typically come with, look for
code that fires the event in question.

.. note:: DroneD does **not** actually have a "mouseclick" event, this is
          just an example.
