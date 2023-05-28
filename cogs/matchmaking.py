import asyncio
import time
from typing import Optional

from discord.ext import commands

# if only python had `std::chrono`
MINUTES_IN_DAY = 24 * 60 * 60


class Matchmaking(commands.Cog):
    def __init__(self):
        # TODO: this does not support N-many matchmaking but this _should_ be temporary anyway... I hope...

        # stores {AUTHOR_ID: (TIME_STARTED, TIME_WAITING, {GAME, GAME...})}
        # we can just pop the author ID from here once a game is found.
        self.matchmaking_people = {}

        # stores {GAME: AUTHOR_ID}
        # This exists so we can quickly look up if a game is currently being matchmade for.
        # Then the author ID is used to pop from currently_matchmaking, and pop all the games from this one.
        self.matchmaking_games = {}

        self.mutex = asyncio.Lock()

    @commands.command(aliases=['m'])
    async def match(self, ctx, minutes: Optional[int] = 30, *games: Optional[str]):
        # TODO: persist match making requests
        # TODO: add platform

        # allow users to only matchmake for 24 hours at most, and one minute at the least.
        minutes = max(1, min(MINUTES_IN_DAY, minutes))

        if not games:
            default_game = await self._lookup_default_game(ctx)
            if default_game is None:
                return await ctx.send(
                    f'No default game found for {ctx.channel.mention}. Please provide games manually.')
            games = default_game

        # un-alias all the game names
        async with ctx.bot.connection.cursor() as cursor:
            await cursor.execute('SELECT * FROM aliases')
            aliases = await cursor.fetchall()

        aliases = {abbreviation: game for abbreviation, game in aliases}
        games = sorted({aliases.get(game, game) for game in games})

        async with self.mutex:
            self._purge_matchmaking_cache()

            # check if they want to cancel
            if ctx.author.id in self.matchmaking_people:
                games = ', '.join(self._purge_requester(ctx.author.id))
                return await ctx.send(f'Cancelled matchmaking for {games}.')

            match = self._try_matchmake(games)
            if not match:
                # TODO: don't use time.time
                self.matchmaking_people[ctx.author.id] = (time.time(), minutes, games)
                self.matchmaking_games |= dict.fromkeys(games, ctx.author.id)

                games = ', '.join(games)
                await ctx.send(f'Matchmaking for {minutes} minutes for {games}')
            else:
                requester, game = match
                return await ctx.send(f'Match found! {ctx.author.mention} vs <@{requester}> on {game}.')

    @commands.command(aliases=['mc'])
    async def cancel(self, ctx):
        async with self.mutex:
            games = ', '.join(self._purge_requester(ctx.author.id))
        await ctx.send(f'Cancelled matchmaking for {games}')

    @staticmethod
    async def _lookup_default_game(ctx):
        async with ctx.bot.connection.cursor() as cursor:
            await cursor.execute(
                'SELECT game FROM default_games WHERE channel_id = ?',
                (ctx.channel.id,)
            )
            return await cursor.fetchone()

    def _try_matchmake(self, games):
        """
        Searches for existing matchmaking requests for a given game. Purges the cache if found.

        This method must be called from within a mutex.
        """

        for game in games:
            if game in self.matchmaking_games:
                requester = self.matchmaking_games[game]
                self._purge_requester(requester)
                return requester, game

        return None

    def _purge_matchmaking_cache(self):
        """
        Purge outdated requests for games from the matchmaking cache.

        This method must be called from within a mutex.
        """

        for requester, (start_time, waiting_time, games) in self.matchmaking_people.items():
            time_elapsed = time.time() - start_time
            if waiting_time < time_elapsed:
                self._purge_requester(requester)

    def _purge_requester(self, requester):
        """
        Purges a person's requests for games from the matchmaking cache.

        This method must be called from within a mutex.
        """

        _, _, games = self.matchmaking_people.pop(requester)
        for game in games:
            self.matchmaking_games.pop(game)
        return games


async def setup(bot):
    await bot.add_cog(Matchmaking())
