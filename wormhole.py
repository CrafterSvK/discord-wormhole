import os
import json
import asyncio
from io import BytesIO

import discord
from discord.ext import commands

config = json.load(open('config.json'))

class Wormhole(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

		self.wormholes = []
		self.sent = []

		self.transferred = 0

	def is_admin(ctx: commands.Context):
		return ctx.author.id == config['admin id']

	@commands.Cog.listener()
	async def on_message(self, message: discord.Message):
		# do not act if channel is not wormhole channel
		if message.channel.id not in config['wormholes']:
			return

		# do not act if author is bot
		if message.author.bot:
			return

		# do not act if message is bot command
		if message.content.startswith(config['prefix'] + 'wormhole'):
			return

		# get wormhole channel objects
		self.__update()

		# copy remote message
		content = None
		files = []
		if message.content:
			content = self.__process(message)

		if message.attachments:
			for f in message.attachments:
				fp = BytesIO()
				await f.save(fp)
				files.append(discord.File(fp, filename=f.filename))

		# send the message
		self.transferred += 1
		await self.__send(message, content, files)

	@commands.Cog.listener()
	async def on_message_edit(self, before: discord.Message, after: discord.Message):
		if before.content == after.content:
			return

		# get forwarded messages
		forwarded = None
		for m in self.sent:
			if m[0].id == after.id:
				forwarded = m
				break
		if not forwarded:
			return

		content = self.__process(after)
		for m in forwarded[1:]:
			await m.edit(content=content)

	@commands.Cog.listener()
	async def on_message_delete(self, message: discord.Message):
		# get forwarded messages
		forwarded = None
		for m in self.sent:
			if m[0].id == message.id:
				forwarded = m
				break
		if not forwarded:
			return

		for m in forwarded[1:]:
			await m.delete()

	@commands.group(name="wormhole")
	async def wormhole(self, ctx: commands.Context):
		if ctx.invoked_subcommand is None:
			m = "**{}** messages sent since the first formation."
			await ctx.send(m.format(self.transferred))

	@wormhole.command()
	async def link(self, ctx: commands.Context):
		"""Send a message with link to the bot"""
		await ctx.send("https://github.com/sinus-x/discord-wormhole")

	@commands.check(is_admin)
	@wormhole.command()
	async def open(self, ctx: commands.Context):
		if ctx.channel.id in config['wormholes']:
			return
		config['wormholes'].append(ctx.channel.id)
		self.__update()
		self.__save()
		await asyncio.sleep(1)
		await self.__send(ctx=ctx, source=True,
			text="Wormhole opened: **{}** in **{}**".format(
				ctx.channel.name, ctx.channel.guild.name), files=None)
		#TODO Send list of opened wormholes

	@commands.check(is_admin)
	@wormhole.command()
	async def close(self, ctx: commands.Context, channel: discord.TextChannel):
		if ctx.channel.id not in config['wormholes']:
			return
		config['wormholes'].remove(ctx.channel.id)
		self.__update()
		self.__save()
		await self.__send(ctx=ctx, source=True,
			text="Wormhole closed: **{}** in **{}**".format(
				ctx.channel.name, ctx.channel.guild.name), files=None)
		#TODO Send list of opened wormholes

	@commands.check(is_admin)
	@wormhole.command()
	async def anonymity(self, ctx: commands.Context, value: str):
		opts = ['none', 'guild', 'full']
		if value not in opts:
			ctx.send("Options are: " + ', '.join(opts))
		else:
			config['anonymity'] = value
			self.__save()
			await self.__send(ctx=ctx, source=True,
				text="New anonymity policy: **{}**".format(value), files=None)


	def __process(self, message: discord.Message):
		"""Escape mentions and apply anonymity"""
		content = message.content
		# escape mentions
		users = message.mentions
		if users is not None:
			for member in users:
				content = content.replace(member.mention, '@'+member.name)
		channels = message.channel_mentions
		if channels is not None:
			for channel in channels:
				content = content.replace(channel.mention, channel.guild.name+'#'+channel.name)
		roles = message.role_mentions
		if roles is not None:
			for role in roles:
				content = content.replace(role.mention, '@'+role.name)

		# apply anonymity option
		a = config.get('anonymity')
		u = discord.utils.escape_mentions(message.author.name)
		g = discord.utils.escape_mentions(message.guild.name)
		if a == 'none':
			content = f'**{u}, {g}**: ' + content
		elif a == 'guild':
			g = discord.utils.escape_mentions(message.guild.name)
			content = f'**{g}**: ' + content
		elif a == 'all':
			pass

		# done
		return content


	async def __send(self, message: discord.Message, text: str, files: list, source: bool = False):
		# redistribute the message
		msgs = [message]
		for w in self.wormholes:
			if w.id == message.channel.id and not source:
				continue
			m = await w.send(content=text, files=files)
			msgs.append(m)

		self.sent.append(msgs)
		await asyncio.sleep(config['message window'])
		self.sent.remove(msgs)


	def __update(self):
		self.wormholes = []
		for w in config['wormholes']:
			self.wormholes.append(self.bot.get_channel(w))

	def __save(self):
		with open('config.json', 'w', encoding='utf-8') as f:
			json.dump(config, f, ensure_ascii=False, indent=4)


def setup(bot):
	bot.add_cog(Wormhole(bot))
