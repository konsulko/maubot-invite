from typing import Type, TypedDict, List

from mautrix.types import EventType
from mautrix.client.api.events import EventMethods
from mautrix.client.api.rooms import RoomMethods
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper

from maubot import Plugin, MessageEvent
from maubot.handlers import command

class InviteGroupConfig(TypedDict):
    room_ids: str
    users: List[str]

class InviteConfig(BaseProxyConfig):
    invite_groups: List[InviteGroupConfig]
    admin_users: List[str]

    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("invite_groups")
        helper.copy("admin_users")

class InviteBot(Plugin):
    event_methods = None
    room_methods = None
    config: InviteConfig

    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()
        self.event_methods = EventMethods(api=self.client.api)
        self.room_methods = RoomMethods(api=self.client.api)

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return InviteConfig
    
    # Request invites for a given authorization token
    @command.new(name="invite", help="Request invites")
    @command.argument("token", pass_raw=True)
    async def invite_handler(self, evt: MessageEvent, token: str) -> None:
        message = ""
        invite = False
        joined_rooms = await self.room_methods.get_joined_rooms()
        for invite_group in self.config["invite_groups"]:
            # If there is an auth token then try to send an invite for each room
            if token in invite_group["auth_tokens"]:
                for room_id in invite_group["room_ids"]:
                    members = await self.event_methods.get_joined_members(room_id)
                    name_evt = await self.event_methods.get_state_event(room_id, EventType.ROOM_NAME)
                    # Send an invite if this user is not already a member
                    if evt.sender in members:
                        message += "You are already a member of " + name_evt.name + ".\n\n"
                        invite = True
                    else:
                        if room_id in joined_rooms:
                            await self.room_methods.invite_user(room_id, evt.sender)
                            message += "You have been invited to " + name_evt.name + ".\n\n"
                            invite = True
        if not invite:
            message += "No invites available.\n"

        await evt.respond(message)

    # Show current configuration to administrators
    @command.new(name="config", help="Show config")
    async def config_handler(self, evt: MessageEvent) -> None:
        if evt.sender not in self.config["admin_users"]:
            await evt.respond("Only admins can use the `!config` command.");
        else:
            message = "Admins:\n"
            for admin_user in self.config["admin_users"]:
                message += "- " + admin_user + "\n"
            message += "\nInvite groups:\n"
            joined_rooms = await self.room_methods.get_joined_rooms()
            for invite_group in self.config["invite_groups"]:
                message += "- Room IDs:\n\n"
                for room_id in invite_group["room_ids"]:
                    name_evt = await self.event_methods.get_state_event(room_id, EventType.ROOM_NAME)
                    message += "  - " + room_id + " (" + name_evt.name + ")\n"
                    if room_id not in joined_rooms:
                        message += "    - WARNING: invite bot not a member and cannot issue invites.\n"
                message += "- Auth tokens:\n\n"
                for auth_token in invite_group["auth_tokens"]:
                    message += "  - " + auth_token + "\n"
                message += "---\n"
            await evt.respond(message)
