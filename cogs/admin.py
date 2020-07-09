import re
import json

import discord
from discord.ext import commands

from core import checks, errors, wormcog
from core.database import repo_b, repo_u, repo_w

config = json.load(open("config.json"))


def is_ID(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


class Admin(wormcog.Wormcog):
    """Manage wormholes"""

    def __init__(self, bot):
        super().__init__(bot)

    @commands.check(checks.is_admin)
    @commands.group(name="beam")
    async def beam(self, ctx):
        """Manage beams"""
        await self.delete(ctx)

        if ctx.invoked_subcommand is not None:
            return

        prefix = config["prefix"] + "beam…"
        values = [
            "add <name>",
            "open <name>",
            "close <name>",
            "edit <name> active [0, 1]",
            "edit <name> admin_id <member ID>",
            "edit <name> anonymity [none, guild, full]",
            "edit <name> replace [0, 1]",
            "edit <name> timeout <int>",
            "list",
        ]

        embed = self.getEmbed(ctx=ctx, title="Beams", description=prefix)
        embed.add_field(name="Commands", value="```" + "\n".join(values) + "```")
        embed.add_field(
            name="Online help",
            value="https://sinus-x.github.io/discord-wormhole/administration#beam",
            inline=False,
        )
        await ctx.send(embed=embed, delete_after=self.delay("admin"))

    @beam.command(name="add", aliases=["create"])
    async def beam_add(self, ctx, name: str):
        """Add new beam"""
        # check names
        pattern = r"[a-zA-Z0-9_]+"
        if re.fullmatch(pattern, name) is None:
            raise errors.BadArgument(f"Beam name must match `{pattern}`")

        repo_b.add(name=name, admin_id=ctx.author.id)
        await self.event.sudo(ctx, f"Beam **{name}** created.")
        await self.feedback(ctx, private=False, message=f"Beam **{name}** created and opened.")

    @beam.command(name="open", aliases=["enable"])
    async def beam_open(self, ctx, name: str):
        """Open closed beam"""
        repo_b.set(name=name, key="active", value=1)
        await self.event.sudo(ctx, f"Beam **{name}** opened.")
        await self.announce(beam=name, message=f"Beam opened!")

    @beam.command(name="close", aliases=["disable"])
    async def beam_close(self, ctx, name: str):
        """Close beam"""
        repo_b.set(name=name, key="active", value=0)
        await self.event.sudo(ctx, f"Beam **{name}** closed.")
        await self.announce(beam=name, message=f"Beam closed.")

    @beam.command(name="edit", aliases=["set"])
    async def beam_edit(self, ctx, name: str, key: str, value: str):
        """Edit beam"""
        if not repo_b.exists(name):
            raise errors.BadArgument("Invalid beam")

        if key in ("active", "admin_id", "replace", "timeout"):
            try:
                value = int(value)
            except ValueError:
                raise errors.BadArgument("Value has to be integer.")

        repo_b.set(name=name, key=key, value=value)

        await self.event.sudo(ctx, f"Beam **{name}** updated: **{key}** = **{value}**.")
        await self.announce(beam=name, message=f"Beam updated: **{key}** is now **{value}**.")

    @beam.command(name="list")
    async def beam_list(self, ctx):
        """List all wormholes"""
        embed = discord.Embed(title="Beam list")

        beam_names = repo_b.listNames()
        for beam_name in beam_names:
            beam = repo_b.get(beam_name)
            ws = len(repo_w.listIDs(beam=beam.name))
            name = f"**{beam.name}** ({'in' if not beam.active else ''}active) | {ws} wormholes"
            value = f"Anonymity _{beam.anonymity}_, " + f"timeout _{beam.timeout} s_ "
            embed.add_field(name=name, value=value, inline=False)
        await ctx.send(embed=embed)

    @commands.check(checks.is_admin)
    @commands.group(name="wormhole")
    async def wormhole(self, ctx):
        """Manage wormholes"""
        await self.delete(ctx)

        if ctx.invoked_subcommand is not None:
            return

        description = config["prefix"] + "wormhole…"
        values = [
            "add <beam> [<channel ID>, None]",
            "remove [<channel ID>, None]",
            "edit <channel ID> beam <beam>",
            "edit <channel ID> admin_id <member ID>",
            "edit <channel ID> active [0, 1]",
            "edit <channel ID> logo <string>",
            "edit <channel ID> readonly [0, 1]",
            "edit <channel ID> messages <int>",
            "list",
        ]

        embed = self.getEmbed(ctx=ctx, title="Wormholes", description=description)
        embed.add_field(name="Commands", value="```" + "\n".join(values) + "```")
        embed.add_field(
            name="Online help",
            value="https://sinus-x.github.io/discord-wormhole/administration#wormhole",
            inline=False,
        )
        await ctx.send(embed=embed, delete_after=self.delay("admin"))

    @wormhole.command(name="add", aliases=["create"])
    async def wormhole_add(self, ctx, beam: str, channel_id: int = None):
        """Open new wormhole"""
        channel = self._getChannel(ctx=ctx, channel_id=channel_id)
        if channel is None:
            raise errors.BadArgument("No such channel")

        repo_w.add(beam=beam, discord_id=channel.id)
        await self.event.sudo(ctx, f"{self._w2str_log(channel)} added.")
        await self.announce(
            ctx, beam=beam, message=f"Wormhole opened: {self._w2str_out(channel)}.",
        )

    @wormhole.command(name="remove", aliases=["delete"])
    async def wormhole_remove(self, ctx, channel_id: int = None):
        """Remove wormhole from database"""
        channel = self._getChannel(ctx=ctx, channel_id=channel_id)
        if channel is None:
            raise errors.BadArgument("No such channel")

        beam_name = repo_w.getAttribute(channel_id, "beam")
        repo_w.delete(discord_id=channel_id)
        await self.event.sudo(ctx, f"{self._w2str_log(channel)} removed.")
        await self.announce(
            ctx, beam=beam_name, message=f"Wormhole closed: {self._w2str_out(channel)}.",
        )

    @wormhole.command(name="edit", aliases=["set"])
    async def wormhole_edit(self, ctx, channel_id: int, key: str, value: str):
        """Edit wormhole"""
        if key in ("admin_id", "active", "readonly", "messages"):
            try:
                value = int(value)
            except ValueError:
                raise errors.BadArgument("Value has to be integer.")

        channel = self._getChannel(ctx=ctx, channel_id=channel_id)

        beam_name = repo_w.getAttribute(channel_id, "beam")
        repo_w.set(discord_id=channel.id, key=key, value=value)
        await self.event.sudo(ctx, f"{self._w2str_log(channel)}: {key} = {value}.")
        await self.announce(
            beam=beam_name,
            message=f"Womhole {self._w2str_out(channel)} updated: **{key}** is **{value}**.",
        )

    @wormhole.command(name="list")
    async def wormhole_list(self, ctx):
        """List all wormholes"""
        embed = self.getEmbed(ctx=ctx, title="Wormholes")
        template = "**{mention}** ({guild}): active {active}, readonly {readonly}"

        beams = repo_b.listNames()
        for beam in beams:
            wormholes = repo_w.listObjects(beam=beam)
            value = []
            for db_w in wormholes:
                wormhole = self.bot.get_channel(db_w.discord_id)
                if wormhole is None:
                    value.append("Missing: " + str(db_w))
                    continue
                value.append(
                    template.format(
                        mention=wormhole.mention,
                        guild=wormhole.guild.name,
                        active=db_w.active,
                        readonly=db_w.readonly,
                    )
                )
            value = "\n".join(value)
            if len(value) == 0:
                value = "No wormholes"
            embed.add_field(name=beam, value=value, inline=False)

        await ctx.send(embed=embed, delete_after=self.delay())

    @commands.check(checks.is_mod)
    @commands.group(name="user")
    async def user(self, ctx):
        """Manage users"""
        await self.delete(ctx)

        if ctx.invoked_subcommand is not None:
            return

        description = config["prefix"] + "user…"
        values = [
            "add <member ID> <nickname> <home_id>",
            "remove <member ID>",
            "edit <member ID> home_id <channel ID>",
            "edit <member ID> mod [0, 1]",
            "edit <member ID> nickname <string>",
            "edit <member ID> readonly [0, 1]",
            "edit <member ID> restricted [0, 1]",
            "list",
        ]

        embed = self.getEmbed(ctx=ctx, title="Users", description=description)
        embed.add_field(name="Commands", value="```" + "\n".join(values) + "```")
        embed.add_field(
            name="Online help",
            value="https://sinus-x.github.io/discord-wormhole/administration#user",
            inline=False,
        )
        await ctx.send(embed=embed, delete_after=self.delay("admin"))

    @user.command(name="add")
    async def user_add(self, ctx, member_id: int, nickname: str, home_id: int):
        """Add user"""
        repo_u.add(discord_id=member_id, nickname=nickname, home_id=home_id)
        self.event.sudo(ctx, f"{str(repo_u.get(member_id))}.")

    @user.command(name="remove", alises=["delete"])
    async def user_remove(self, ctx, member_id: int):
        """Remove user"""
        if ctx.author.id != config["admin id"] and repo_u.getAttribute(member_id, "mod") == 1:
            return await ctx.send("> You do not have permission to alter mod accounts")
        if ctx.author.id != config["admin id"] and member_id == config["admin id"]:
            return await ctx.send("> You do not have permission to alter admin account")

        repo_u.delete(member_id)
        await self.event.sudo(ctx, f"User **{member_id}** removed.")

    @user.command(name="edit", aliases=["set"])
    async def user_edit(self, ctx, member_id: int, key: str, value: str):
        """Edit user"""
        if ctx.author.id != config["admin id"] and repo_u.getAttribute(member_id, "mod") == 1:
            return await ctx.send("> You do not have permission to alter mod accounts")
        if ctx.author.id != config["admin id"] and member_id == config["admin id"]:
            return await ctx.send("> You do not have permission to alter admin account")

        if key in ("home_id", "mod", "readonly", "restricted"):
            try:
                value = int(value)
            except ValueError:
                raise errors.BadArgument("Value has to be integer.")

        repo_u.set(discord_id=member_id, key=key, value=value)
        await self.event.sudo(ctx, f"{member_id} updated: **{key}** = **{value}**.")

    @user.command(name="list")
    async def user_list(self, ctx):
        """List all registered users"""
        db_users = repo_u.listObjects()

        template = (
            "{id}: {name} ({nickname})\n"
            "- {home} ({guild})\n"
            "- MOD {mod}, RO {ro}, RESTRICTED {restricted}"
        )

        wormholes = {}
        result = []
        for db_user in db_users:
            # get user
            user = self.bot.get_user(db_user.discord_id)
            user_name = str(user) if hasattr(user, "name") else "---"
            # get wormhole's guild
            if str(db_user.home_id) not in wormholes.keys():
                channel = self.bot.get_channel(db_user.home_id)
                if isinstance(channel, discord.TextChannel):
                    wormholes[str(db_user.home_id)] = self.sanitise(channel.guild.name)
                else:
                    wormholes[str(db_user.home_id)] = "---"

            # add string
            result.append(
                template.format(
                    id=db_user.discord_id,
                    name=user_name,
                    nickname=db_user.nickname,
                    home=db_user.home_id,
                    guild=wormholes[str(db_user.home_id)],
                    mod=db_user.mod,
                    ro=db_user.readonly,
                    restricted=db_user.restricted,
                )
            )

        async def sendOutput(output: str):
            if hasattr(ctx.channel, "id") and repo_w.exists(ctx.channel.id):
                await ctx.author.send("```" + output + "```")
            else:
                await ctx.send("```" + output + "```")

        # iterate over the result
        output = ""
        for line in result:
            if len(output) > 2000:
                await sendOutput(output)
                output = ""
            output += "\n" + line
        if len(result) == 0:
            output = "No users."
        await sendOutput(output)

    def _getChannel(self, *, ctx: commands.Context, channel_id: int = None) -> discord.TextChannel:
        if channel_id:
            return self.bot.get_channel(channel_id)
        if isinstance(ctx.channel, discord.TextChannel):
            return ctx.channel

        raise errors.BadArgument("Missing channel ID.")

    def _getMember(self, *, member_id: int) -> discord.User:
        return self.bot.get_user(member_id)

    def _w2str_out(self, channel: discord.TextChannel) -> str:
        return f"**{channel.mention}** in {channel.guild.name}**"

    def _w2str_log(self, channel: discord.TextChannel) -> str:
        return f"{channel.guild.name}/{channel.name} (ID {channel.id})"


def setup(bot):
    bot.add_cog(Admin(bot))