import logging
import random
import uuid
import json
import os

import discord

OMAEWAMOUSHINDEIRU = [
    "おまえはもうしんでいる",
    "おまえはもう死んでいる",
    "お前はもうしんでいる",
    "お前はもう死んでいる"
]

NANI = [
    "**なに？！**",
    "**何？！**"
]

BESTGIRL = [
    "best girl dyphan",
    "best girl dyphanbot",
    "dyphan is best girl",
    "dyphanbot is best girl"
]

dbot = None

class TestPlugin(object):
    """docstring for TestPlugin."""
    def __init__(self, dyphanbot):
        self.dyphanbot = dyphanbot
        self.ai_session_id = None
        self.ai_project_id = "dyphanai" # TODO: move to config

    async def test(self, client, message, args):
        if 'self' in args:
            await message.channel.send(self.dyphanbot.bot_mention(message) + " test")
        else:
            await message.channel.send("Tested!!")

    async def anime(self, client, message=None, args=None):
        # TODO: Make this run automatically instead of on command.
        # TODO: Maybe randomly choose from a list of anime to watch from as an easter egg?
        activity = discord.Activity(
            name="anime",
            state="Watching an anime episode",
            details="It's a very exciting anime!",
            type=discord.ActivityType.watching
        )
        await client.change_presence(activity=activity, status=discord.Status.dnd)
        if message:
            await message.channel.send("Imma watch some anime... ~~brb~~ but I'll still be here. I can multitask... literally.")

    async def ai(self, client, message):
        #text = " ".join(args)
        text = message.content
        if not self.ai_session_id:
            self.ai_session_id = str(uuid.uuid4())

        async with message.channel.typing():
            import dialogflow_v2 as dialogflow
            session_client = dialogflow.SessionsClient()

            session = session_client.session_path(self.ai_project_id, self.ai_session_id)
            print('Session path: {}\n'.format(session))
            text_input = dialogflow.types.TextInput(
                text=text,
                language_code="en-US"
            )

            query_input = dialogflow.types.QueryInput(text=text_input)
            response = session_client.detect_intent(
                session=session,
                query_input=query_input
            )
            print('Query text: {}'.format(response.query_result.query_text))
            print('Detected intent: {} (confidence: {})\n'.format(
                response.query_result.intent.display_name,
                response.query_result.intent_detection_confidence
            ))
            print('Fulfillment text: {}\n'.format(response.query_result.fulfillment_text))
            await message.channel.send("{}".format(response.query_result.fulfillment_text))


    async def handle_message(self, client, message):
        if "Dyphan" in message.content:
            await message.channel.send("sup bitch")
        elif any(omaeshin in message.content for omaeshin in OMAEWAMOUSHINDEIRU):
            await message.channel.send(random.choice(NANI))

    async def handle_raw_message(self, client, message):
        if "Dyphan likes it raw" in message.content:
            await message.channel.send("I LIKE IT RAWW!!!!")
        elif any(bgrill in message.content.lower() for bgrill in BESTGIRL):
            await message.channel.send(":heart:")

def plugin_init(dyphanbot):
    testplugin = TestPlugin(dyphanbot)
    dyphanbot.add_ready_handler(testplugin.anime)

    dyphanbot.add_command_handler("test", testplugin.test)
    dyphanbot.add_command_handler("anime", testplugin.anime)
    dyphanbot.add_command_handler("/unknown_cmd/", testplugin.ai)
    dyphanbot.add_message_handler(testplugin.handle_message)
    dyphanbot.add_message_handler(testplugin.handle_raw_message, raw=True)
