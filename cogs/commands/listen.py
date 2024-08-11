import discord
import aiosqlite
import yaml
import json
from discord import app_commands
from discord.ext import commands, tasks
from twscrape import API
from datetime import datetime

api = API()

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

guild_id = data["General"]["GUILD_ID"]
embed_color = data["General"]["EMBED_COLOR"]
on_job_role_id = data["Roles"]["ON_JOB_ROLE_ID"]
listening_categories = data["Listening_Categories"]

class ListenCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def cog_load(self):
        self.listenerLoop.start()

    @tasks.loop(seconds=60)
    async def listenerLoop(self):
        async with aiosqlite.connect('database.db') as db:
            guild = self.bot.get_guild(guild_id)
            on_job_role = guild.get_role(on_job_role_id)

            cursor = await db.execute('SELECT * FROM listeners')
            listeners = await cursor.fetchall()

            for listener in listeners:
                username = listener[0]
                channel_id = listener[1]
                tweets = listener[2]

                user = await api.user_by_login(username)
                channel = self.bot.get_channel(channel_id)
                tweet_list = json.loads(tweets)

                if not channel:
                    await db.execute('DELETE FROM listeners WHERE username=?', (username,))
                    await db.commit()
                    return

                tweets = [tweet async for tweet in api.user_tweets(user.id, limit=2)]

                if tweets:
                    tweet = tweets[0]
                    if tweet.url not in tweet_list:
                        await self.process_tweet(db, tweet, tweet_list, username, channel, on_job_role)
                    else:
                        if len(tweets) > 1:
                            tweet = tweets[1]
                            if tweet.url not in tweet_list:
                                await self.process_tweet(db, tweet, tweet_list, username, channel, on_job_role)

    async def process_tweet(self, db, tweet, tweet_list, username, channel, on_job_role):
        cursor = await db.execute('SELECT * FROM keywords')
        keywords = await cursor.fetchall()

        for keyword in keywords:
            if keyword[1] in tweet.rawContent:
                keyword_channel = self.bot.get_channel(keyword[0])
                if not keyword_channel:
                    await db.execute('DELETE FROM keywords WHERE keyword=?', (keyword[1],))
                    await db.commit()
                    continue

                embed = discord.Embed(title="Listener", description=f"""
[New Keyword Tweet By **{username}**]({tweet.url})

{tweet.rawContent}
""", color=discord.Color.from_str(embed_color))
                embed.set_author(name=username, icon_url=tweet.user.profileImageUrl)
                embed.timestamp = datetime.now()
                await keyword_channel.send(content=on_job_role.mention, embed=embed)

        tweet_list.append(tweet.url)

        updated_tweets = json.dumps(tweet_list)

        await db.execute('UPDATE listeners SET tweets=? WHERE username=?', (updated_tweets, username))
        await db.commit()

        embed = discord.Embed(title="Listener", description=f"""
[New Tweet By **{username}**]({tweet.url})

{tweet.rawContent}
""", color=discord.Color.from_str(embed_color))
        embed.set_author(name=username, icon_url=tweet.user.profileImageUrl)
        embed.timestamp = datetime.now()

        await channel.send(content=on_job_role.mention, embed=embed)

    @listenerLoop.before_loop
    async def before_my_task(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="listen", description="Sets up a Twitter listener.")
    @app_commands.describe(username="What Twitter account should the bot listen to?")
    async def listen(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        async with aiosqlite.connect('database.db') as db:

            full_categories = 0
            not_full = None

            for category in listening_categories:
                channel = self.bot.get_channel(category)
                if channel:
                    if len(channel.channels) == 50:
                        full_categories += 1
                    else:
                        not_full = channel
                        break
            
            if full_categories == len(listening_categories):
                embed = discord.Embed(title="Listener", description=f"All listening categories are full, please contact an admin.", color=discord.Color.red())
                await interaction.followup.send(embed=embed)
                return

            cursor = await db.execute('SELECT * FROM listeners WHERE username=?', (username,))
            username_in_db = await cursor.fetchone()

            if username_in_db is not None:
                embed = discord.Embed(title="Listener", description=f"**{username}** is already in the database.", color=discord.Color.red())
                await interaction.followup.send(embed=embed)
                return
            
            user = await api.user_by_login(username)
            if not user:
                embed = discord.Embed(title="Listener", description=f"**{username}** is an invalid Twitter username.", color=discord.Color.red())
                await interaction.followup.send(embed=embed)
                return

            tweet_list = json.dumps([])

            channel = await not_full.create_text_channel(name=f"{username}")

            await db.execute('INSERT INTO listeners VALUES (?,?,?);', (username, channel.id, tweet_list))
            await db.commit()

            embed = discord.Embed(title="Listener", description=f"**{username}** is now being listened for new tweets.", color=discord.Color.from_str(embed_color))
            await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ListenCog(bot))