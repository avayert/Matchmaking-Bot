import discord
import time
import steam
import sqlite3
import math
import asyncio
from datetime import datetime

# for debug logs
def dprint(message):
    if DEBUG or COUNTER_DEBUG or LOG or LOG_VERBOSE:
        print(message)
        f = None
        try:
            f = open("log.log", "a")
            f.write(datetime.now().strftime("%d/%m/%Y %H:%M:%S")+" d  :  "+message+"\n")
        finally:
            f.close()
def vprint(message):
    if DEBUG or COUNTER_DEBUG or LOG_VERBOSE:
        print(message)
        f = None
        try:
            f = open("log.log", "a")
            f.write(datetime.now().strftime("%d/%m/%Y %H:%M:%S")+" v  :  "+message+"\n")
        finally:
            f.close()
            print("err writing")

TOKEN = '' # Discord bot key
client = discord.Client()

STEAM_KEY = "" # Steam API key
steam.api.key.set(STEAM_KEY)

SUPER_ADMIN_ID = 0 # my discord id

LOG = True
LOG_VERBOSE = False
DEBUG = False
COUNTER_DEBUG = False # ignore the superadmin (allows two instances to run at the same time)
SECONDS = 60 #lul
DEFAULT_MATCHMAKING_EXPIRATION = 30

DATABASE_NAME = "/opt/matchmaking/data.db"

CREATE_TABLE_MATCH = """CREATE TABLE match (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id INTEGER NOT NULL, discord_id INTEGER NOT NULL, game VARCHAR(100) NOT NULL, expiration INT NOT NULL, platform VARCHAR(5) DEFAULT "pc", server_id INTEGER NOT NULL, timestamp INTEGER);"""
    # id = match[0]
    # channel_id = match[1]
    # discord_id = match[2]
    # game = match[3]
    # expires_at = match[4]
    # platform = match[5]
    # server_id = match[6]
    # timestamp = match[7]
CREATE_TABLE_CHANNEL = """CREATE TABLE channel (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id INTEGER NOT NULL UNIQUE, default_game varchar(100) NOT NULL, default_platform VARCHAR(5) DEFAULT "pc", default_matchmake_message VARCHAR(100) DEFAULT "Matchmaking for {0} on {1} for {2} minutes", default_match_message VARCHAR(100) DEFAULT "Match found! {0} vs {1} on {2} on {3}", default_cancel_message VARCHAR(100) DEFAULT "Canceled matchmaking for {0}");"""
    #  id = channel[0]
    #  channel_id = channel[1]
    #  default_game = channel[2]
    #  default_platform = channel[3]
    #  default_matchmake_message = channel[4]
    #  default_match_message = channel[5]
    #  default_cancel_message = channel[6]
CREATE_TABLE_USER = """CREATE TABLE user ( id INTEGER PRIMARY KEY AUTOINCREMENT, discord_id INTEGER NOT NULL UNIQUE, steam_id INTEGER UNIQUE );"""
    #  id = user[0]
    #  discord_id = user[1]
    #  steam_id = user[2]
#CREATE_TABLE_GAME = """CREATE TABLE game ( id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(100))"""
    # id = game[0]
    # name = game[1]

PLATFORM_PC = "pc"
PLATFORM_PSN = "psn"
PLATFORM_XBOX = "xbox"

USAGE_MESSAGE = "Usage: .m <TIME>(default 30 minutes) <GAME> <PLATFORM>(pc|psn|xbox)"
# These are used when there's no registered channel found
DEFAULT_MATCHMAKE_MESSAGE = "Matchmaking for {0} on {1} for {2} minutes"
DEFAULT_MATCH_MESSAGE = "Match found! {0} vs {1} on {2} on {3}"
DEFAULT_CANCEL_MESSAGE = "Canceled matchmaking for {0}"


class Match:
    def __init__(self, id, channel_id, discord_id, game, expires_at, platform, server_id, timestamp):
        self.id = id
        self.channel_id = channel_id
        self.discord_id = discord_id
        self.game = game
        self.expires_at = expires_at
        self.platform = platform
        self.server_id = server_id
        self.timestamp = timestamp

