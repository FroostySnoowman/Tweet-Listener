import discord
import asyncio
import yaml
import sys
from discord.ext import commands
from twscrape import API
from cogs.functions.db import check_tables

api = API()

with open('config.yml', 'r') as file:
    data = yaml.safe_load(file)

embed_color = data["General"]["EMBED_COLOR"]
activity = data["General"]["ACTIVITY"].lower()
doing_activity = data["General"]["DOING_ACTIVITY"]
streaming_activity_twitch_url = data["General"]["STREAMING_ACTIVITY_TWITCH_URL"]
status = data["General"]["STATUS"].lower()
token = data["General"]["TOKEN"]

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

if status == "online":
    _status = getattr(discord.Status, status)
elif status == "idle":
    _status = getattr(discord.Status, status)
elif status == "dnd":
    _status = getattr(discord.Status, status)
elif status == "invisible":
    _status = getattr(discord.Status, status)
else:
    sys.exit(f"""
{bcolors.FAIL}{bcolors.BOLD}ERROR:{bcolors.ENDC}
{bcolors.FAIL}Invalid Status: {bcolors.ENDC}{bcolors.OKCYAN}{status}{bcolors.ENDC}
{bcolors.OKBLUE}Valid Options: {bcolors.ENDC}{bcolors.OKGREEN}{bcolors.UNDERLINE}online{bcolors.ENDC}{bcolors.OKGREEN}, {bcolors.UNDERLINE}idle{bcolors.ENDC}{bcolors.OKGREEN}, {bcolors.UNDERLINE}dnd{bcolors.ENDC}{bcolors.OKGREEN}, or {bcolors.UNDERLINE}invisible{bcolors.ENDC}
{bcolors.OKGREEN}config.json {bcolors.OKCYAN}Line 7
""")

if activity == "playing":
    if doing_activity == "":
        sys.exit(f"""
{bcolors.FAIL}{bcolors.BOLD}ERROR:{bcolors.ENDC}
{bcolors.FAIL}Invalid Doing Activity: {bcolors.OKBLUE}It Must Be Set!
{bcolors.OKGREEN}config.json {bcolors.OKCYAN}Line 5
""")
    else:
        _activity = discord.Game(name=doing_activity)
elif activity == "watching":
    if doing_activity == "":
        sys.exit(f"""
{bcolors.FAIL}{bcolors.BOLD}ERROR:{bcolors.ENDC}
{bcolors.FAIL}Invalid Doing Activity: {bcolors.OKBLUE}It Must Be Set!
{bcolors.OKGREEN}config.json {bcolors.OKCYAN}Line 5
""")
    else:
        _activity = discord.Activity(name=doing_activity, type=discord.ActivityType.watching)
elif activity == "listening":
    if doing_activity == "":
        sys.exit(f"""
{bcolors.FAIL}{bcolors.BOLD}ERROR:{bcolors.ENDC}
{bcolors.FAIL}Invalid Doing Activity: {bcolors.OKBLUE}It Must Be Set!
{bcolors.OKGREEN}config.json {bcolors.OKCYAN}Line 5
""")
    else:
        _activity = discord.Activity(name=doing_activity, type=discord.ActivityType.listening)
elif activity == "streaming":
    if streaming_activity_twitch_url == "":
        sys.exit(f"""
{bcolors.FAIL}{bcolors.BOLD}ERROR:{bcolors.ENDC}
{bcolors.FAIL}Invalid Streaming Activity Twitch URL: {bcolors.OKBLUE}It Must Be Set!
{bcolors.OKGREEN}config.json {bcolors.OKCYAN}Line 6
""")
    elif not "https://twitch.tv/" in streaming_activity_twitch_url:
        sys.exit(f"""
{bcolors.FAIL}{bcolors.BOLD}ERROR:{bcolors.ENDC}
{bcolors.FAIL}Invalid Streaming Activity Twitch URL: {bcolors.OKBLUE}It Must Be A Valid Twitch URL!
{bcolors.OKGREEN}config.json {bcolors.OKCYAN}Line 6
""")
    else:
        _activity = discord.Streaming(name=doing_activity, url=streaming_activity_twitch_url)
else:
    sys.exit(f"""
{bcolors.FAIL}{bcolors.BOLD}ERROR:{bcolors.ENDC}
{bcolors.FAIL}Invalid Activity: {bcolors.ENDC}{bcolors.OKCYAN}{activity}{bcolors.ENDC}
{bcolors.OKBLUE}Valid Options: {bcolors.ENDC}{bcolors.OKGREEN}{bcolors.UNDERLINE}playing{bcolors.ENDC}{bcolors.OKGREEN}, {bcolors.UNDERLINE}watching{bcolors.ENDC}{bcolors.OKGREEN}, {bcolors.UNDERLINE}listening{bcolors.ENDC}{bcolors.OKGREEN}, or {bcolors.UNDERLINE}streaming{bcolors.ENDC}
{bcolors.OKGREEN}config.json {bcolors.OKCYAN}Line 4
""")

intents = discord.Intents.all()

initial_extensions = [
                      'cogs.commands.keyword',
                      'cogs.commands.listen',
                      'cogs.commands.unkeyword',
                      'cogs.commands.unlisten',
                      'cogs.functions.db'
                      ]

async def delete_accounts():
    for account in await api.pool.get_all():
        await api.pool.delete_accounts(account.username)

class TwitterListener(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or('.'), owner_ids=[503641822141349888, 790245191985659925], intents=intents, activity=_activity, status=_status)

    async def on_ready(self):

        print(f'Signed in as {self.user}')

        print('Checking local databases...')
        await check_tables()
        print('Check successful!')

        print('Attempting to sync commands...')
        await self.tree.sync()
        print('Succesfully synced slash commands!')

    async def setup_hook(self):
        with open('accounts.txt', 'r') as file:
            for line in file:
                try:
                    username, password, email, email_password = line.strip().split(':')
                    await api.pool.add_account(username, password, email, email_password)
                except Exception as e:
                    continue
        
        await api.pool.login_all()

        await asyncio.sleep(3)

        for extension in initial_extensions:
            await self.load_extension(extension)

client = TwitterListener()
client.remove_command('help')

client.run(token)