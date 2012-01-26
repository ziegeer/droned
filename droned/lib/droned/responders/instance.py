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
from twisted.internet import defer 
from twisted.python.failure import Failure
from droned.models.app import App, AppInstance
from droned.models.conversation import AlreadyAskingQuestion
from droned.responders import responder


@responder(pattern="^start (?P<apps>.+)", form="start <apps>", help="Start comma-separated list of apps (or \"all\")")
def start(conversation, apps):
    performAction(conversation, apps, 'start', lambda i: not i.running)


@responder(pattern="^stop (?P<apps>.+)", form="stop <apps>", help="Stop comma-separated list of apps (or \"all\")")
def stop(conversation, apps):
    performAction(conversation, apps, 'stop', lambda i: i.running)


@responder(pattern="^restart (?P<apps>.+)", form="restart <apps>", help="Restart comma-separated list of apps (or \"all\")")
def restart(conversation, apps):
    performAction(conversation, apps, 'restart', lambda i: i.running)


@defer.deferredGenerator
def performAction(conversation, apps, action, instanceFilter):
    result = None
    try:
        # Resolve the list of app names
        if apps == 'all':
            apps = set(app for app in App.objects if app.shouldRunOn)
            names = "" #used in question below
        else:
            givenNames = [name.strip() for name in apps.split(',')]
            apps = set()
            names = ', '.join(givenNames)
            for name in givenNames:
                if App.exists(name):
                    apps.add( App(name) )
                else:
                    conversation.say("Sorry, I've never heard of the %s application" % name)
                    raise AssertionError('Unknown Application')

        instances = [i for i in AppInstance.objects if i.app in apps if instanceFilter(i)]

        if not instances:
            conversation.say("There are no instances to %s." % action)
            raise AssertionError('No known instances')

        count = len(instances)
        question = 'Are you sure you want to %s all %d %s instances, <b>yes</b> or <b>no</b>?' % (action, count, names)
        answers = ('yes','no')
        try:
            d = conversation.ask(question, answers)
            wfd = defer.waitForDeferred(d)
            yield wfd
            response = wfd.getResult()
        except AlreadyAskingQuestion:
            conversation.say("This command requires confirmation but I have already asked you another question. "
                    "Please answer that question first or tell me to <b>nevermind</b> it then try again.")
            raise AssertionError('already, busy asking question')

        if response == 'yes':
            #we also need to trap StopIteration(Exception) due to generators
            action_list = [ getattr(i, action)().addErrback(lambda x: \
                    x.trap(StopIteration) or x) for i in instances ]

            d = defer.DeferredList(action_list, consumeErrors=True)
            wfd = defer.waitForDeferred(d)
            yield wfd
            results = wfd.getResult()
            failures = [outcome for (successful,outcome) in results if not successful]
            conversation.context['failures'] = failures
            conversation.say("%s operations complete. %d instances failed to %s." % (action.capitalize(),len(failures),action))
        else:
            conversation.say("Ok, I will not restart anything.")
    except AssertionError: pass
    except:
        result = Failure()
    yield result
