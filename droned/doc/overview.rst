######################
Overview of DroneD
######################

What is DroneD?
*******************
There are many different ways to answer this question, but perhaps the most
useful way to think of droned is as a *programmable model of our software environment*. 
This begs the question, what exactly is a "programmable model"? Even further, 
what do I mean by "a model of our software environment?"

Defining the environment
=========================
What exactly do we mean when we talk about an *environment*? In the context
of droned an environment is defined to be the following at minimum:
* servers & artifacts (aka software)

That's it you ask? I know in my environment its much more complicated than
that! And you'd be right. In the real world there are very few cases where
you'd only need to know that some piece of software, say jboss, runs on 
server webapp01.mycompany.com. In the real world you care about things like:
* server OS details
* software versions
* software configuration
* server and software groups within an environment. 
	* Compute clusters
	* Customer or region specific groups
* ....and the list goes on.

In the droned world these nuances are captured as properties of your server 
or artifact. And in fact new *top* level elements can be defined as well.
But we're getting ahead of ourselves and we'll come back to some of these 
details a bit later. Lets see a very basic conceptual example of how these
relations are defined.

image:: admin/diagrams/png/prelim_concepts1.png

This contrived environment consists of a few key elements. First off  we
have 6 servers. Four are some type of application server. Two are database
servers. We also have an *application group* defined which includes servers
2,4 and 6. Droned allows us to define answers to all of these questions. 
* What servers exist?
* What software does each server run?
* Is there more than one instance of a given applicationEach application?
* Are there any relations between multiple servers or applications?
* What are the necessary resources for my applications?	

In this respect droned seems very similar to other solutions such as
`cfengine <http://cfengine.com/>`, `puppet <http://puppetlabs.com/>` and `chef <http://wiki.opscode.com/display/chef/Home>`. 
True there are some basic similarities but as we shall see the differences
between these tools is significant enough that they act complimentary to 
each other rather than one displacing the other.

The Programmable Model
======================
So how is droned's model *programmable*? Essentially, droned does not
*do* anything on its own. We typically *tell it* what to do to our environment
**in terms of its environment model**. "Hey droned, start apache on server
XYZ." can be translated to some very simple Python code that tells droned
precisely what actions to take. This is a very useful abstraction, and
it allows us to manipulate our environment in high-level terms rather than
depending on an expert who knows all the requisite details of implementing
such a change manually. Ultimately this makes automation easier, more powerful,
and more maintainable.


Why the silly name?
===================
There really is no great reason. I like to think of it the way I think of
names I've made for other pieces of software. It is one part intuitive,
one part technically accurate, and one part utter nonsense.


What is DroneD?
***************
* It is a daemon
* It regularly scans its *universe* (local processes and files and 
  optionally other droned's)
* It maintains a structured **descriptive model** of its *universe*
* It uses a structured **prescriptive model** that defines what its
  *universe* **should** look like
* It provides simple open interfaces for reading its *descriptive model*
  and manipulating its *prescriptive model*


How do we use DroneD?
*********************
While a number of interfaces exist or could be added on to droned, the
primary means of telling droned what to do is via Jabber. Initially
this may seem like a somewhat arbitrary choice, perhaps because it "sounds
cool" but the choice was really quite intentional and has proven to be
extremely functional. The primary reasons behind using Jabber as a user
interface are as follows:

* It is an established communication standard at Orbitz
* It is real-time
* It is bi-directional and thus allows for interactive use
* It supports both targetted and group messaging
* It is an open standard and thus allows for interoperation with other tools
