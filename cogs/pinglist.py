from sqlite3 import IntegrityError

import discord
from discord.ext import commands


class Pinglist(commands.Cog):

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def pinglist(self, ctx):
        """
        Lists the available ping lists on the server.
        """

        # TODO: add join/leave behaviour to the parent command.

        async with ctx.bot.connection.cursor() as cursor:
            await cursor.execute('SELECT name FROM pinglists')
            rows = await cursor.fetchall()

        # TODO: pagination
        output = '\n'.join(f'{index:>2}. {name}' for index, (name,) in enumerate(sorted(rows), start=1))
        await ctx.send(f'```{output}```')

    @pinglist.command()
    async def create(self, ctx, *, name: str):
        """
        Create a new ping list.
        """

        try:
            async with ctx.bot.connection.cursor(transaction=True) as cursor:
                await cursor.execute(
                    'INSERT INTO pinglists VALUES (?, ?)',
                    (name, ctx.author.id)
                )
                await cursor.execute(
                    'INSERT INTO pinglist_subscriptions VALUES (?, ?)',
                    (ctx.author.id, name)
                )
        except IntegrityError:
            return await ctx.send(f'Ping list with name "{name}" already exists.')

        await ctx.send(f'Created new ping list "{name}".')

    @pinglist.command()
    async def join(self, ctx, *, name: str):
        """
        Join an existing ping list.
        """

        try:
            async with ctx.bot.connection.cursor(transaction=True) as cursor:
                await cursor.execute(
                    'INSERT INTO pinglist_subscriptions VALUES (?, ?)',
                    (ctx.author.id, name)
                )
        except IntegrityError:
            return await ctx.send(f'A ping list with the name "{name}" does not exist.')

        await ctx.send(f'Added you to the ping list "{name}".')

    @pinglist.command()
    async def leave(self, ctx, *, name: str):
        """
        Leave a ping list.
        """

        async with ctx.bot.connection.cursor(transaction=True) as cursor:
            await cursor.execute(
                'DELETE FROM pinglist_subscriptions WHERE subscriber = ? AND subscription = ?',
                (ctx.author.id, name)
            )

        await ctx.send(f'Removed you from the ping list "{name}".')

    @pinglist.command()
    async def delete(self, ctx, *, name: str):
        """
        Delete a ping list. You must either own the ping list, or have sufficient permissions to delete it.
        """

        # I'd usually use a check for a command like this, but the
        # owner bypass is just easier to implement within the command

        sufficient_permissions = ctx.author.guild_permissions.manage_channels

        async with ctx.bot.connection.cursor(transaction=True) as cursor:
            await cursor.execute(
                'DELETE FROM pinglists WHERE name = ? AND (owner_id = ? OR ?) RETURNING name',
                (name, ctx.author.id, sufficient_permissions)
            )
            result = await cursor.fetchone()

        if result is None:
            return await ctx.send(f'You may not delete the ping list "{name}"')

        return await ctx.send(f'Deleted ping list "{name}".')

    @pinglist.command(aliases=['ping'])
    async def summon(self, ctx, *, name: str):
        """
        Ping all the people on a given ping list. You must be a member of the ping list to do this.
        """

        async with ctx.bot.connection.cursor() as cursor:
            await cursor.execute(
                'SELECT subscriber FROM pinglist_subscriptions WHERE subscription = ?',
                (name,)
            )
            results = await cursor.fetchall()

        if results is None:
            return await ctx.send(f'This ping list does not seem to exist.')

        # format mentions manually so that we don't have to deal with Discord chunking and intent nonsense.
        mentions = ', '.join(f'<@{id}>' for (id,) in results)
        await ctx.send(f'Pinging for {name}\n{mentions}')

    @pinglist.command()
    async def transfer(self, ctx, target: discord.Member, *, name: str):
        """
        Transfer ownership of a ping list to another user.
        """

        # TODO interactive menus without name?
        sufficient_permissions = ctx.author.guild_permissions.manage_channels

        async with ctx.bot.connection.cursor(transaction=True) as cursor:
            await cursor.execute(
                'UPDATE pinglists SET owner_id = ? WHERE name = ? AND (owner_id = ? OR ?) RETURNING name',
                (target.id, name, ctx.author.id, sufficient_permissions)
            )
            result = await cursor.fetchone()

        if result is None:
            return await ctx.send(f'You are not allowed to transfer the ping list "{name}".')


async def setup(bot):
    await bot.add_cog(Pinglist())
