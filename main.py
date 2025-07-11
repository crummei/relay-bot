import os
import json
import discord
from discord.ext import commands
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="<", intents=intents)

# Helper functions for config
def loadConfig():
    try:
        with open("config.json", "r") as f:
            content = f.read().strip()
            if not content:
                # Empty file: initialize default config
                return {"relayChannels": {}}
            logging.info(f"Loading config...")
            return json.loads(content)
    except FileNotFoundError:
        # File doesn't exist: create default config file and return default config
        defaultConfig = {"relayChannels": {}}
        with open("config.json", "w") as f:
            json.dump(defaultConfig, f, indent=2)
        return defaultConfig
    except json.JSONDecodeError:
        # JSON invalid: either fix file manually or reset here
        print("Warning: config.json is invalid JSON. Resetting to default.")
        defaultConfig = {"relayChannels": {}}
        with open("config.json", "w") as f:
            json.dump(defaultConfig, f, indent=2)
        return defaultConfig

def getRelayChannels():
    config = loadConfig()
    logging.info(f"Getting relay channels...")
    return config.get("relayChannels", {})

def updateRelayChannels(sourceId, destId):
    config = loadConfig()
    relay = config.get("relayChannels", {})
    relay.setdefault(sourceId, []).append(destId)
    config["relayChannels"] = relay
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)
    logging.info(f"Added {destId} to {sourceId}.")

def removeRelayEntry(sourceId, destId=None):
    config = loadConfig()
    relayChannels = config.get("relayChannels", {})

    if sourceId not in relayChannels:
        return False

    if destId is None:
        del relayChannels[sourceId]
        logging.info(f"Removed {sourceId} from sources.")
    else:
        if destId in relayChannels[sourceId]:
            relayChannels[sourceId].remove(destId)
            logging.info(f"Removed {destId} from source: {sourceId}.")
            if not relayChannels[sourceId]:
                del relayChannels[sourceId]
                logging.info(f"Source {sourceId} is now empty. Deleting source...")
        else:
            return False

    config["relayChannels"] = relayChannels
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)
    return True

# Main bot code
@bot.event
async def on_ready():
    logging.info(f'Bot: {bot.user} is ready\n-------------\n')

@bot.command()
@commands.has_permissions(administrator=True)
async def add(ctx):
    def check_channel(m):
        return m.author == ctx.author and m.channel == ctx.channel

    await ctx.send("Please mention the **source** channel (e.g. #general) or type channel ID:")

    try:
        sourceMsg = await bot.wait_for("message", check=check_channel, timeout=60)
        sourceChannel = None

        if sourceMsg.channel_mentions:
            sourceChannel = sourceMsg.channel_mentions[0]
        else:
            sourceChannel = bot.get_channel(int(sourceMsg.content.strip()))

        if sourceChannel is None:
            await ctx.send("Invalid source channel. Command cancelled.")
            return

        await ctx.send("Now please mention the **destination** channel or type channel ID:")

        destMsg = await bot.wait_for("message", check=check_channel, timeout=60)
        destChannel = None

        if destMsg.channel_mentions:
            destChannel = destMsg.channel_mentions[0]
        else:
            destChannel = bot.get_channel(int(destMsg.content.strip()))

        if destChannel is None:
            await ctx.send("Invalid destination channel. Command cancelled.")
            return

        sourceID = str(sourceChannel.id)
        destID = destChannel.id
        updateRelayChannels(sourceID, destID)

        await ctx.send(f"Relay added: messages from {sourceChannel.mention} will be sent to {destChannel.mention}")

    except Exception as e:
        await ctx.send("Timed out or error occurred, command cancelled.")
        logging.warning(e)

@bot.command()
@commands.has_permissions(administrator=True)
async def remove(ctx):
    def check_channel(m):
        return m.author == ctx.author and m.channel == ctx.channel

    await ctx.send("Please mention the **source** channel you wish to modify (e.g. #general) or type channel ID:")

    try:
        sourceMsg = await bot.wait_for("message", check=check_channel, timeout=60)
        sourceChannel = None

        if sourceMsg.channel_mentions:
            sourceChannel = sourceMsg.channel_mentions[0]
        else:
            sourceChannel = bot.get_channel(int(sourceMsg.content.strip()))

        if sourceChannel is None:
            await ctx.send("Invalid source channel. Command cancelled.")
            return

        sourceID = str(sourceChannel.id)

        await ctx.send("Type `all` to remove the entire source relay, or mention a **destination** channel to remove:")

        destMsg = await bot.wait_for("message", check=check_channel, timeout=60)

        if destMsg.content.lower() == "all":
            success = removeRelayEntry(sourceID)
            if success:
                await ctx.send(f"Removed all relays from source channel {sourceChannel.mention}.")
            else:
                await ctx.send("No relays found for that source channel.")
            return

        destChannel = None
        if destMsg.channel_mentions:
            destChannel = destMsg.channel_mentions[0]
        else:
            try:
                destChannel = bot.get_channel(int(destMsg.content.strip()))
            except ValueError:
                await ctx.send("Invalid destination channel ID. Command cancelled.")
                return

        if destChannel is None:
            await ctx.send("Invalid destination channel. Command cancelled.")
            return

        destID = destChannel.id

        success = removeRelayEntry(sourceID, destID)
        if success:
            await ctx.send(f"Removed relay from {sourceChannel.mention} to {destChannel.mention}.")
        else:
            await ctx.send("That relay was not found.")

    except Exception as e:
        await ctx.send("Timed out or error occurred, command cancelled.")
        logging.warning(e)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    relayChannels = getRelayChannels()
    messageChannelID = str(message.channel.id)
    if messageChannelID in relayChannels:
        for destId in relayChannels[messageChannelID]:
            dest = bot.get_channel(int(destId))
            if dest:
                await dest.send(message.content)
    else:
        await bot.process_commands(message)

bot.run(os.environ.get('TOKEN'))