class Channel:
    def __init__(self, id, channel_id, default_game, default_platform, default_matchmake_message, default_match_message, default_cancel_message):
        self.id = id
        self.channel_id = channel_id
        self.default_game = default_game
        self.default_platform = default_platform
        self.default_matchmake_message = default_matchmake_message
        self.default_match_message = default_match_message
        self.default_cancel_message = default_cancel_message

class User:
    def __init__(self, id, discord_id, steam_id):
        self.id = id
        self.discord_id = discord_id
        self.steam_id = steam_id

@client.event
async def on_message(message : discord.Message):
    msg = message.content
    if msg.startswith(",m"):
        await message.add_reaction("<:muikea:296390386547556352>")
    elif msg.startswith('.steamid') or msg.startswith(".lobby") or msg.startswith(".m"):
        # We do not want the bot to reply to itself
        if message.author == client.user:
            return
        # For debug, only allows the super admin to use bot
        if DEBUG and message.author.id != SUPER_ADMIN_ID:
            return
        # For debug, ignore calls from super admin
        if COUNTER_DEBUG and message.author.id == SUPER_ADMIN_ID:
            return
        dprint("------------------------------------------------ channel_id:" + str(message.channel.id))

        conn = sqlite3.connect(DATABASE_NAME) # create connection
        if msg.startswith('.steamid'):
            dprint(".steamid ; " + message.author.name + "-" + str(message.author.id))
            await cmd_steamid(message, conn)
        elif msg.startswith('.lobby'):
            dprint(".lobby ; " + message.author.name + "-" + str(message.author.id))
            await cmd_lobby(message, conn)
        elif msg.startswith('.ml') or msg.startswith('.m list'):
            await cmd_list(message, conn)
        elif msg.startswith('.mc') or msg.startswith('.m clear'):
            await cmd_clearall(message, conn)
        elif msg.startswith('.m') and message.channel.id != BOT_PM_CHANNEL:
            dprint(".m ; " + message.author.name + "-" + str(message.author.id))
            await cmd_matchmake(message, conn)
        conn.close()
#end

async def cmd_stats(message : discord.Message, conn):
    userId = message.author.id
    cur = conn.cursor()

    dprint("Messages found: " + str(counter))
    return

async def cmd_steamid(message : discord.Message, conn):
    # Handle the user input
    content = (' '.join(message.content.split())).split(" ")
    args = content[1:len(content)]
    if len(args) is None or len(args) == 0:
        await message.channel.send(".steamid <steamID64|URL> | Use the numerical 'steamID64' value OR your steamcommunity profile url")
        return
    steamId = args[0]

    cur = conn.cursor()
    cur.execute("SELECT * FROM user WHERE discord_id = ?", (message.author.id,))
    user = cur.fetchone()
    # If user does not exist, insert it into the db
    sqlcommand = "INSERT INTO user (steam_id, discord_id) VALUES (?,?);"
    message_action = "registered"
    if user is not None:
        # update instead of inserting if user was found
        sqlcommand = "UPDATE user SET steam_id = ? WHERE discord_id = ?;"
        message_action = "updated"
    if len(args) > 0:
        try:
            id = None
            if steamId.isdigit() or "/profiles/" in steamId:
                if "/profiles/" in steamId: # Also works with non-vanity profile urls
                    steamId = steamId.rsplit("/profiles/", 1)[1]
                    steamId = steamId.replace("/", "")
                profile = steam.user.profile(str(steamId))
                id = profile.id64
            else:
                profile = steam.user.vanity_url(steamId)
                id = profile.id64
            if id is None:
                raise steam.user.ProfileNotFoundError()
            cur = conn.cursor()
            cur.execute(sqlcommand, (id, message.author.id))
            conn.commit()
        except sqlite3.Error as e:
            await message.channel.send("That SteamID is already registered to someone.")
            dprint("SteamID already registered.")
            return
        except (steam.user.ProfileNotFoundError, steam.user.VanityError):
            dprint("Couldn't find profile.")
            await message.channel.send("Couldn't find profile.")
            return
    await message.channel.send("SteamID {0}. You can now use the .lobby command.".format(message_action))
#end


