*************
Preliminaries
*************


DroneD In Git
========================
You can check out the latest droned git like so::



Bug Tracking
============
Use github's bug tracking facility.


Style Guidelines
================
Basically just follow these simple rules and you should be OK:

* Use 4-space indentation
* Use *very* descriptive variable names
* Follow all terminology / naming conventions *very* strictly


The Twisted Paradigm
====================
Twisted is very awkward for most people at the beginning, but once you wrap
your brain around it you will be well rewarded with an excellent development
framework. Not only is it worth while to do this on your own, it is absolutely
necessary to understand the Twisted paradigm to understand how droned
works. In addition to the
`standard twisted docs <http://twistedmatrix.com/projects/core/documentation/howto/index.html>`_
I have written two short tutorials below to try and clarify some of the
concepts that are often confusing at first. It is important to remember that
despite the fact that Twisted is very different from "standard" programming
practices, it is ultimately very very simple and powerful.

.. toctree::
   :maxdepth: 1

   twisted/reactor
   twisted/deferreds


Code Profiling
==============
This has been removed, but will be re-added at a later time.

DroneD has a ``--profile`` command-line option that enables the built-in
python profiler module for the duration of droned's execution (so don't
run it like this for days on end or you'll run out of memory/disk). The profile
data is stored in the top-level droned directory in a file called
``profile``. This file can be inspected and reported on using the standard
python profiling techniques described here:

http://docs.python.org/library/profile.html#pstats.Stats

One caveat is that if you have the ``DEBUG_DEFERREDS`` config option enabled
then you will see a lot of time eaten up by the ``traceback`` module. This
is because Twisted uses this module internally for the deferred debugging
functionality. So you should probably set ``DEBUG_DEFERREDS = False``
when running droned in profiling mode.
