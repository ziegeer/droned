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
from droned.models.conversation import ChatRoom
from droned.responders import responder


@responder(pattern="joinchat (?P<room>\S+)", form="joinchat <room>", help="Tell droned to join a chat room")
def joinchat(conversation, room):
  conversation.say("Ok, I will join the %s chat room." % room)
  chat = ChatRoom(room)
  chat.join()


@responder(pattern="leavechat( (?P<room>\S+))?", form="leavechat [room]", help="Tell droned to leave a chat room")
def leavechat(conversation, room):
  if room is None:
    room = conversation.buddy.split('@')[0]
    if not ChatRoom.exists(room):
      conversation.say("This isn't a chat room.")
      return
  if ChatRoom.exists(room):
    conversation.say("Ok, I will leave the %s chat room." % room)
    chat = ChatRoom(room)
    chat.leave()
  else:
    conversation.say("I'm not in the \"%s\" chat room." % room)