async def cmd_lobby(message : discord.Message, conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM user WHERE discord_id = ?", (message.author.id,))

    steamId = None
    user = cur.fetchone()
    # Check if the user has a steamID registered
    if user is not None:
        if user[2] is not None:
            steamId = user[2]
        else:
            await message.channel.send("Please register your SteamID first with .steamid <steamid64>.")
            return
    else:
        await message.channel.send("Please register your SteamID first with .steamid <steamid64>.")
        return

    # Try to find the user's profile (just to make sure it exists)
    profile = None
    try:
        profile = steam.user.profile(steamId)
        id = profile.id64
        if id is None:
            raise steam.user.ProfileNotFoundError()
    except steam.user.ProfileNotFoundError:
        await message.channel.send("Couldn't find your registered profile.")
        return

    # Make sure the required lobby information is available
    if profile.lobbysteamid is None or profile.lobbysteamid == 0 or profile.current_game[0] is None:
        await message.channel.send("No lobby found.")
        return

    await message.channel.send("steam://joinlobby/{0}/{1}/{2}".format(str(profile.current_game[0]), str(profile.lobbysteamid), str(steamId)))
#end

async def cmd_clearall(message : discord.Message, conn):
    deleteAllMatchesByUserId(message.author.id, conn)
    await message.channel.send(DEFAULT_CANCEL_MESSAGE.format("everything!"))

async def cmd_list(message : discord.Message, conn):
    # Load all pending matches
    cur = conn.cursor()
    cur.execute("SELECT * FROM match")
    matches = cur.fetchall()
    matches = check_match_expriration(matches, conn)

    listMessage = "Pending searches:"
    for guild in client.guilds: # Get matches in just this server
        guildName = None
        if guild.get_member(message.author.id) == None:
            continue # Not a mutual guild
        else:
            guildName = guild.name

        for m in matches:
            match = Match(int(m[0]), int(m[1]), int(m[2]), m[3], int(m[4]), m[5], int(m[6]), int(m[7]))
            if match.server_id == guild.id:
                if guildName is not None:
                    listMessage += "\n- " + guildName + " -"
                    guildName = None
                listMessage += "\n" + match.game + " on " + match.platform
    #end loops
    await message.author.send(listMessage)

async def cmd_matchmake(message : discord.Message, conn):
    global DEFAULT_MATCHMAKING_EXPIRATION
    global SECONDS

    # Handle the user input
    args = (' '.join(message.content.split())).split(" ")
    args = args[1:len(args)]
    dprint("args="+"; ".join(args))
    duration = DEFAULT_MATCHMAKING_EXPIRATION
    matchmakeMessage = None
    matchMessage = None
    cancelMessage = None
    platform = None
    gameList = []
    banList = ["table", "tables", "drop", "insert", "insert", ";", "\\"]
    if len(args) > 0:
        for arg in args:
            if arg.isdigit(): # arg is a time value, since it's the only digit we accept
                duration = int(arg)
                if duration == 0:
                    duration == 1
                elif duration >= 1440:
                    duration = 1440
            else:
                for word in banList:
                    if word in arg.lower(): # what the fuck dude
                        dprint("ban pls")
                        return
                if arg.lower() == PLATFORM_PC: # arg is a platform
                    platform = PLATFORM_PC
                elif arg.lower() == PLATFORM_PSN or arg.lower() == "ps4" : # arg is a platform
                    platform = PLATFORM_PSN
                elif arg.lower() == PLATFORM_XBOX : # arg is a platform
                    platform = PLATFORM_XBOX
                else: # arg is a game
                    if arg.lower() == "h" or arg.lower() == "help":
                        await message.channel.send(USAGE_MESSAGE)
                        return
                    exists = False
                    for game in gameList:
                        if game.lower() == arg.lower():
                            exists = True
                            break
                    if not exists:
                        gameList.append(arg)

    # Is this channel actually registerd to work with the bot?
    cur = conn.cursor()
    cur.execute("SELECT * FROM channel WHERE channel_id = ?", (message.channel.id,))
    channelInfo = cur.fetchone()

    ch = None

    if channelInfo is not None: # Stop if not registered
        ch = Channel(int(channelInfo[0]), int(channelInfo[1]), channelInfo[2], channelInfo[3], channelInfo[4], channelInfo[5], channelInfo[6])
        if len(gameList) == 0:
            gameList.append(ch.default_game)
        if platform is None:
            platform = ch.default_platform
        matchmakeMessage = ch.default_matchmake_message
        matchMessage = ch.default_match_message
        cancelMessage = ch.default_cancel_message
    else:
        if len(gameList) == 0:
            await message.channel.send(USAGE_MESSAGE)
            return
        if platform is None: # Lets just assume it's PC on non-registered channels
            platform = PLATFORM_PC
        matchMessage = DEFAULT_MATCH_MESSAGE
        matchmakeMessage = DEFAULT_MATCHMAKE_MESSAGE
        cancelMessage = DEFAULT_CANCEL_MESSAGE


    # Load all pending matches
    cur.execute("SELECT * FROM match")
    matches = cur.fetchall()

    matches = check_match_expriration(matches, conn)

    serverId = None
    for guild in client.guilds: # Check if the match request is in this server
        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel):
                if channel.id == message.channel.id:
                    serverId = int(guild.id)
                    break
        if serverId is not None:
            break
    if serverId is None:
        dprint("server id is None!")
        return

    pressF = False
    canceledMatches = []
    createdMatches = []
    if len(matches) > 0:
        for game in gameList: # Go through the list of games given by the user
            newMatch = True
            # Handle existing matches in this loop
            for m in matches: # Go through the list of pending match requests
                match = Match(int(m[0]), int(m[1]), int(m[2]), m[3], int(m[4]), m[5], int(m[6]), int(m[7]))
                if match.server_id != serverId:
                    continue

                vprint("----------------")
                vprint("Pending - Request.")
                vprint("channel_id: " + str(match.channel_id) + " - " + str(message.channel.id))
                vprint("discord_id: " + str(match.discord_id) + " - " + str(message.author.id))
                vprint("game:" + str(match.game) + " - " + str(game))
                vprint("platform:" + str(match.platform) + " - " + str(platform))
                vprint("server_id:" + str(match.server_id) + " - " + str(serverId))

                if match.discord_id != message.author.id: # Is request made by this user?
                    # A game in gameList is the same as in some pending request. Deal with it.
                    # Afterwards we do need to delete all pending requests that possible were made
                    # during this process
                    if match.game.lower() == game.lower() and match.platform.lower() == platform.lower() and match.server_id == serverId:
                        dprint("Match made successfully!")
                        # We found a pending matchmaking request for the given game and platform in this channel!
                        cur = conn.cursor()
                        cur.execute("DELETE FROM match WHERE id = ?;", (match.id,))
                        conn.commit()
                        msg = matchMessage.format("<@{}>".format(match.discord_id), message.author.mention, game, platform.upper())
                        await message.channel.send(msg)
                        # Delete other pending match requests for both players
                        deleteAllMatchesByUserId(message.author.id, conn)
                        deleteAllMatchesByUserId(match.discord_id, conn)
                        return # We are done
                elif match.game.lower() == game.lower() and match.platform.lower() == platform.lower():
                    # We found an old matchmaking request from this user in this channel. Cancel it.
                    deleteMatch(match, conn)
                    canceledMatches.append(game) # For informing the user later below
                    newMatch = False
                    if len(matches) == 1 and (time.time() - 60) < match.timestamp:
                        dprint("memes")
                        pressF = True
                    break
            # No existing matches that matter... has to be a new match then...
            if newMatch:
                createNewMatch(game.lower(), platform.lower(), duration, message, channelInfo, serverId, conn)
                createdMatches.append(game)
    else: # There's no matches, so this has to be a new one
        for game in gameList:
            createNewMatch(game.lower(), platform.lower(), duration, message, channelInfo, serverId, conn)
            createdMatches.append(game)

    # We created a new match if we are here
    dprint("Deleted matches: " + ", ".join(canceledMatches))

    if len(canceledMatches) == 1 and len(createdMatches) == 0 and pressF:
        dprint("more memes")
        await message.add_reaction("🇫")

    if len(canceledMatches) > 0:
        await message.channel.send(cancelMessage.format(', '.join(canceledMatches)))
    dprint("Created matches: " + ", ".join(createdMatches))
    if len(createdMatches) > 0:
        await message.channel.send(matchmakeMessage.format(', '.join(createdMatches), platform.upper(), duration))
    return

