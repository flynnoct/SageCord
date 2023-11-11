import io
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

    # DM Message, ignore for now FIXME
    if isinstance(message.channel, discord.channel.DMChannel):
        return
    
    # FIXME: temp patch
    if message.channel.id == 1172458968849862737:
        return
    # Parse attachments
    user_attachments = []
    if message.attachments:
        for attachment in message.attachments:
            user_attachments.append(await attachment.read())

    response_messages = message_processor.get_response(
        content = message.content, 
        attachments = user_attachments,
        context_id = message.channel.id)
    for response_message in response_messages:
        for content in response_message:
            # if it's a text message
            if content["type"] == "text":
                text_value = content["text_value"]
                discord_files = []
                placeholder_texts = []
                # file paths
                annotations = content["annotations"]["file_path"]
                for annotation in annotations:
                    discord_files.append(
                        discord.File(
                            fp = io.BytesIO(annotation["file_content"]), 
                            filename = annotation["file_name"]
                            )
                        )
                    placeholder_texts.append(annotation["placeholder_text"])
                # file citations
                annotations = content["annotations"]["file_citation"]
                for annotation in annotations:
                    pass
                if len(discord_files) == 0: # no files
                    await message.reply(text_value)
                else: # with files
                    discord_files = discord_files[:10] # file limit
                    placeholder_texts = placeholder_texts[:10]
                    sent_message = await message.reply(text_value, files = discord_files)
                    for i in range(len(sent_message.attachments)):
                        attachment = sent_message.attachments[i]
                        placeholder_text = placeholder_texts[i]
                        attachment_url = attachment.url
                        text_value = text_value.replace(placeholder_text, attachment_url)
                    await sent_message.edit(content = text_value)

            # elif it is an image
            elif content["type"] == "image_file":
                await message.reply(
                    file = discord.File(
                        fp = io.BytesIO(content["file_content"]), 
                        filename = content["file_name"]
                        )
                    )
            else:
                raise Exception("Unknown message type")



# handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

client.run(
    CL.get("discord", "bot_token"), 
    # log_handler=handler, 
    root_logger=True, 
    log_level=logging.DEBUG # Add options to handle log_level 
    )
