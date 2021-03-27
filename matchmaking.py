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

BANLIST = ["table", "tables", "drop", "insert", "insert", ";", "\\"]

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
CREATE_TABLE_ALIAS = """CREATE TABLE alias (server_id INTEGER, name VARCHAR(100), other_name VARCHAR(100))"""
    # server_id = id of the server for the alias
    # name = abbreviation of a game
    # other_name = abbreviation of a game with a fullname
CREATE_TABLE_FULLNAME = """CREATE TABLE fullname (server_id INTEGER, name VARCHAR(100), other_name VARCHAR(100))"""
    # server_id = id of the server for the full name
    # name = abbreviation of a game
    # other_name = full name of a game
CREATE_TABLE_PINGHOST = """CREATE TABLE pinghost (server_id INTEGER NOT NULL, discord_id INTEGER NOT NULL, listname VARCHAR(100) UNIQUE)"""
    # server_id = id of the server for the pinglist
    # discord_id = id of the user who can ping the listers
    # listname = the name of the list
CREATE_TABLE_PINGSUB = """CREATE TABLE pingsub (server_id INTEGER NOT NULL, discord_id INTEGER NOT NULL, listname VARCHAR(100))"""
    # server_id = id of the server for the pinglist
    # discord_id = id of the user who has subscribed to a pinglist
    # listname = the name of the subscribed list
CREATE_TABLE_BOARD = """CREATE TABLE board (server_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, message_id INTEGER)"""
    # server_id = id of the server for the matchboard
    # channel_id = the channel where the bot posts the active matches
    # message_id = the id of the last message the bot posted on the board

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
    elif msg.startswith('.steamid') or msg.startswith(".lobby") or msg.startswith(".m") or msg.startswith(".fullname") or msg.startswith(".alias") or msg.startswith(".d") or msg.startswith(".p") or msg.startswith(".board"):
        # We do not want the bot to reply to itself
        if message.author == client.user:
            return
        # For debug, only allows the super admin to use bot
        if DEBUG and message.author.id != SUPER_ADMIN_ID:
            return
        # For debug, ignore calls from super admin
        if COUNTER_DEBUG and message.author.id == SUPER_ADMIN_ID:
            return
        dprint("------------------------------------------------  channel_id:" + str(message.channel.id))

        admin = message.author.id == SUPER_ADMIN_ID
        directMessage = isinstance(message.channel, discord.channel.DMChannel)
        if not directMessage: #message.author.guild_permissions seems to cause an error in dms
            admin = admin or message.author.guild_permissions.manage_channels
                    
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
        elif msg.startswith('.m') and not directMessage:
            dprint(".m ; " + message.author.name + "-" + str(message.author.id))
            await cmd_matchmake(message, conn)
        elif msg.startswith('.pc') and not directMessage:
            dprint(".pc ; " + message.author.name + "-" + str(message.author.id))
            await cmd_pinglistclear(message, conn, admin)
        elif msg.startswith('.p') and not directMessage:
            dprint(".p ; " + message.author.name + "-" + str(message.author.id))
            await cmd_pinglist(message, conn)
        elif admin and not directMessage:
            if msg.startswith('.fullname'):
                await cmd_fullname(message, conn)
            elif msg.startswith('.alias'):
                await cmd_alias(message, conn)
            elif msg.startswith('.d'):
                await cmd_default(message, conn)
            elif msg.startswith('.board'):
                await cmd_board(message, conn)
        conn.close()
#end

