******************************
Quick Jabber Command Reference
******************************


DroneD Commands
---------------
DroneD allows you to send commands directly to droned agents. This is not
intended for obscure debugging practices but rather for day-to-day use. The
reason is that droned already has a very simple and powerful command set for
managing a server and the applications on it. So rather than duplicating those
commands in droned, I chose to simply allow you to talk directly to droned.

To tell droned that you want to send a droned command, simply start your 
command with an ``@`` character. So to send a droned agent the ``foo`` command
you would tell droned ``@foo``.

Also droned currently only lets you talk directly to one droned agent
at a time, and you specify which one by *talking about a server*. So for
example::

  server egapp01
  @wl status

Tells droned you want to talk about the ``egapp01`` server, and then
you want to send the droned agent on that server the ``wl status`` command.

All droned commands have a *help message* that you can access by simply
putting ``help`` before the command. So to get help on the ``wl`` command
mentioned above you would simply say ``@help wl``.

So what commands can you send to droned? There are quite a few, but the
vast majority of the time you will use *AppManager commands*. That is,
commands that are used to talk to an AppManager service running within
droned. Each AppManager command is simply named after the application
it manages. So in our previous example ``@wl status`` we actually used
the ``wl`` AppManager command with a single argument, ``status``. This
essentially asks the ``wl`` AppManager for status on the instances it
is managing. For more AppManager command arguments simply run ``@help wl``.

So how do you know what apps run on a given server? DroneD has a simple
``apps`` command to list the. So for example::

  server egbs01
  apps
  > tbs-shop
  > tbs-txn
  > roi-tracker
  > deals
  @roi-tracker status
  @roi-tracker add 10.4
  @roi-tracker start a

This example shows us talking about the server ``egbs01``, then listing the
apps that run on that server. Then we asked the ``roi-tracker`` AppManager
for status on its instances. Then we added a new roi-tracker instance using
roi-tracker version 10.4. Then we started instance *a* of roi-tracker.
Simple enough. Use ``@help`` to learn more.


.. note:: Currently all of this documentation is auto-generated (which is
          why it looks so ugly) from docstrings. Once the command syntax
          becomes more stable these commands should be documented manually


Core Commands
-------------
.. automodule:: droned.responders.core
   :members:


Context Commands
----------------
.. automodule:: droned.responders.context
   :members:


Application Commands
--------------------
.. automodule:: droned.responders.instance
   :members:


Deployment Commands
-------------------
.. automodule:: droned.responders.deployment
   :members:


Event Subscription Commands
---------------------------
.. automodule:: droned.responders.events
   :members:


Log Analysis Commands
---------------------
.. automodule:: droned.responders.logs
   :members:


Chat Room Commands
------------------
.. automodule:: droned.responders.chat
   :members:


Team Commands
-------------
.. automodule:: droned.responders.support
   :members:


Anomaly Commands
----------------
.. automodule:: droned.responders.anomaly
   :members:
