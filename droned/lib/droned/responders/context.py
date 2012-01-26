###############################################################################
#   Copyright 2006 to the present, Orbitz Worldwide, LLC.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
###############################################################################
from droned.responders import responder


@responder(pattern="^app (?P<name>.+)", form="app <name>", auth_required=False, help="Talk about an application")
def app(conversation, name):
  if App.exists(name):
    conversation.context['app'] = App(name)
    conversation.context['subject'] = App(name)
    conversation.say("Ok, we're talking about %s" % name)
  else:
    msg = "Sorry, I've never heard of the app \"%s\"." % name
    conversation.say(msg)


@responder(pattern="^server (?P<hostname>.+)", form="server <name>", auth_required=False, help="Talk about a server")
def server(conversation, hostname):
  server = Server.byName(hostname)
  if server:
    conversation.context['server'] = server
    conversation.context['subject'] = server
    conversation.say("Ok, we're talking about %s" % hostname)
    if server.unreachable:
      stacktrace = server.connectFailure.getTraceback()
      msg = "By the way, %s is unreachable because of the following connection failure\n%s" % (hostname,stacktrace)
      conversation.say(msg, useHTML=False)
  else:
    msg = "Sorry, I've never heard of the server \"%s\"." % hostname
    conversation.say(msg)


@responder(pattern='^instance (?P<label>.+)$', form='instance [label]', auth_required=False,
 help='Talk about an instance (assumes server & app)')
def instance(conversation, label):
  context = conversation.context
  if 'app' not in context or 'server' not in context:
    conversation.say("You have to tell me what <b>app</b> and <b>server</b> you're talking about first.")
    return
  app = context['app']
  server = context['server']
  instances = [ai for ai in server.appinstances if ai.app is app and ai.label == label]
  if instances:
    context['instance'] = instances[0]
    conversation.say("Ok, we're talking about %s" % instances[0].description, useHTML=False)
  else:
    conversation.say("There is no '%s' instance of %s on %s." % (label, app.name, server.hostname))


@responder(pattern="^status", context_key='subject', form="status", auth_required=False,
 help="Display instance status for the current app/server")
def status(conversation):
  subject = conversation.context.get('subject')
  if isinstance(subject, Server) and subject.unreachable:
    status = "%s is unreachable: %s\n" % (subject.hostname, subject.connectFailure.value)
    conversation.say(status, useHTML=False)
    return
  status = ""
  for i in subject.appinstances:
    status += "%s-%s[%s] on %s" % (i.app.name, i.version, i.label, i.server.hostname)
    if i.running:
      cpu = str(i.cpu)
      if cpu is None: cpu = '?'
      threads = str(i.threads)
      if threads is None: threads = '?'
      memory = str(int(i.memory / 1024 /1024)) + 'MB'
      status += "\tcpu=%s threads=%s memory=%s\n" % (cpu,threads,memory)
    elif i.crashed:
      status += "\t(crashed)\n"
    else:
      status += "\t(not running)\n"
  if status:
    status = '\n' + status #makes output look better
  else:
    status = "No instances configured"
  conversation.say(status, useHTML=False)


@responder(pattern="^poll$", context_key='server', form='poll', help='Fetch latest info about the current server')
def poll(conversation):
  server = conversation.context['server']
  conversation.say("polling %s" % server.hostname)
  conversation.context['deferreds'] = [server.droned.poll()]


@responder(pattern="^apps( (?P<mods>.+))?$",
 form='apps [+|-app]+', help='List/modify apps that should run on the current server')
def apps(conversation, mods):
  if 'server' not in conversation.context:
    all = [app.name for app in App.objects]
    conversation.say('Here are all the applications I know about.\n' + '\n'.join(all), useHTML=False)
    return

  server = conversation.context['server']
  apps = sorted(app.name for app in server.apps)
  if mods:
    for mod in mods.split():
      name = mod[1:]
      app = App.exists(name) and App(name)
      if not app:
        return conversation.say("Unknown app \"%s\"" % name)
      if mod.startswith('+'):
        app.runsOn(server)
      elif mod.startswith('-'):
        app.doesNotRunOn(server)
      else:
        return conversation.say("Invalid syntax.")
    conversation.say("Ok.")
  else:
    if apps:
      conversation.say('\n' + '\n'.join(apps), useHTML=False)
    else:
      conversation.say("%s has no matching applications" % server.hostname)


@responder(pattern="^servers( (?P<mods>.+))?$",
 form='servers [+|-hostname]*', help='List/modify servers that should run the current app')
def servers(conversation, mods):
  if 'app' not in conversation.context:
    all = [server.hostname for server in Server.objects]
    conversation.say('Here are all the servers I know about.\n' + '\n'.join(all), useHTML=False)
    return

  app = conversation.context['app']
  servers = sorted(server.hostname for server in app.shouldRunOn)
  if mods:
    for mod in mods.split():
      hostname = mod[1:]
      server = Server.byName(hostname)
      if not server:
        conversation.say("Unknown server \"%s\"" % hostname)
        return
      if mod.startswith('+'):
        app.runsOn(server)
      elif mod.startswith('-'):
        app.doesNotRunOn(server)
      else:
        conversation.say("Invalid syntax.")
        return
    conversation.say("Ok.")
  else:
    if servers:
      m = 'Here are all of the servers that run %s.\n' % (app.name,) 
      conversation.say(m + '\n'.join(servers), useHTML=False)
    else:
      conversation.say("%s has no matching servers" % (app.name,))


@responder(pattern='^(nevermind|nm|meh|bah)', form='nevermind', help='Forget the current question (aliases: nm,meh,bah)')
def nevermind(conversation):
  conversation.nevermind()
  conversation.say("Ok.")


# Avoid import circularities
from droned.models.app import App
from droned.models.server import Server
