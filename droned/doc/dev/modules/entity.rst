droned.entity
=================

.. automodule:: droned.entity

This module defines the core conceptual classes used by DroneD's
object model of the environment.

ParameterizedSingleton
----------------------

.. autoclass:: ParameterizedSingleton
   :members: exists, delete, isValid

   For example, say we are trying to model human beings and we want to define
   them with a ``Person`` class. Now assume we can and uniquely identify
   any person by their full name (for the sake of this example). If we give
   our ``Person`` class the ``ParameterizedSingleton`` metaclass then we have
   a powerful and convenient way of creating an object model of people. Since
   people are uniquely defined by their full names we write our ``Person``
   constructor to take two arguments, the person's first and last name.
   What ``ParameterizedSingleton`` does is ensure that every time we
   instantiate ``Person`` with the same first and last name we get back the
   exact same ``Person`` object. This is very convenient because we don't
   have to store the ``Person`` objects somewhere and look them up each
   time we want them. It is also conceptually powerful because the object
   model more closely reflects the reality we are modeling. For example,
   ``Person("Bob", "Jones")`` will instantiate a ``Person`` object the first
   time we call it, but subsequent calls of ``Person("Bob", "Jones")`` will
   yield the exact same object. Note that a call to
   ``Person("Bob", "Patterson")`` or ``Person("Bill", "Jones")`` would yield
   different ``Person`` objects.

   It is very important to remember when writing classes that use
   ``ParameterizedSingleton`` that the constructor args must be *hashable*
   and **must** uniquely identify the object in all situations.


Entity
------
The ``Entity`` class uses ``ParameterizedSingleton`` as its metaclass, and thus
all subclasses inherit the ``ParameterizedSingleton`` behavior.

.. autoclass:: Entity
   :members: serialize, deserialize, __getstate__, construct, __repr__

   .. attribute:: serializable

      If True, all instances of this class will be serialized and saved by the
      Journal service. Defaults to False.

Here is a brief example of a serializable ``Entity``::

  class Person(Entity):
    serializable = True

    def __init__(first_name, last_name):
      self.first_name = first_name
      self.last_name = last_name

    def __getstate__(self):
      return {
        'first_name' : self.first_name,
        'last_name' : self.last_name
      }

    @staticmethod
    def construct(state):
      return Person( state['first_name'], state['last_name'] )


This may seem like a lot of extra work to simply serialize an object but this
approach has two key advantages. First if a class definition changes in such a
way that would normally be incompatible with basic pickling (often from
changes to the constructor or the names of class members) then this allows
such a change to be handled explicitly and safely in the ``construct(state)``
method. Second and even more importantly, pickling always creates *new objects*
which doesn't make sense when using ``ParameterizedSingleton``. One of the
planned features for droned is to transfer state information between
multiple droned instances for failover capability. The ``construct(state)``
method allows the deserialization process to update existing objects
rather than always creating new ones.
