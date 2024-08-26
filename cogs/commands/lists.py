import discord
import aiosqlite
import asyncio
import yaml
import json
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional
from datetime import datetime
from twscrape import API

api = API()

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

guild_id = data["General"]["GUILD_ID"]
embed_color = data["General"]["EMBED_COLOR"]
ping_role_id = data["Roles"]["PING_ROLE_ID"]
list_categories = data["List_Categories"]

class ListsCog(commands.GroupCog, name="list"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def cog_load(self):
        self.listListener.start()

    @tasks.loop(seconds=60)
    async def listListener(self):
        async with aiosqlite.connect('database.db') as db:
            guild = self.bot.get_guild(guild_id)
            ping_role = guild.get_role(ping_role_id)

            cursor = await db.execute('SELECT * FROM lists')
            twitter_lists = await cursor.fetchall()

            for twitter_list in twitter_lists:
                id = twitter_list[0]
                channel_id = twitter_list[1]
                tweets = twitter_list[2]

                channel = self.bot.get_channel(channel_id)
                tweet_list = json.loads(tweets)

                if not channel:
                    await db.execute('DELETE FROM lists WHERE list=?', (id,))
                    await db.commit()
                    return

                tweets = [tweet async for tweet in api.list_timeline(id, limit=1)]

                if tweets:
                    tweet = tweets[0]
                    if tweet.url not in tweet_list:
                        await self.process_tweet(db, tweet, tweet_list, id, channel, ping_role)

    async def process_tweet(self, db, tweet, tweet_list, id, channel, ping_role):
        tweet_list.append(tweet.url)

        updated_tweets = json.dumps(tweet_list)

        await db.execute('UPDATE lists SET tweets=? WHERE list=?', (updated_tweets, id))
        await db.commit()

        embed = discord.Embed(title="Listener", description=f"""
[New Tweet]({tweet.url})

[Twitter List](https://x.com/i/lists/{id})

{tweet.rawContent}
""", color=discord.Color.from_str(embed_color))
        embed.set_author(name=tweet.user.displayname, icon_url=tweet.user.profileImageUrl)
        embed.timestamp = datetime.now()

        await channel.send(content=ping_role.mention, embed=embed)

    @listListener.before_loop
    async def before_my_task(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="listen", description="Sets up a Twitter list listener.")
    @app_commands.describe(twitter_list="What Twitter list should the bot listen to? (integer)")
    async def listen(self, interaction: discord.Interaction, twitter_list: str) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            twitter_list = int(twitter_list)
        except:
            embed = discord.Embed(title="Listener", description=f"**{twitter_list}** is not a valid integer!", color=discord.Color.red())
            await interaction.followup.send(embed=embed)
            return

        async with aiosqlite.connect('database.db') as db:

            full_categories = 0
            not_full = None

            for category in list_categories:
                channel = self.bot.get_channel(category)
                if channel:
                    if len(channel.channels) == 50:
                        full_categories += 1
                    else:
                        not_full = channel
                        break
            
            if full_categories == len(list_categories):
                embed = discord.Embed(title="Listener", description=f"All listening categories are full, please contact an admin.", color=discord.Color.red())
                await interaction.followup.send(embed=embed)
                return

            cursor = await db.execute('SELECT * FROM lists WHERE list=?', (twitter_list,))
            username_in_db = await cursor.fetchone()

            if username_in_db is not None:
                embed = discord.Embed(title="Listener", description=f"**{twitter_list}** is already in the database.", color=discord.Color.red())
                await interaction.followup.send(embed=embed)
                return
            
            tweets = [tweet async for tweet in api.list_timeline(twitter_list, limit=1)]

            if not tweets:
                embed = discord.Embed(title="Listener", description=f"**{twitter_list}** is either an invalid Twitter list or there's no tweets in it!", color=discord.Color.red())
                await interaction.followup.send(embed=embed)
                return

            tweet_list = json.dumps([])

            channel = await not_full.create_text_channel(name=f"{twitter_list}")

            await db.execute('INSERT INTO lists VALUES (?,?,?);', (twitter_list, channel.id, tweet_list))
            await db.commit()

            embed = discord.Embed(title="Listener", description=f"**{twitter_list}** is now being listened for new tweets.", color=discord.Color.from_str(embed_color))
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="unlisten", description="Removes a Twitter list listener.")
    @app_commands.describe(twitter_list="What Twitter list should the bot no longer listen to? (integer)")
    async def unlisten(self, interaction: discord.Interaction, twitter_list: Optional[str]) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            twitter_list = int(twitter_list)
        except:
            embed = discord.Embed(title="Listener", description=f"**{twitter_list}** is not a valid integer!", color=discord.Color.red())
            await interaction.followup.send(embed=embed)
            return

        async with aiosqlite.connect('database.db') as db:
            if twitter_list:
                cursor = await db.execute('SELECT * FROM lists WHERE list=?', (twitter_list,))
                list_in_db = await cursor.fetchone()

                if not list_in_db:
                    embed = discord.Embed(title="Listener", description=f"**{twitter_list}** is not in the database.", color=discord.Color.red())
                    await interaction.followup.send(embed=embed)
                    return

                channel = self.bot.get_channel(list_in_db[1])
                
                await db.execute('DELETE FROM lists WHERE list=?', (twitter_list, ))
                await db.commit()
            else:
                cursor = await db.execute('SELECT * FROM lists WHERE channel_id=?', (interaction.channel.id,))
                channel_in_db = await cursor.fetchone()

                if not channel_in_db:
                    embed = discord.Embed(title="Listener", description=f"**{interaction.channel.mention}** is not in the database.", color=discord.Color.red())
                    await interaction.followup.send(embed=embed)
                    return

                twitter_list = channel_in_db[0]
                channel = self.bot.get_channel(channel_in_db[1])

                await db.execute('DELETE FROM lists WHERE channel_id=?', (interaction.channel.id, ))
                await db.commit()

            embed = discord.Embed(title="Listener", description=f"**{twitter_list}** is no longer being listened to for new tweets.", color=discord.Color.red())
            if channel:
                embed.set_footer(text="Channel deleting in 5 seconds.")
            await interaction.followup.send(embed=embed)

            if channel:
                await asyncio.sleep(5)
                await channel.delete()

async def setup(bot):
    await bot.add_cog(ListsCog(bot))