async def cmd_fullname(message : discord.Message, conn):
    content = (' '.join(message.content.split())).split(" ")
    args = content[1:len(content)]
    if len(args) is None or len(args) == 0:
        await message.channel.send(".fullname <SHORT NAME> (abbreviation of the name of the game, without spaces) <FULL NAME> (Full name of the game, can include spaces)")
        return
    if args[0].isdigit():
        await message.channel.send("The abbreviation can't be a digit.")
        return
    for i in range(len(args)):
        if checkBan(args[i].lower()):
            return
    
    #Check if the game has a fullname
    cur = conn.cursor()
    cur.execute("SELECT * FROM fullname WHERE name = ? AND server_id = ?", (args[0].lower(), message.channel.guild.id,))
    game = cur.fetchone()
    shortname = ""
    fullname = ""
    
    if len(args) == 1:
        #If only one argument, delete full name if found
        if game is not None:
            cur.execute("DELETE FROM fullname WHERE name = ? AND server_id = ?;", (args[0].lower(), message.channel.guild.id,))
            cur.execute("DELETE FROM alias WHERE other_name = ? AND server_id = ?;", (args[0].lower(), message.channel.guild.id,))
            conn.commit()
            await message.channel.send("Deleted the full name for the game \"" + args[0] +"\".")
            return
        else:
            await message.channel.send("No fullname for the game \"" + args[0] +"\".")
        return
    else:
        shortname = args[0]
        del args[0]
        fullname = ' '.join(args)
        if game is not None:
            #Update instead of inserting if game has a full name already
            cur.execute("UPDATE fullname SET other_name = ? WHERE name = ? AND server_id = ?;", (fullname, shortname.lower(), message.channel.guild.id,))
        else:
            cur.execute("INSERT INTO fullname (name, other_name, server_id) VALUES (?, ?, ?);", (shortname.lower(), fullname, message.channel.guild.id,))
        
    conn.commit()
    await message.channel.send("Set the full name of \"" + shortname +"\" as \"" + fullname +"\".")
#end

async def cmd_alias(message : discord.Message, conn):
    content = (' '.join(message.content.split())).split(" ")
    args = content[1:len(content)]
    
    if len(args) is None or len(args) == 0:
        await message.channel.send(".alias <SHORT NAME>... <SHORT NAME> (abbreviation of the name of the game, without spaces)| One of the short names has to have a full name")
        return
        
    cur = conn.cursor()
    fullnameIndex = -1
    toDelete = []
    
    for i in range(len(args)):
        if checkBan(args[i].lower()):
            return
        if args[i].isdigit(): #No digits allowed in aliases
            toDelete.append(i)
            continue
        cur.execute("SELECT * FROM fullname WHERE name = ? AND server_id = ?", (args[i].lower(), message.channel.guild.id,))
        check = cur.fetchone()
        if check is not None:
            if fullnameIndex == -1:
                fullnameIndex = i
            else:
                #Multiple games with a full name
                await message.channel.send("Multiple of the listed games have a fullname!")
                return
    
    
    if len(toDelete) > 0:
        toDelete.reverse()
        for i in range(len(toDelete)):
            del args[i]
            if fullnameIndex > i:
                fullnameIndex -= 1
    
    if len(args) is None or len(args) == 0:
        await message.channel.send(".alias <SHORT NAME>... <SHORT NAME> (abbreviation of the name of the game, without spaces)| One of the short names has to have a full name")
        return
        
    if fullnameIndex == -1:
        #No game has a full name
        for arg in args:
            cur.execute("DELETE FROM alias WHERE name = ? AND server_id = ?;", (arg.lower(), message.channel.guild.id,))
        conn.commit()
        await message.channel.send("Deleted aliases for " + ", ".join(args) + ".")
        return
    
    if len(args) == 1:
        #Has only name and it has a full name
        await message.channel.send(".alias <SHORT NAME>...<SHORT NAME> (abbreviation of the name of the game, without spaces) | One of the short names has to have a full name")
        return
    
    #Exactly one fullnamed game and at least 1 without one
    aliases = []
    for i in range(len(args)):
        if i == fullnameIndex:
            continue
        cur.execute("SELECT * FROM alias WHERE name = ? AND server_id = ?;", (args[i].lower(), message.channel.guild.id,))    
        alias = cur.fetchone()
        aliases.append(args[i])
        if alias is not None:
            #Update instead of inserting if game has an alias already
            cur.execute("UPDATE alias SET other_name = ? WHERE name = ? AND server_id = ?;", (args[fullnameIndex].lower(), args[i].lower(), message.channel.guild.id,))
        else:
            cur.execute("INSERT INTO alias (name, other_name, server_id) VALUES (?, ?, ?);", (args[i].lower(), args[fullnameIndex].lower(), message.channel.guild.id,))
    await message.channel.send("Set the alias as \"" + args[fullnameIndex] + "\" for " + ", ".join(aliases) + ".")
    conn.commit()
#end
        
