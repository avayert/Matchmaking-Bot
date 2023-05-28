import asyncio
import pathlib
from os import getenv

import asqlite
import discord
from discord.ext import commands

EXTENSIONS = [
    'cogs.configuration',
    'cogs.pinglist',
    'cogs.matchmaking',
]


async def main():
    token = getenv('DISCORD_BOT_TOKEN')
    if token is None:
        print('You must set the `DISCORD_BOT_TOKEN` environment variable to run the bot.')
        return

    # Discord works on an "opt-in-to-events" system. The discord documentation does a really bad job at explaining
    # what that actually means, so I just recommend reading through the attributes listed on the following page:
    # https://discordpy.readthedocs.io/en/stable/api.html#discord.Intents
    intents = discord.Intents.default()
    intents.message_content = True

    discord.utils.setup_logging()

    # Disable role and everyone mentions to avoid kahvikone toimii moments.
    allowed_mentions = discord.AllowedMentions(users=True, roles=False, everyone=False)

    sql_script = pathlib.Path('./sql/V1.sql')

    async with (
        commands.Bot(command_prefix=commands.when_mentioned_or('.'), intents=intents,
                     allowed_mentions=allowed_mentions) as bot,
        asqlite.connect('database.db') as connection,
    ):
        await connection.executescript(sql_script.read_text())

        for extension in EXTENSIONS:
            await bot.load_extension(extension)

        bot.connection = connection

        await bot.start(token=token)


if __name__ == '__main__':
    asyncio.run(main())