def deleteMatch(match, conn):
    dprint("Deleting match id=" + str(match.id))
    cur = conn.cursor()
    cur.execute("DELETE FROM match WHERE id = ?;", (match.id,))
    conn.commit()

def deleteAllMatchesByUserId(discord_id, conn):
    dprint("Deleting all matches from user discord_id=" + str(discord_id))
    cur = conn.cursor()
    cur.execute("DELETE FROM match WHERE discord_id = ?;", (discord_id,))
    conn.commit()

def createNewMatch(game, platform, duration, message, channelInfo, server_id, conn):
    dprint("Creating a new match!!!")
    expiration = math.ceil(time.time() + duration * SECONDS)
    cur = conn.cursor() # Now create a new match
    dprint("channel_id=" + str(message.channel.id) + ", discord_id=" + str(message.author.id) + ", game=" + game + ", expiration=" + str(expiration) + ", platform=" + platform + ", server_id=" + str(server_id))
    cur.execute("INSERT INTO match (channel_id, discord_id, game, expiration, platform, server_id, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?);", 
        (message.channel.id, message.author.id, game, expiration, platform, server_id, math.ceil(time.time())))
    conn.commit()

    dprint("Match created!!! " + str(cur.lastrowid))

# Removes orphaned matches
def check_match_expriration(matches, conn):
    dprint("Cleaning expired matches...")
    deleteSql = "DELETE FROM match WHERE id IN ({})"
    returnMatchList = []
    idList = []
    for match in matches:
        if match[4] <= math.ceil(time.time()):
            idList.append(match[0])
        else:
            returnMatchList.append(match)
    cur = conn.cursor()
    cur.execute(deleteSql.format(", ".join("?" * len(idList))), idList)
    conn.commit()
    return returnMatchList