async def cmd_default(message : discord.Message, conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM channel WHERE channel_id = ?", (message.channel.id,))
    channel = cur.fetchone()
    content = (' '.join(message.content.split())).split(" ")
    args = content[1:len(content)]
    
    platformChanged = False
    platform = PLATFORM_PC
    gameChanged = False
    game = ""
    
    if len(args) is None or len(args) == 0:
        if channel is not None: #delete the default game for the channel
            cur.execute("DELETE FROM channel WHERE channel_id = ?;", (message.channel.id,))
            conn.commit();
            await message.channel.send("Removed the default game for this channel.")
        else:
            await message.channel.send(".default <GAME> <PLATFORM>(pc(default)|psn|xbox)")
        return
    
    for arg in args:
        if arg.isdigit(): # arg is a time value, since it's the only digit we accept
            continue
        else:
            if checkBan(arg.lower()):
                return
            if arg.lower() == PLATFORM_PC: # arg is a platform
                platform = PLATFORM_PC
                platformChanged = True
            elif arg.lower() == PLATFORM_PSN or arg.lower() == "ps4" : # arg is a platform
                platform = PLATFORM_PSN
                platformChanged = True
            elif arg.lower() == PLATFORM_XBOX : # arg is a platform
                platform = PLATFORM_XBOX
                platformChanged = True
            elif game == "" and gameChanged == False: # arg is a game
                game = arg.lower();
                gameChanged = True
    
    if not gameChanged and not platformChanged:
        await message.channel.send(".default <GAME> <PLATFORM>(pc(default)|psn|xbox)")
        return
    
        
    if channel is not None: #Change existing default parameters
        if gameChanged:
            cur.execute("UPDATE channel SET default_game = ? WHERE channel_id = ?;", (game, message.channel.id,))
        if platformChanged:
            cur.execute("UPDATE channel SET default_platform = ?WHERE channel_id = ?;", (platform, message.channel.id,)) 
        await message.channel.send("Changed default parameters for the channel.")
    elif game == "": #No default parameters, so we need a game
        await message.channel.send(".default <TIME>(default 30 minutes) <GAME> <PLATFORM>(pc(default)|psn|xbox)")
        return
    else:
        cur.execute("INSERT INTO channel (channel_id, default_game, default_platform) VALUES (?, ?, ?);",(message.channel.id, game, platform)) 
        await message.channel.send("Gave the channel a default game.")
    conn.commit()
#end

async def cmd_pinglist(message : discord.Message, conn):
    content = (' '.join(message.content.split())).split(" ")
    args = content[1:len(content)]
    if len(args) is None or len(args) == 0:
        await message.channel.send(".p <NAME> (Name of the pinglist. If one with that name exists, you subscribe to it. If not you create it. If you have created the list, you ping everyone on it.)")
        return
    for i in range(len(args)):
        if checkBan(args[i].lower()):
            return
            
    #Check if the name is already a list
    arg = ' '.join(args)
    
    cur = conn.cursor()
    cur.execute("SELECT discord_id FROM pinghost WHERE listname = ? AND server_id = ?", (arg.lower(), message.channel.guild.id,))
    pinglist = cur.fetchone()
    
    #Check if the name is already a list
    if pinglist is not None: #List exists already
        if message.author.id == pinglist[0]: #Message author created the list
            cur.execute("SELECT discord_id FROM pingsub WHERE listname = ? AND server_id = ?",(arg.lower(), message.channel.guild.id,))
            subs = cur.fetchall()
            ping = "Pinging for \"" + arg + "\" - "
            for i in range(len(subs)):
                ping += "<@{}>".format(subs[i][0])
                if i < len(subs)-1:
                    ping += ", "
            
            await message.channel.send(ping)
            return
        else: #Not the authors list
            cur.execute("SELECT * FROM pingsub WHERE listname = ? AND server_id = ? AND discord_id = ?",(arg.lower(), message.channel.guild.id, message.author.id,))
            pinglist = cur.fetchone()
            if pinglist is None: #Not here, subscribe
                cur.execute("INSERT INTO pingsub (listname, server_id, discord_id) VALUES (?, ?, ?);", (arg.lower(), message.channel.guild.id, message.author.id,))
                conn.commit()
                await message.channel.send("Subscribed for pinglist called \"" + arg + "\".")
                return
            else: #Already subscribe, remove
                cur.execute("DELETE FROM pingsub WHERE listname = ? AND server_id = ? AND discord_id = ?;", (arg.lower(), message.channel.guild.id, message.author.id,))
                conn.commit()
                await message.channel.send("Removed subscription for pinglist called \"" + arg + "\".")
                return
    else: #No list, so create one
        cur.execute("INSERT INTO pinghost (listname, server_id, discord_id) VALUES (?, ?, ?);", (arg.lower(), message.channel.guild.id, message.author.id,))
        conn.commit()
        await message.channel.send("Created pinglist called \"" + arg + "\".")
#end

async def cmd_pinglistclear(message : discord.Message, conn, admin):
    content = (' '.join(message.content.split())).split(" ")
    args = content[1:len(content)]
    if len(args) is None or len(args) == 0:
        await message.channel.send(".pc <NAME> (Name of the pinglist you want to delete. You have to be a moderator or have created the list to delete it")
        return
    for i in range(len(args)):
        if checkBan(args[i].lower()):
            return
    
    arg = ' '.join(args)
    
    cur = conn.cursor()
    cur.execute("SELECT discord_id FROM pinghost WHERE listname = ? AND server_id = ?", (arg.lower(), message.channel.guild.id,))
    pinglist = cur.fetchone()
    
    if pinglist is not None:
        if pinglist[0] == message.author.id or admin:
            cur.execute("DELETE FROM pinghost WHERE listname = ? AND server_id = ?", (arg.lower(), message.channel.guild.id,))
            conn.commit()
            await message.channel.send("Deleted a pinglist with the name \"" + arg + "\".")
        else:
            await message.channel.send("You do not have the permission to delete that list.")
    else:
        await message.channel.send("No pinglist with the name \"" + arg + "\".")
#end

async def cmd_board(message : discord.Message, conn):
    cur = conn.cursor()
    cur.execute("SELECT channel_id, message_id FROM board WHERE server_id = ?", (message.channel.guild.id,))
    board = cur.fetchone()
    
    if board is not None: #server already has a board
        if board[0] == message.channel.id: #The message was in the messageboard, so let's delete it
            cur.execute("DELETE FROM board WHERE channel_id = ?;", (message.channel.id,))
            dprint("Deleted board.")
            conn.commit()
        else: #Designate a new channel
            cur.execute("UPDATE board SET channel_id = ? WHERE server_id = ?;", (message.channel.id, message.channel.guild.id))
            conn.commit()
            dprint("Update board.")
            await updateBoard(message.channel.guild.id, conn, True) #Update the message into new channel, so we want to delete instead of update
    else: #server has no board
        cur.execute("INSERT INTO board(channel_id, server_id, message_id) VALUES (?,?,?);", (message.channel.id, message.channel.guild.id, -1,))
        conn.commit()
        dprint("New board.")
        await updateBoard(message.channel.guild.id, conn, True) #Update the message into new channel, so we want to delete instead of update
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
    await updateBoard(message.guild.id, conn, False)

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
    cur = conn.cursor()
    
    if len(args) > 0:
        for arg in args:
            if arg.isdigit(): # arg is a time value, since it's the only digit we accept
                duration = int(arg)
                if duration <= 0:
                    duration == 1
                elif duration >= 1440:
                    duration = 1440
            else:
                if checkBan(arg.lower()):
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
                    gameName = getAlias(arg.lower(), cur, message.channel.guild.id)
                    for game in gameList:
                        if game.lower() == gameName:
                            exists = True
                            break
                    if not exists:
                        gameList.append(gameName)

    # Is this channel actually registerd to work with the bot?
    cur.execute("SELECT * FROM channel WHERE channel_id = ?", (message.channel.id,))
    channelInfo = cur.fetchone()

    ch = None

    if channelInfo is not None: # Stop if not registered
        ch = Channel(int(channelInfo[0]), int(channelInfo[1]), channelInfo[2], channelInfo[3], channelInfo[4], channelInfo[5], channelInfo[6])
        if len(gameList) == 0:
            gameList.append(getAlias(ch.default_game, cur, message.channel.guild.id))
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
                        msg = matchMessage.format("<@{}>".format(match.discord_id), message.author.mention, getFullName(game, cur, message.channel.guild.id), platform.upper())
                        conn.commit()
                        await message.channel.send(msg)
                        # Delete other pending match requests for both players
                        deleteAllMatchesByUserId(message.author.id, conn)
                        deleteAllMatchesByUserId(match.discord_id, conn)
                        await updateBoard(message.channel.guild.id, conn, False)
                        return # We are done
                elif match.game.lower() == game.lower() and match.platform.lower() == platform.lower():
                    # We found an old matchmaking request from this user in this channel. Cancel it.
                    deleteMatch(match, conn)
                    canceledMatches.append(getFullName(game, cur, message.channel.guild.id)) # For informing the user later below
                    newMatch = False
                    if len(matches) == 1 and (time.time() - 60) < match.timestamp:
                        dprint("memes")
                        pressF = True
                    break
            # No existing matches that matter... has to be a new match then...
            if newMatch:
                createNewMatch(game.lower(), platform.lower(), duration, message, channelInfo, serverId, conn)
                createdMatches.append(getFullName(game,cur, message.channel.guild.id))
    else: # There's no matches, so this has to be a new one
        for game in gameList:
            createNewMatch(game.lower(), platform.lower(), duration, message, channelInfo, serverId, conn)
            createdMatches.append(getFullName(game, cur, message.channel.guild.id))

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
    
    await updateBoard(message.channel.guild.id, conn, len(createdMatches) > 0)
    return

def checkBan(message):
    for word in BANLIST:
        if word in message.lower(): # what the fuck dude
            dprint("ban pls")
            return True
    return False
    
def getAlias(game, cur, id):
    game = game.lower() #we want to store stuff internally as lower case
    cur.execute("SELECT other_name FROM alias WHERE name = ? AND server_id = ?", (game, id,))
    alias = cur.fetchone()
    if alias is not None:
        dprint(alias[0]);
        return alias[0];
    return game

def getFullName(game, cur, id):
    cur.execute("SELECT other_name FROM fullname WHERE name = ? AND server_id = ?", (game.lower(), id,))
    fullname = cur.fetchone()
    if fullname is not None:
        dprint(fullname[0]);
        return fullname[0];
    return game
    
async def updateBoard(server_id : int, conn, deleteInsteadOfUpdate : bool):
    cur = conn.cursor()
    cur.execute("SELECT channel_id, message_id FROM board WHERE server_id = ?;", (server_id,))
    board = cur.fetchone()
    
    if board is not None:
        channel = client.get_channel(board[0])
        if channel is not None: 
            cur.execute("SELECT * FROM match WHERE server_id = ?", (server_id,))
            matches = cur.fetchall()
            matches = check_match_expriration(matches, conn)

            listMessage = "Pending searches:"
            statusMessage = ""
            game = ""
            for m in matches:
                match = Match(int(m[0]), int(m[1]), int(m[2]), m[3], int(m[4]), m[5], int(m[6]), int(m[7]))
                game = match.game
                statusMessage += " " + game
                cur.execute("SELECT other_name FROM fullname WHERE name = ?", (match.game,))
                fullname = cur.fetchone()
                statusMessage += " " + game
                if fullname is not None:
                    game = fullname[0]
                listMessage += "\n" + game + " on " + match.platform.upper() + " until " + time.strftime("%H.%M", time.localtime(match.expires_at))
        
            hasMessage = False
            if statusMessage == "":
                statusMessage = "None"
            await client.change_presence(activity=discord.Game(statusMessage))
            if board[1] >= 0: #-1 is no message yet, and fetch_message excepts a non-negative value
                try:
                    message = await channel.fetch_message(board[1])
                    hasMessage = True
                except discord.NotFound as e:
                    dprint(str(e))
            
            if deleteInsteadOfUpdate or not hasMessage:
                if hasMessage:
                    await message.delete()
                message = await channel.send(listMessage)
                cur.execute("UPDATE board SET message_id = ? WHERE channel_id = ?;", (message.id, message.channel.id))
                conn.commit()
            else:
                await message.edit(content=listMessage)
#end
    
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
        
    try:
        cur.execute(CREATE_TABLE_FULLNAME)
    except sqlite3.Error as e:
        dprint(str(e))
    try:
        cur.execute(CREATE_TABLE_ALIAS)
    except sqlite3.Error as e:
        dprint(str(e))
    
    try:
        cur.execute(CREATE_TABLE_PINGHOST)
    except sqlite3.Error as e:
        dprint(str(e))
        
    try:
        cur.execute(CREATE_TABLE_PINGSUB)
    except sqlite3.Error as e:
        dprint(str(e))
    
    try:
        cur.execute(CREATE_TABLE_BOARD)
    except sqlite3.Error as e:
        dprint(str(e))
        
    conn.close()

async def task():
    await client.wait_until_ready()
#    while True:
#        await asyncio.sleep(1)
#        print('Running')

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


