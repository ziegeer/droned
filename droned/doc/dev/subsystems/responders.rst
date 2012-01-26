The Responders Subsystem
************************

Finally, we have gotten to *Responders*. This is probaby the most likely
place to start hacking on droned because *responders* are used to define
how droned *responds* to jabber messages (though it would be entirely
possible to have responders work for other types of messages like email
as well!). A responder is simply a function defined in a module within the
``droned.responders`` sub-package (and it has to use a special
``@responder`` decorator). This is probably easiest to explain with an
example::

  # This should be in a file in lib/droned/responders/
  from droned.responders import responder

  @responder(pattern="^wassup( (?P<name>.+))?$", form="wassup [name]",
   help="Give a shout-out to droned")
  def wassup(context, name):
    chat = context['conversation']
    if name == 'homey':
      chat.say("sup G")
    else:
      chat.say("Greetings sir.")

So let's go through this line by line. First we import the ``responder``
decorator from ``droned.responders`` (so it's defined in the __init__.py).
Then we define a ``wassup`` function (this is our responder). The ``responder``
decorator requires several keyword args, here's what they are:

* ``pattern`` - This is a regular expression that is used to determine what
  messages this responder applies to. When someone sends a message to
  droned he looks at all of his responder functions for one that has a
  pattern that matches the message. When he finds a responder that matches
  he calls it. If none match you get the standard "Sorry I don't understand..."
* ``form`` - This is a human-readable description of how to use your responder.
  It is used by the ``?`` responder to print a useful help message. This is
  required.
* ``help`` - This is also used by the help system and should very briefly
  describe what your responder does.

There are other optional arguments but you generally won't need to worry
about them unless you are a droned whiz. And if you're a droned
whiz then why would you need documentation on them :) ?

So there is another important bit that I haven't explained yet. Notice
that our ``wassup`` function takes two arguments, ``context`` and ``name``. The
``context`` argument is *always* passed to all responder functions. The
``name`` argument is only passed because we used the *named group* regex
syntax (ie. ``(?P<groupName>groupPattern)``). So basically if the user
types "wassup fool" then the pattern will match and it will have a named
group (called *name*) that matches the value "fool". This means your function
will be called with ``name="fool"``. However if the user simply typed "wassup"
then the latter part would not match (but that's OK because the group is
followed by a ``?`` quantifier) so your function would be called with
``name=None``. Simple enough.

Now what about that ``context`` part, what the heck is that? Well it turns out
that every Conversation (a ``droned.models.conversation.Conversation``
object) has a *context* dictionary. This is used to maintain the state of the
conversation. So for instance when you tell droned ``app hse``, there is
an ``app`` responder that changes the conversation's context like so::

  @responder(pattern="^app (?P<name>.+)$", form="app <name>",
   help="Talk about an application")
  def app(context, name):
    if App.exists(name):
      context['subject'] = context['app'] = App(name)
      context['conversation'].say("Ok, we're talking about %s" % name)
    else:
      context['conversation'].say("Sorry, I've never heard of %s before" % name)

That is the actual *app* responder. So hopefully you can imagine how a
conversation's *context* might be useful. Also note that you can really
use it to contain *anything* you want, but as usual you have to rely on
conventions. Note that every context has a *conversation* key that maps
to the underlying ``Conversation`` object. You should read the code for
the Conversation model to get familiar with it, it is really quite simple.

.. note:: Since I like avoiding abbreviations wherever possible and I hate
          typing "conversation" over and over again I like to use "chat" as
          a short name for ``context['conversation']``. This is merely a
          convention and is not meant to indicate that droned is talking
          in an actual chat room, though that is sometimes the case.
