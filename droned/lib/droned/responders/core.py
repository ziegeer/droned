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
import re, traceback
from twisted.python.failure import Failure
from twisted.internet import defer
from droned.errors import DroneCommandFailed
from droned.responders import responder, responders, jabber_config
import config


@responder(pattern="^(\?|help) ?(?P<regex>\S+)?", form="? [regex]", auth_required=False,
 help="Display help, optionally filtered")
def help(conversation, regex):
    help_text = ""
    groups = {}
    for func in responders.values():
        if func.module not in groups:
            groups[func.module] = []
        groups[func.module].append(func)
    for group,funcs in sorted(groups.items()):
        help_text += "\n<<< %s commands >>>\n" % group
        for func in funcs:
            help_text += "%24s  %s\n" % (func.form, func.help)

    if regex:
        regex = re.compile(regex)
        output = ""
        for line in help_text.split('\n'):
            if regex.search(line):
                output += line + '\n'
    else:
        output = help_text

    conversation.say('\n' + output, useHTML=False)

    if not regex:
        doc_url = "http://%s:%d/doc/index.html" % (config.HOSTNAME, config.DRONED_PORT)
        conversation.say("For more information read my online documentation at %s" % doc_url)


@responder(pattern="^!(?P<source>.+)", form="!<code>", help="Execute some python code")
def python(conversation, source):
    from droned.entity import namespace
    source = source.strip()
    try:
        code = compile(source, '<jabber>', 'eval')
    except:
        try:
            code = compile(source, '<jabber>', 'single')
        except:
            msg = "I couldn't compile your code.\n%s" % traceback.format_exc()
            conversation.say(msg, useHTML=False)
            return
    try:
        result = eval(code, namespace)
    except:
        result = traceback.format_exc()
    conversation.say(str(result), useHTML=False)


@responder(pattern="^@(?P<command>.+)", context_key='server', form="@<command>", help="Run a droned command on the current server")
@defer.deferredGenerator
def droneblast(conversation, command):
    server = conversation.context.get('server')
    response = None
    d = None
    try:
        if not isinstance(server, Server):
            conversation.say('On what <b>server</b>?')
            raise AssertionError('incomplete converation context')

        options = {}
        if 'timeout' in conversation.context:
            options['timeout'] = conversation.context['timeout']

        try:
            conversation.say("Running droned command...")
            d = server.manager.run(command, **options)
            deferreds = conversation.context.get('deferreds', [])
            deferreds.append(d)
            conversation.context.update({'deferreds': deferreds})
            wfd = defer.waitForDeferred(d)
            yield wfd
            result = wfd.getResult()
        except:
            failure = Failure()
            if failure.check(DroneCommandFailed):
                rc = failure.value.resultContext
                conversation.say(rc.get('description') or str(rc), useHTML=False)
            else:
                conversation.say(failure.getTraceback(), useHTML=False)
        else:
            if isinstance(result, dict):
                output = result.values()[0].get('description', str(result))
            else:
                output = str(result)
            deferreds = conversation.context.get('deferreds', [])
            try: deferreds.remove(d)
            except: pass
            conversation.context.update({'deferreds': deferreds})
            conversation.say("Command completed\n%s" % output, useHTML=False)
    except AssertionError: pass
    except:
        result = Failure()
    yield result


@responder(pattern="^set (?P<var>\S+) (?P<value>.+)", form="set <var> <value>", help="Define a context variable")
def _set(conversation, var, value):
    try:
        value = float(value)
    except:
        try:
            value = int(value)
        except: pass
    conversation.context[var] = value
    conversation.say("Ok.")


@responder(pattern="^unset (?P<var>\S+)", form="unset <var>", help="Delete a context variable")
def unset(conversation, var):
    if var in conversation.context:
        del conversation.context[var]
    conversation.say("Ok.")


@responder(pattern="^wtf", form="wtf", auth_required=False, help="Display the current context variables")
def wtf(conversation):
    msg = ""
    for key,value in sorted( conversation.context.items() ):
        if key in ('conversation',): continue
        msg += "%s: %s\n" % (key, value)
    conversation.say(msg, useHTML=False)


@responder(pattern="^clear$", form="clear", help="Hackishly clear the chat window")
def clear(conversation):
    conversation.say('\n' * 30, useHTML=False)


@responder(pattern="^tasks$", form='tasks', help="Display tasks droned is performing for you")
def tasks(conversation):
    deferreds = conversation.context.get('deferreds',[])
    if deferreds:
        listing = '\n' + '\n'.join("#%d %s" % i for i in enumerate(deferreds))
        conversation.say(listing, useHTML=False)
    else:
        conversation.say("I'm not executing any tasks for you right now.")


