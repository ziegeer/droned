***********************
Post-Installation Tasks
***********************

These are the necessary steps you must take after installing droned
but before using it.


Setup DroneD Keys
=================
In addition to SSH keys, every environment has a unique RSA key pair called
the droned *master key* that must be installed for droned to be able to
manage droned agents in the environment. Typically this key will be generated
by hand on the server you run droned on (ie. a promo server). The
``master.private`` file must be installed on the promo server and the
corresponding ``master.public`` file must be installed on all of the
application servers in the environment (everywhere droned runs).

The files both go in the same place, ``/etc/pki/droned/``

	/usr/bin/droned-genkeys master

This will create both the ``master.private`` and ``master.public`` files.
You need to then copy the ``master.public`` file to the same directory out
on every server in the environment. The ``master.private`` file only needs
to be on the promo server. After installing these files it will be necessary
to restart any applications that use them (ie. droned or droned).

To test that this is installed properly you should create a file called
``servers`` that contains the hostnames of all servers in the environment
(newline delimited) and run the following command::

	/usr/bin/droneblaster -f servers -k master -t 5 ping

There will be a line of output for every server listed in the ``servers``
file. Any server that responds with a "PONG" is working properly. Any
server that responds with "Connection Refused" probably does not have
a running droned agent. Any server that responds with a timeout error or
a "ValueError" or basically anything else means that the keys are not
installed properly. When in doubt, generate a new key pair and redeploy
it to the entire environment.
