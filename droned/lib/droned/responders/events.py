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
from droned.models.event import Event
from droned.responders import responder, dispatch


@responder(pattern="^subscribe (?P<event>\S+)", form="subscribe <event>|all", help="Subscribe to event notifications")
def subscribe(conversation, event):
    subscriptions = set(conversation.context.get('subscriptions', set()))
    if event == 'all':
        events = Event.objects
    else:
        events = [ Event(event) ]
    for event in events:
        conversation.say("Subscribed to %s events" % event.name)
        subscriptions.add(event.name)
        event.subscribe(conversation.notify)
    conversation.context['subscriptions'] = subscriptions


@responder(pattern="^unsubscribe (?P<event>\S+)", form="unsubscribe <event>|all", help="Unsubscribe from event notifications")
def unsubscribe(conversation, event):
    subscriptions = set(conversation.context.get('subscriptions', []))
    if event == 'all':
        eventList = Event.objects
    else:
        eventList = [ Event(event) ]
    for event in eventList:
        conversation.say("Unsubscribed from %s events" % event.name)
        event.unsubscribe(conversation.notify)
        subscriptions.discard(event.name)
    conversation.context['subscriptions'] = sorted(subscriptions)


@responder(pattern=".*<b>(?P<event>\S+)</b>.*occurred \((?P<string>.*)\).*")
def notification(conversation, event, string):
    #hopefully you know how to parse this string
    if Event.exists(event):
        context = {
            'conversation': conversation,
            'message': string,
            'event': event,
        }
        Event(event).fire(**context)


@responder(pattern="<b>Announcement from .*</b> ::: (?P<string>.*)")
def annoucement(conversation, string):
    return dispatch(conversation, string)


@responder(pattern="Sorry I don't know what you mean by that.*")
def circular_conversation(conversation, *args):
    """Blackhole these circular conversations"""
    return