@responder(pattern="^failed( (?P<num>\d+))?$", form='failed [num]',
 help="Display one or all failed tasks droned just performed for you")
def failed(conversation, num):
    failures = conversation.context.get('failures',[])

    droned_results = [f.value.resultContext for f in failures if f.check(DroneCommandFailed)]
    other_failures = [f for f in failures if not f.check(DroneCommandFailed)]

    if num: # Detailed error report
        droned_errors = [str(rc) for rc in droned_results]
        other_errors = [f.getTraceback() for f in other_failures]
        errors = droned_errors + other_errors

        num = int(num)
        try:
            conversation.say('\n' + errors[num], useHTML=False)
        except:
            conversation.say('No failure #%d' % num)
    elif failures: # Error summary listing
        droned_errors = ['%(server)s: %(description)s' % rc for rc in droned_results]
        other_errors = [str(f) for f in other_failures]
        errors = droned_errors + other_errors

        listing = '\n' + '\n'.join("#%d %s" % i for i in enumerate(errors))
        conversation.say(listing, useHTML=False)
    else:
        conversation.say("I have not failed to do anything for you recently.")


@responder(pattern='^pollall\s*', form='pollall', help='Poll every server as quickly as possible')
def pollall(conversation):
    count = 0
    for server in Server.objects:
        server.droned.poll()
        count += 1
    conversation.say("Polling %d servers..." % count)


@responder(pattern='^auth request$', form='auth request', auth_required=False,
 help='Request authorization from environment administrator')
@defer.deferredGenerator
def auth_request(conversation):
    result = None
    try:
        if conversation.authorized:
            conversation.say("You are already authorized to use this droned.")
            raise AssertionError('Already authorized to use this droned')

        conversation.say("Ok, I will pass your request along to the environment administrator. I will let you know what they decide.")
        deputy = Conversation(jabber_config.DEPUTY)
        try:
            question = "%s has requested authorization, do you wish to <b>grant</b> or <b>deny</b> this request?" % conversation.buddy
            answers = ('grant','deny')
            d = deputy.ask(question, answers)
            wfd = defer.waitForDeferred(d)
            yield wfd
            answer = wfd.getResult()
        except AlreadyAskingQuestion:
            err = "Sorry, the environment administrator is busy dealing with something else right now. "
            err += "You should wait and try again later, or if it is urgent contact them directly. "
            err += "The environment administrator is %s" % jabber_config.DEPUTY
            conversation.say(err)
            raise AssertionError('Administrator is busy')

        if answer == 'grant':
            conversation.grantAuthorization()
            deputy.say("%s has been granted authorization." % conversation.buddy)
        else:
            err = "Your request for authorization has been denied. If you wish to discuss this further you "
            err += "should contact the environment administrator directly. "
            err += "The environment administrator is %s" % jabber_config.DEPUTY
            conversation.say(err)
            deputy.say("%s has been denied authorization." % conversation.buddy)
    except AssertionError: pass
    except:
        result = Failure()
    yield result


@responder(pattern='^revoke (?P<user>.+)$', form='revoke <user>', help='Revoke authorization for a user (admin only)')
def revoke(conversation, user):
    if conversation.buddy != jabber_config.DEPUTY:
        conversation.say("Sorry, this command is only available to the environment administrator (%s)." % jabber_config.DEPUTY)
        return

    naughtyUser = Conversation.byName(user)
    if naughtyUser:
        conversation.say("Ok, I am revoking authorization for %s." % naughtyUser.buddy)
        naughtyUser.revokeAuthorization()
    else:
        conversation.say("There is no user by that name.")


@responder(pattern='^who$', form='who', help='List users that have talked to droned in the past hour')
def who(conversation):
    listing = []

    for user in Conversation.objects:
        minutes = int(user.idleTime) / 60
        if minutes > 60:
            continue
        elif minutes > 0:
            plural = (minutes > 1 and 's') or ''
            listing.append("%-20s %d minute%s ago" % (user.buddyName, minutes, plural))
        else:
            listing.append("%-20s less than a minute ago" % user.buddyName)

    heading = "The following users have talked to me in the last hour.\n"
    heading += "%-20s last active\n" % 'username'
    conversation.say(heading + '\n'.join(listing), useHTML=False)


@responder(pattern='^repeat', form='repeat', auth_required=False, help='Tell droned to repeat the last question')
def repeat(conversation):
    if conversation.askingQuestion:
        conversation.say( conversation.context['question'] )
        conversation.say("Acceptable answers are: %s" % ', '.join(conversation.expectedAnswers))
    else:
        conversation.say("I have no open questions for you.")


#Avoid import circularities
from droned.models.server import Server
from droned.models.conversation import Conversation, AlreadyAskingQuestion
