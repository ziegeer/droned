*************
Prerequisites
*************

.. _Python: http://www.python.org/
.. _Twisted: http://www.twistedmatrix.com/
.. _ZopeInterface: http://www.zope.org/Products/ZopeInterface/
.. _PyOpenSSL: http://pyopenssl.sourceforge.net/
.. _Sphinx: http://sphinx.pocoo.org/

The following pieces of software should be installed in the order they are
listed in.


Python 2.4
==========
DroneD was developed to run on Python 2.4. It should work perfectly
fine with Python 2.7 though as of this writing that has not been extensively 
tested. It is important to remember that all of the python libraries that droned
uses must be installed specifically for the version of Python that you intend
to run droned on. A common mistake when installing python modules is to
simply run ``python setup.py install``, which installs the module on the
system's default version of python which may not be 2.4. To be safe, you
should instead use the following command where appropriate
``python2.4 setup.py install``.


zope-interface
==============
This package is required by the Twisted framework. The latest packages can be
found on the ZopeInterface_ project page.

	http://www.zope.org/Products/ZopeInterface/3.3.0/zope.interface-3.3.0.tar.gz


PyOpenSSL
=========
This package is required by Twisted (Words) for SSL support (necessary for
jabber connectivity). The latest packages can be found on the PyOpenSSL_
project page.

	http://downloads.sourceforge.net/pyopenssl/pyOpenSSL-0.8.tar.gz


Twisted
=======
Twisted_ is high performance network application framework that droned
uses heavily. Unfortunately the authors tend to change the APIs fairly
frequently so it is entirely possible that using the latest version of
Twisted will not work without updating droned's code. At the time of
this writing the current version of twisted is 8.1, which can be retrieved
here:

	http://tmrc.mit.edu/mirror/twisted/Twisted/8.1/Twisted-8.1.0.tar.bz2

That is the core twisted package, however droned uses some experimental
features of twisted that must be installed through a separate package called
Twisted-Web2_.

	http://tmrc.mit.edu/mirror/twisted/Web2/8.1/TwistedWeb2-8.1.0.tar.bz2


Sphinx
======
Sphinx_ is used to generate DroneD's documentation. While not strictly
necessary to run DroneD, it is necessary to build DroneD's
documentation. Since the documentation is served up via DroneD's built-in
webapp, this can be very useful and is probably a good idea.

Unfortunately the bastards who make Sphinx do not publish release packages
directly, instead they use the *Easy Install* system. This should be available
on most modern Linux distributions by default. To install Sphinx, simply run
``easy_install -U Sphinx``. Also if you feel like it run
``easy_install -U Pygments`` to get syntax highlighting in the code samples.
