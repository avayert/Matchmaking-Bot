"""
Commands related to configuring channels, games, et cetera.
"""
from discord.ext import commands


class Configuration(commands.Cog):
    PLATFORMS = {
        'pc': 'pc',
        'xbox': 'xbox',
        'psn': 'psn',
        'ps4': 'psn',
        'ps5': 'psn',
    }

    @commands.group(invoke_without_command=True)
    async def alias(self, ctx, abbreviation: str, *, game: str = None):
        """
        Adds an abbreviated alias for a game. Abbreviation must not contain spaces.
        After the abbreviation, a name for a game can be given. If omitted, the abbreviation will be deleted.
        The name of the game can contain any characters, and is equivalent to the old `fullname` command.
        An existing alias can be given instead of a game name, and the command will operate as the existing `alias`.
        """

        async with ctx.bot.connection.cursor(transaction=True) as cursor:
            if not game:
                await cursor.execute(
                    'DELETE FROM aliases WHERE abbreviation=? RETURNING game;',
                    (abbreviation,)
                )
                result = await cursor.fetchone()
                if result is None:
                    return await ctx.send(f'Alias "{abbreviation}" does not exist.')

                return await ctx.send(f'Deleted alias "{abbreviation}" for game "{game}".')

            # check if right hand side is an existing alias
            await cursor.execute(
                'SELECT game FROM aliases WHERE abbreviation=?;',
                (game,)
            )
            row = await cursor.fetchone()

            if row is not None:
                game, = row

            await cursor.execute(
                'INSERT INTO aliases VALUES (?, ?)'
                '  ON CONFLICT (abbreviation)'
                '  DO UPDATE SET game=excluded.game'
                '  RETURNING game;',
                (abbreviation, game)
            )
            game, = await cursor.fetchone()

            await ctx.send(f'Added "{abbreviation}" as an alias for "{game}".')

    @alias.command()
    async def list(self, ctx):
        async with ctx.bot.connection.cursor() as cursor:
            await cursor.execute('SELECT * FROM aliases')
            results = await cursor.fetchall()

        padding_width = max(len(alias) for alias, game in results)
        aliases = '\n'.join(f'{alias:{padding_width}} - {game}' for alias, game in sorted(results))
        await ctx.send(f'```\n{aliases}```')

    @commands.command()
    @commands.guild_only()
    async def default(self, ctx, item: str = None):
        """
        Sets either the default game or platform for a given channel.

        If no argument is given, clears the default platform and game.
        """

        async with ctx.bot.connection.cursor(transaction=True) as cursor:
            if item is None:
                await cursor.execute(
                    'DELETE FROM default_platforms WHERE channel_id=?;',
                    (ctx.channel.id,)
                )
                await cursor.execute(
                    'DELETE FROM default_games WHERE channel_id=?;',
                    (ctx.channel.id,)
                )
                return await ctx.send('Cleared defaults for the channel.')

            if item in self.PLATFORMS:
                platform = self.PLATFORMS[item]
                await cursor.execute(
                    'INSERT INTO default_platforms VALUES (?, ?)'
                    '  ON CONFLICT (channel_id)'
                    '  DO UPDATE SET platform=excluded.platform',
                    (ctx.channel.id, platform)
                )
                return await ctx.send(f'Set default platform to "{platform}" for {ctx.channel.mention}.')

            else:
                await cursor.execute(
                    'INSERT INTO default_games VALUES (?, ?)'
                    '  ON CONFLICT (channel_id)'
                    '  DO UPDATE SET game=excluded.game',
                    (ctx.channel.id, item)
                )
                return await ctx.send(f'Set default game to "{item}" for {ctx.channel.mention}.')


async def setup(bot):
    await bot.add_cog(Configuration())
