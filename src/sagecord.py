import discord
import logging
from config_loader import ConfigLoader as CL
from message_processor import MessageProcessor

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

message_processor = MessageProcessor()

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user: # Prevents bot from responding to itself
        return

    # if message.content.startswith('$hello'):
    #     await message.channel.send('Hello!')
    print(message)
    print(type(message.content), message.content)

    # DM Message
    if isinstance(message.channel, discord.channel.DMChannel):
        response = message_processor.get_response(content = message.content, context_id = message.channel.id)
        await message.reply(response)

# handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

client.run(
    CL.get("discord", "bot_token"), 
    # log_handler=handler, 
    root_logger=True, 
    log_level=logging.DEBUG # Add options to handle log_level 
    )