@client.event
async def on_ready():
    dprint('Logged in as: '+client.user.name)
    dprint('Bot ID: '+str(client.user.id))
    for guild in client.guilds:
        dprint('------')
        dprint ("Connected to server: {0} : named {1}".format(str(guild.id), guild.name))
        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel):
                dprint ("channel: {0} : named {1}".format(str(channel.id), channel.name))
    dprint('-----------------------------------------------')
    # Lets make sure we have the database operational
    conn = sqlite3.connect(DATABASE_NAME)

    cur = conn.cursor()

    try:
        cur.execute("PRAGMA database_list")
        rows = cur.fetchall()
        for row in rows:
           dprint(str(row[0]))
           dprint(str(row[1]))
           dprint(str(row[2]))
    except sqlite3.Error as e:
        dprint("err checking sb path: " + str(e))
    try:
        cur.execute(CREATE_TABLE_MATCH)
    except sqlite3.Error as e:
        dprint(str(e))

    try:
        cur.execute(CREATE_TABLE_CHANNEL)
    except sqlite3.Error as e:
        dprint(str(e))

    try:
        cur.execute(CREATE_TABLE_USER)
    except sqlite3.Error as e:
        dprint(str(e))
    conn.close()

async def task():
    await client.wait_until_ready()
#    while True:
#        await asyncio.sleep(1)
#        print('Running')

while True:
    client.loop.create_task(task())
    try:
        client.loop.run_until_complete(client.start(TOKEN))
    except SystemExit:
        handle_exit()
    except KeyboardInterrupt:
        handle_exit()
        client.loop.close()
        print("Program ended")
        break

    print("Bot restarting")
    client = discord.Client(loop=client.loop)

def handle_exit():
    print("Handling")
    client.loop.run_until_complete(client.logout())
    for t in asyncio.Task.all_tasks(loop=client.loop):
        if t.done():
            t.exception()
            continue
        t.cancel()
        try:
            client.loop.run_until_complete(asyncio.wait_for(t, 5, loop=client.loop))
            t.exception()
        except asyncio.InvalidStateError:
            pass
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            pass
