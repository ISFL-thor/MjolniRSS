import discord
from discord.ext import tasks, commands
import feedparser
import json
import logging
import re
import asyncio
import aiohttp
import sqlite3
import random
import html
from html import unescape
from html.parser import HTMLParser
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Set the logging level to INFO

# Create a formatter
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')

# Create a file handler and set its level to INFO
file_handler = logging.FileHandler('bot_log.txt')  # This will log to a file named "bot_log.txt"
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Create a stream handler (for console logging) and set its level to INFO
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

with open('config.json', 'r') as f:
    CONFIG = json.load(f)

TOKEN = CONFIG['token']
FEEDS = CONFIG['predefined_feeds']

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True


# Create a new SQLite database or connect to existing one
conn = sqlite3.connect('bot_data.db')
cursor = conn.cursor()

# Create a table for posted_links if it doesn't exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS posted_links (
    feed_url TEXT PRIMARY KEY,
    links TEXT
)
''')
conn.commit()
cursor.execute('''
CREATE TABLE IF NOT EXISTS feeds (
    feed_url TEXT,
    guild_id TEXT,
    channel_id TEXT,
    role_id TEXT,
    color TEXT,
    title_template TEXT,
    description_template TEXT,
    PRIMARY KEY(feed_url, guild_id)
)
''')
conn.commit()

bot = commands.Bot(command_prefix='!', intents=intents)

# Use a set to keep track of entry links that have been posted
posted_links = set()


link_emoji_map = {
    # SHL Teams - SHL General
    "https://simulationhockey.com/images/smilies/stampede.png": "<:stampede:604776491158470666>",
    "https://simulationhockey.com/images/smilies/dragonsnew.png": "<:Dragons:832486991496609816>",
    "https://simulationhockey.com/images/smilies/blizzard.png": "<:Blizzard:829951660805324841>",
    "https://simulationhockey.com/images/smilies/steelhawks.png": "<:steelhawks:604352700238528532>",
    "https://simulationhockey.com/images/smilies/panthers-new.png": "<:Panthers:832487036983967784>",
    "https://simulationhockey.com/images/smilies/Rage-Emote.png": "<:rage:604353688286265385>",
    "https://simulationhockey.com/images/smilies/monarchs.png": "<:Monarchs:829951688797454357>",
    "https://simulationhockey.com/images/smilies/wolfpack4.png": "<:Wolfpack:832487080030371841>",
    "https://simulationhockey.com/images/smilies/pride-new.png": "<:pride:604352963418390555>",
    "https://simulationhockey.com/images/smilies/barracuda-new.png": "<:Barracuda:829951715473883147>",
    "https://simulationhockey.com/images/smilies/renegades.png": "<:renegades:604354480649142282>",
    "https://simulationhockey.com/images/smilies/toronto2.png": "<:NorthStars:1086789437045870592>",
    "https://simulationhockey.com/images/smilies/platoon2.png": "<:Platoon:829951556169629706>",
    "https://simulationhockey.com/images/smilies/auroranew.png": "<:Aurora:992253411301019668>",
    "https://simulationhockey.com/images/smilies/syndicate2.png": "<:Syndicate:829951629654622228>",
    "https://simulationhockey.com/images/smilies/specters.png": "<:specters:604352928647479306>",
    "https://simulationhockey.com/images/smilies/argonauts.png": "<:Argonauts:829951702748233800>",
    "https://simulationhockey.com/images/smilies/inferno.png": "<:Inferno:829949803299209226>",
    "https://simulationhockey.com/images/smilies/forge.png": "<:Forge:1067316544897552454>",
    "https://simulationhockey.com/images/smilies/Patriotesnew.png": "<:Patriotes:991509441465810944>",
    # SMJHL Teams - SHL General
    "https://simulationhockey.com/images/smilies/falcons2.png": "<:Falcons:829958086713802782>",
    "https://simulationhockey.com/images/smilies/timber.png": "<:Timber:829958772084441098>",
    "https://simulationhockey.com/images/smilies/kraken.png": "<:Kraken:956735648964948038>",
    "https://simulationhockey.com/images/smilies/scarecrows2.png": "<:Scarecrows:956738082852462592>",
    "https://simulationhockey.com/images/smilies/raptors-new.png": "<:Raptors:829958769164812288>",
    "https://simulationhockey.com/images/smilies/knights2.png": "<:Knights:956728074605572135>",
    "https://simulationhockey.com/images/smilies/armada2.png": "<:Armada:829958769135583242>",
    "https://simulationhockey.com/images/smilies/whalers2.png": "<:whalers:1140696580580712478>",
    "https://simulationhockey.com/images/smilies/berserkers.png": "<:Berserkers:829958772104888320>",
    "https://simulationhockey.com/images/smilies/malamutes.png": "<:Malamutes:970738688332025886>",
    "https://simulationhockey.com/images/smilies/citadelles.png": "<:Citadelles:829958771606290513>",
    "https://simulationhockey.com/images/smilies/battleborn-new.png": "<:Battleborn:956738985353412608>",
    "https://simulationhockey.com/images/smilies/silvertips.png": "<:Grizzlies:918196555155116034>",
    "https://simulationhockey.com/images/smilies/elk.png": "<:Elk:918196554794430487>",
    # IIHF Teams - SHL General
    "https://simulationhockey.com/images/smilies/canada.png": ":flag_ca:",
    "https://simulationhockey.com/images/smilies/czechia.png": ":flag_cz:",
    "https://simulationhockey.com/images/smilies/finland.png": ":flag_fi:",
    "https://simulationhockey.com/images/smilies/france.png": ":flag_fr:",
    "https://simulationhockey.com/images/smilies/germany.png": ":flag_de:",
    "https://simulationhockey.com/images/smilies/ireland.png": ":flag_ie:",
    "https://simulationhockey.com/images/smilies/japan3.png": ":flag_jp:",
    "https://simulationhockey.com/images/smilies/latvia.png": ":flag_lv:",
    "https://simulationhockey.com/images/smilies/norway.jpg": ":flag_no:",
    "https://simulationhockey.com/images/smilies/russia.png": ":flag_ru:",
    "https://simulationhockey.com/images/smilies/sweden.png": ":flag_se:",
    "https://simulationhockey.com/images/smilies/switzerland2.png": ":flag_ch:",
    "https://simulationhockey.com/images/smilies/uk.png": ":flag_gb:",
    "https://simulationhockey.com/images/smilies/usa.png": ":flag_us:",
    "https://simulationhockey.com/images/smilies/world.png": ":earth_americas:",
    # ISFL Teams - Management Server
    "https://forums.sim-football.com/images/smilies/isfl/BAL_thumb.png": "<:hawks:844368870097027103>",
    "https://forums.sim-football.com/images/smilies/isfl/BER_thumb.png": "<:firesalamanders:758509150832951297>",
    "https://forums.sim-football.com/images/smilies/isfl/CHI_thumb.png": "<:butchers:714662621273653338>",
    "https://forums.sim-football.com/images/smilies/isfl/COL_thumb.png": "<:yeti:714662885434982411>",
    "https://forums.sim-football.com/images/smilies/isfl/CTC_thumb.png": "<:crash:1169443820795068466>",
    "https://forums.sim-football.com/images/smilies/isfl/SAR_thumb.png": "<:sailfish:1169445556649738332>",
    "https://i.imgur.com/CrcVfke.png": "<:wraiths:1216955319901487235>",
    "https://forums.sim-football.com/images/smilies/isfl/ARI_thumb.png": "<:outlaws:714662565950783510>",
    "https://forums.sim-football.com/images/smilies/isfl/AUS_thumb.png": "<:copperheads:758506174907416656>",
    "https://forums.sim-football.com/images/smilies/isfl/HON_thumb.png": "<:hahalua:716144808464220232>",
    "https://forums.sim-football.com/images/smilies/isfl/OCO_thumb.png": "<:otters:1169444728673148958>",
    "https://forums.sim-football.com/images/smilies/isfl/NOLA_thumb.png": "<:secondline:714662827599593474>",
    "https://forums.sim-football.com/images/smilies/isfl/NYS_thumb.png": "<:silverbacks:758507657631498288>",
    "https://forums.sim-football.com/images/smilies/isfl/SJS_thumb.png": "<:sabercats:1169445091123937460>",
    # DSFL Teams - Management Server
    "https://forums.sim-football.com/images/smilies/isfl/DAL_thumb.png": "<:birddogs:758506247010910272>",
    "https://forums.sim-football.com/images/smilies/isfl/MBB_thumb.png": "<:buccaneers:1169444159724195991>",
    "https://forums.sim-football.com/images/smilies/isfl/NOR_thumb.png": "<:seawolves:1169233534347657216>",
    "https://forums.sim-football.com/images/smilies/isfl/TIJ_thumb.png": "<:luchadores:926162485025845288>",
    "https://forums.sim-football.com/images/smilies/isfl/KCC_thumb.png": "<:coyotes:926159762771542036>",
    "https://forums.sim-football.com/images/smilies/isfl/LON_thumb.png": "<:royals:714662776328421487>",
    "https://forums.sim-football.com/images/smilies/isfl/MIN_thumb.png": "<:greyducks:926161154936549386>",
    "https://forums.sim-football.com/images/smilies/isfl/POR_thumb.png": "<:pythons:926162167978405999>",
    "https://forums.sim-football.com/images/smilies/isfl/ISFL_logo.png": "<:ISFL:732057448558493766>",
    "https://i.imgur.com/zVJYj6b.png": "<:DSFL:1169234030768693338>"
}


def convert_to_discord_format(text, link_emoji_map):
    logger.debug(f"Initial text: {text}")

    # Convert common BBCode to Discord Markdown
    text = re.sub(r'\[b](.*?)\[/b]', r'**\1**', text)
    text = re.sub(r'\[i](.*?)\[/i]', r'*\1*', text)
    text = re.sub(r'\[u](.*?)\[/u]', r'__\1__', text)

    # Adjusted to keep the URL and discard the tags
    text = re.sub(r'\[url=.*?](.*?)\[/url]', r'\1', text)

    # Convert custom tags
    text = re.sub(r'<span class="mycode_b".*?>(.*?)</span>', r'**\1**', text)
    text = re.sub(r'<a class="mentionme_mention".*?>(.*?)</a>', r'\1', text)

    # Extract and display just the URL from img tags
    text = re.sub(r'\[img.*?](.*?)\[/img]', r'\1', text)  # Handle BBCode img tags
    text = re.sub(r'<img.*?src="(.*?)".*?>', r'\1', text)  # Handle HTML img tags

    logger.info(f"Text after tag removal: {text}")

    # Remove alignment tags
    text = re.sub(r'\[div align=.*?]', '', text)

    # Replace only non-Discord emoji HTML tags
    def replace_non_discord_html_tags(match):
        if match.group(0).startswith('<:') and match.group(0).endswith('>'):
            return match.group(0)  # Preserve Discord emoji tags
        else:
            return ''  # Remove other HTML tags

    # Use the custom function in the regular expression substitution
    text = re.sub(r'<.*?>', replace_non_discord_html_tags, text)

    logger.debug(f"Text after HTML processing: {text}")

    # Replace specific links with emojis as the last step
    for link, emoji in link_emoji_map.items():
        if link in text:
            logger.debug(f"Attempting to replace link {link} with emoji {emoji}")
            updated_text = text.replace(link, emoji)
            if updated_text != text:
                logger.debug(f"Successfully replaced link {link} with emoji {emoji}")
                text = updated_text
            else:
                logger.debug(f"Failed to replace link {link} with emoji {emoji}")
        else:
            logger.debug(f"Link {link} not found in text, unable to replace with emoji {emoji}")

    logger.debug(f"Final processed text: {text}")
    return text


def load_feeds_from_db():
    cursor.execute("SELECT * FROM feeds")
    data = cursor.fetchall()

    feeds_dict = {}
    for feed_url, _, channel_id, role_id, color, title_template, description_template in data:
        feed_data = {
            "channel_id": channel_id,
            "role_id": role_id,
            "color": color,
            "title_template": title_template,
            "description_template": description_template
        }

        if feed_url in feeds_dict:
            feeds_dict[feed_url].append(feed_data)
        else:
            feeds_dict[feed_url] = [feed_data]

    return feeds_dict


# Load feeds once when the script is run
FEEDS = load_feeds_from_db()
logger.info(f"Loaded feeds: {FEEDS}")


class TruncateHTMLParser(HTMLParser):
    def __init__(self, max_length):
        super().__init__()
        self.max_length = max_length
        self.truncated = ''
        self.current_length = 0
        self.truncate_at = None

    def handle_starttag(self, tag, attrs):
        if self.current_length < self.max_length:
            self.truncated += self.get_starttag_text()

    def handle_endtag(self, tag):
        if self.current_length < self.max_length:
            self.truncated += f"</{tag}>"

    def handle_data(self, data):
        if self.current_length < self.max_length:
            remaining_length = self.max_length - self.current_length
            if len(data) > remaining_length:
                self.truncated += data[:remaining_length] + "..."
                self.current_length = self.max_length
                self.truncate_at = self.getpos()
            else:
                self.truncated += data
                self.current_length += len(data)


class UsernameExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.username = None
        self.capture_username = False

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            attrs_dict = dict(attrs)
            # Check if 'href' contains "member.php?action=profile"
            if 'href' in attrs_dict and "member.php?action=profile" in attrs_dict['href']:
                self.capture_username = True

    def handle_data(self, data):
        if self.capture_username:
            self.username = data
            self.capture_username = False

    def handle_endtag(self, tag):
        if tag == 'a':
            self.capture_username = False


def extract_username_from_rss_entry(raw_content):
    parser = UsernameExtractor()
    parser.feed(raw_content)
    return parser.username


def truncate_html_with_ellipsis(html: str, length: int) -> str:
    parser = TruncateHTMLParser(length)
    parser.feed(html)
    return parser.truncated


def load_posted_links():
    cursor.execute("SELECT * FROM posted_links")
    data = cursor.fetchall()
    return {feed_url: json.loads(links) for feed_url, links in data}


def save_posted_links(data):
    for feed_url, links in data.items():
        cursor.execute("INSERT OR REPLACE INTO posted_links (feed_url, links) VALUES (?, ?)", (feed_url, json.dumps(links)))
    conn.commit()


def get_feed_group_and_name(feed_url):
    # Reverse lookup the feed group and feed name using the feed URL.
    for league, feeds in CONFIG["predefined_feeds"].items():
        for feed_group, feed_details in feeds.items():
            if isinstance(feed_details, dict):
                if feed_url in feed_details.values():
                    return feed_group, feed_url
                for feed_name, details in feed_details.items():
                    if details["url"] == feed_url:
                        return feed_group, feed_name
    return None, None


def get_feed_info_from_url(feed_url):
    for league, groups in CONFIG["predefined_feeds"].items():
        for group, feeds in groups.items():
            for feed_name, details in feeds.items():
                if details["url"] == feed_url:
                    return league, feed_name
    return None, None  # If not found, return None for both


async def fetch_feed(session, feed_url):
    async with session.get(feed_url) as response:
        return await response.text(), feed_url


async def send_embed_to_channel(channel, role_mention, embed):
    try:
        # Prepare the content to be sent. If there's a role mention, it will be added after the embed.
        content = role_mention or None
        await channel.send(content=content, embed=embed)
    except discord.Forbidden:
        logger.info(f"Permission error: Unable to send message to channel {channel.id} in server"
                       f" {channel.guild.name}. Skipping this server.")
    except Exception as e:
        logger.info(f"Error occurred while sending message to channel {channel.id} in server"
                     f" {channel.guild.name}. Error: {e}")


@bot.event
async def on_ready():
    global posted_links, FEEDS
    posted_links = load_posted_links()
    FEEDS = load_feeds_from_db()
    activity = discord.Game(name="with RSS feeds", type=3)
    await bot.change_presence(activity=activity)
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    rss_check.start()  # Start the RSS check loop


@tasks.loop(seconds=180)
async def rss_check():
    global posted_links
    logger.info("Checking RSS feeds...")

    logger.info(f"FEEDS dictionary: {FEEDS}")

    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[fetch_feed(session, feed_url) for feed_url in FEEDS.keys()])

        for feed_text, feed_url in results:
            try:
                feed = feedparser.parse(feed_text)
                feed_data = FEEDS.get(feed_url)

                league, feed_name = get_feed_info_from_url(feed_url)
                logger.info(f"Checking {league or 'Unknown League'} feed: {feed_name}")

                if not feed.entries:
                    logger.info(f"No entries found for feed: {feed_url}")
                    continue

                tasks_to_gather = []
                for entry in feed.entries:
                    if entry.link not in posted_links.get(feed_url, []):
                        # Extract author information
                        author_info = entry.get('author') or (
                            entry.get('authors')[0]['name'] if 'authors' in entry else None)
                        logger.info(f"Author field content: {author_info}")

                        if author_info:
                            username = extract_username_from_rss_entry(author_info)
                            logger.info(f"Extracted username: {username}")
                        else:
                            username = None
                            logger.info("No author information found in RSS entry.")

                        truncated_summary = truncate_html_with_ellipsis(entry.summary, 1000)
                        converted_summary = convert_to_discord_format(truncated_summary, link_emoji_map)

                        feed_data_list = feed_data if isinstance(feed_data, list) else [feed_data]
                        for feed_setting in feed_data_list:
                            embed = discord.Embed(
                                title=convert_to_discord_format(feed_setting['title_template'].format(
                                    entry_title=entry.title,
                                    entry_link=entry.link,
                                    author=username
                                ), link_emoji_map),  # Added link_emoji_map as an argument here
                                description=convert_to_discord_format(feed_setting['description_template'].format(
                                    entry_link=entry.link,
                                    entry_title=entry.title,
                                    entry_summary=converted_summary,  # Use converted_summary here
                                    author=username
                                ), link_emoji_map),  # Added link_emoji_map as an argument here
                                color=int(feed_setting['color'].lstrip('#'), 16)
                            )
                            logger.info(f"Created embed for entry link: {entry.link}")

                            channel_id = int(feed_setting['channel_id'])
                            channel = bot.get_channel(channel_id)
                            if channel:
                                logger.info(f"Fetched channel with ID: {channel_id}")
                                role_id = feed_setting.get('role_id')
                                role_mention = f'<@&{role_id}>' if role_id else None
                                task = send_embed_to_channel(channel, role_mention, embed)
                                tasks_to_gather.append(task)
                                if feed_url not in posted_links:
                                    posted_links[feed_url] = []
                                posted_links[feed_url].append(entry.link)
                            else:
                                logger.warning(f"Channel with ID {channel_id} not found!")

                if tasks_to_gather:
                    await asyncio.gather(*tasks_to_gather)

            except Exception as e:
                logger.error(f"An error occurred while processing feed {feed_url}: {e}")

        save_posted_links(posted_links)


@rss_check.before_loop
async def before_rss_check():
    logger.info("Waiting until bot is ready...")
    await bot.wait_until_ready()


@bot.slash_command(name="addfeed", description="Adds a predefined RSS feed by group and name.")
@discord.option(name='league', description="The name of the league you're adding notifications for "
                                           "(e.g., ISFL, SHL).", type=str, choices=["ISFL", "SHL"])
@discord.option(name='channel_name', description="The name of the channel to send notifications to.", type=str)
@discord.option(name='feed_group', description="Use this if you want to add a group of related feeds"
                                               " (e.g., Media, TPE, Budget).", type=str, required=False,
                choices=["Media", "TPE", "Budget", "Jobs", "Announcements"])
@discord.option(name='feed_name', description="Use this if you only want one specific feed from within a group"
                                              " (e.g. PointTasks, Jobs)", type=str, required=False)
@discord.option(name='role_name', description="The name of the role to mention (optional).", type=str, required=False)
async def add_predefined_feed(ctx, league: str, channel_name: str, feed_group: str = None, feed_name: str = None,
                              role_name: str = None):
    logger.info(f"Received command with params - league: {league}, channel_name: {channel_name}, feed_group:"
                f" {feed_group}, feed_name: {feed_name}, role_name: {role_name}")

    # Parse Channel Tag
    if channel_name.startswith("<#") and channel_name.endswith(">"):
        try:
            channel_id = int(channel_name[2:-1])  # Extracting the ID
        except ValueError:
            logger.error(f"Invalid channel tag format: {channel_name}")
            await ctx.respond("Invalid channel tag format.")
            return

        channel = ctx.guild.get_channel(channel_id)
        if not channel:
            logger.warning(f"Channel with ID '{channel_id}' not found in the server.")
            await ctx.respond(f"Channel with ID '{channel_id}' not found!")
            return
        logger.info(f"Channel found with ID: {channel_id}, Name: {channel.name}")
    else:
        channel_name = channel_name.lstrip("#").replace(" ", "-").lower()
        matching_channels = [ch for ch in ctx.guild.text_channels if ch.name.lower() == channel_name]

        if not matching_channels:
            logger.warning(f"No channel found with name: '{channel_name}'")
            await ctx.respond(f"Channel named '{channel_name}' not found!")
            return

        if len(matching_channels) > 1:
            logger.warning(f"Multiple channels found with the same name: '{channel_name}'")
            await ctx.respond(f"Multiple channels named '{channel_name}' found! Please provide a unique channel name.")
            return

        channel = matching_channels[0]
        channel_id = channel.id
        logger.info(f"Channel found with name: {channel.name}, ID: {channel_id}")

    # Parse Role Mention
    role_id = None
    if role_name:
        if role_name.startswith("<@&") and role_name.endswith(">"):
            try:
                role_id = int(role_name[3:-1])  # Extracting the ID
            except ValueError:
                logger.error(f"Invalid role tag format: {role_name}")
                await ctx.respond("Invalid role tag format.")
                return

            role = ctx.guild.get_role(role_id)
            if not role:
                logger.warning(f"Role with ID '{role_id}' not found in the server.")
                await ctx.respond(f"Role with ID '{role_id}' not found in this server!")
                return
            logger.info(f"Role found with ID: {role_id}, Name: {role.name}")
        else:
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if role:
                role_id = role.id
                logger.info(f"Role found with name: {role.name}, ID: {role_id}")
            else:
                logger.warning(f"Role '{role_name}' not found in the server.")
                await ctx.respond(f"Role '{role_name}' not found in this server!")
                return

    # Perform a case-insensitive search for league
    league_key = next((k for k in CONFIG["predefined_feeds"] if k.lower() == league.lower()), None)
    if not league_key:
        await ctx.respond(f"'{league}' does not exist!")
        logger.warning(f"Attempted to add non-existent league '{league}'")
        return
    league = league_key  # set the correct case from the dictionary
    logger.info(f"Matched league: {league}")

    # Perform a case-insensitive search for feed_group
    if feed_group:
        feed_group_key = next((k for k in CONFIG["predefined_feeds"][league] if k.lower() == feed_group.lower()), None)
        if not feed_group_key:
            await ctx.respond(f"'{feed_group}' is not a valid feed group for the '{league}' league.")
            return
        feed_group = feed_group_key  # set the correct case from the dictionary
        logger.info(f"Matched feed group: {feed_group}")

    # Search for the feed_name across all groups if feed_group isn't provided
    if feed_name and not feed_group:
        for grp, feeds in CONFIG["predefined_feeds"][league].items():
            if feed_name.lower() in [name.lower() for name in feeds.keys()]:
                feed_group = grp
                break
        logger.info(f"Derived feed group from feed name: {feed_group}")

    # Perform a case-insensitive search for feed_name within the identified feed_group
    if feed_name:
        feed_name_key = next((k for k in CONFIG["predefined_feeds"][league][feed_group] if k.lower() == feed_name.lower()), None)
        if not feed_name_key:
            await ctx.respond(f"'{feed_name}' is not a valid feed name for the '{league}' league.")
            return
        feed_name = feed_name_key  # set the correct case from the dictionary
        logger.info(f"Matched feed name: {feed_name}")

    def add_feed_to_server(name, details):
        feed_url = details["url"]
        feed_color = details["color"]
        feed_title_template = details["title_template"]
        feed_description_template = details["description_template"]
        # Create the feed configuration
        FEEDS[feed_url] = {
            "channel_id": channel_id,
            "color": feed_color,
            "title_template": feed_title_template,
            "description_template": feed_description_template,
            "role_id": role_id
        }
        # Save to the database
        cursor.execute(
            "INSERT OR REPLACE INTO feeds (feed_url, guild_id, channel_id, role_id, color, "
            "title_template, description_template) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (feed_url, str(ctx.guild.id), channel_id, role_id, feed_color, feed_title_template,
             feed_description_template))
        conn.commit()
        logger.info(f"Added feed {name} from {league} to {channel.name} - ({channel.id}) in {ctx.guild.name} -"
                    f" ({ctx.guild.id})")

    # If only feed_name is provided (or both feed_group and feed_name are provided)
    if feed_name:
        if not feed_group:
            for grp, feeds in CONFIG["predefined_feeds"][league].items():
                if feed_name in feeds:
                    feed_group = grp
                    break
            # Check if feed_group is still None after the loop
            if not feed_group:
                await ctx.respond(f"'{feed_name}' is not a valid feed name for the '{league}' league.")
                return
        feed_name_key = next((k for k in CONFIG["predefined_feeds"][league][feed_group]
                              if k.lower() == feed_name.lower()), None)
        if not feed_name_key:
            await ctx.respond(f"'{feed_name}' is not a valid feed name for the '{league}'"
                              f" league in the '{feed_group}' group.")
            return
        feed_name = feed_name_key  # set the correct case from the dictionary
        details = CONFIG["predefined_feeds"][league][feed_group][feed_name]
        add_feed_to_server(feed_name, details)
    # If only feed_group is provided without feed_name
    elif feed_group:
        for name, details in CONFIG["predefined_feeds"][league][feed_group].items():
            add_feed_to_server(name, details)
    # If neither feed_group nor feed_name is provided, add the entire group
    else:
        for feed_grp, feeds in CONFIG["predefined_feeds"][league].items():
            for name, details in feeds.items():
                add_feed_to_server(name, details)

    if feed_group and role_name:
        await ctx.respond(f"Added feed(s) from {league} - {feed_group} to {channel.name}"
                          f" with role mention {role_name}.")
    elif feed_group:
        await ctx.respond(f"Added feed(s) from {league} - {feed_group} to {channel.name}.")
    elif role_name:
        await ctx.respond(f"Added feed(s) from {league} to {channel.name} with role mention {role_name}.")
    else:
        await ctx.respond(f"Added feed(s) from {league} to {channel.name}.")

    # Try to send a confirmation message to the requested channel in an embed
    try:
        confirmation_msg = "This channel has been set up for RSS feed notifications."
        embed = discord.Embed(title="Confirmation", description=confirmation_msg, color=0x3498db)
        await channel.send(embed=embed)
    except discord.Forbidden:
        error_msg = (f"I don't have permission to send messages or embeds in {channel.name}. Please adjust the"
                     f" permissions to ensure I have access to view/send messages/embed links and mention roles in "
                     f"that specific channel. Your feeds have been subscribed to and will work after fixing the "
                     f"permissions.")
        await ctx.respond(error_msg)


@bot.slash_command(name="removefeed", description="Remove all feeds from the specified channel.")
@discord.option(name='channel_name', description="The name of the channel from which to remove the feeds.", type=str)
async def remove_feed(ctx, channel_name: str):
    if ctx.author.guild_permissions.manage_guild:

        # Parse Channel Tag
        if channel_name.startswith("<#") and channel_name.endswith(">"):
            try:
                channel_id = int(channel_name[2:-1])  # Extracting the ID
            except ValueError:
                await ctx.respond("Invalid channel tag format.")
                return

            channel = ctx.guild.get_channel(channel_id)
            if not channel:
                await ctx.respond(f"Channel with ID '{channel_id}' not found!")
                return
        else:
            # Convert spaces to dashes and then convert the channel name to lowercase for plain text names
            channel_name = channel_name.replace(" ", "-").lower()
            matching_channels = [ch for ch in ctx.guild.channels if ch.name.lower() == channel_name]

            if len(matching_channels) == 0:
                await ctx.respond(f"Channel named {channel_name} not found!")
                return
            elif len(matching_channels) > 1:
                await ctx.respond(f"There are multiple channels with the name {channel_name}. Please specify uniquely.")
                return

            # If we're here, we have a unique match
            channel_id = matching_channels[0].id

        # Remove from the database
        cursor.execute("DELETE FROM feeds WHERE guild_id = ? AND channel_id = ?", (str(ctx.guild.id), str(channel_id)))
        conn.commit()

        await ctx.respond(f"All feeds removed from {channel_name} for this server.")
    else:
        await ctx.respond("You don't have permission to remove feeds!")


@bot.slash_command(name="listfeeds", description="Lists the available RSS feeds that you can use.")
@discord.option(name='league', description="The name of the league you're adding notifications for "
                                           "(e.g., ISFL, SHL).", type=str, choices=["ISFL", "SHL"])
async def list_feeds(ctx, league: str):
    feed_list = []
    predefined_feeds = CONFIG["predefined_feeds"]

    if league and league in predefined_feeds:
        feeds = predefined_feeds[league]
        for feed_name, feed_details in feeds.items():
            if isinstance(feed_details, dict) and "url" not in feed_details:
                nested_feeds = "\n".join(feed_details.keys())
                feed_list.append(f"**{feed_name}**:\n{nested_feeds}\n")
            else:
                feed_list.append(f"{feed_name}\n")
    else:
        for league, feeds in predefined_feeds.items():
            for feed_name, feed_details in feeds.items():
                if isinstance(feed_details, dict) and "url" not in feed_details:
                    nested_feeds = "\n".join(feed_details.keys())
                    feed_list.append(f"**{feed_name}**:\n{nested_feeds}\n")
                else:
                    feed_list.append(f"{feed_name}\n")

    await ctx.respond(f"Available feeds:\n{''.join(feed_list)}")


@bot.slash_command(name="checkfeeds", description="Check the current RSS subscriptions for this server.")
async def check_subscriptions(ctx):
    if ctx.author.guild_permissions.manage_guild:
        # Fetch the subscribed feeds for the current server
        cursor.execute("SELECT feed_url, channel_id, role_id, color, title_template, description_template "
                       "FROM feeds WHERE guild_id = ?", (str(ctx.guild.id),))
        feeds = cursor.fetchall()

        # If there are no subscriptions for the server
        if not feeds:
            await ctx.respond("This server has no RSS subscriptions!")
            return

        # Create an embed
        embed = discord.Embed(title="Current RSS Subscriptions", color=0x3498db)

        for feed_url, channel_id, role_id, color, title_template, description_template in feeds:
            league, feed_name = get_feed_info_from_url(feed_url)
            feed_group, _ = get_feed_group_and_name(feed_url)
            channel = ctx.guild.get_channel(int(channel_id))
            role = ctx.guild.get_role(int(role_id)) if role_id else None

            # Add the feed details to the embed
            feed_details = (f"Channel: {channel.name if channel else 'Channel not found'}\nRole:"
                            f" {role.name if role else 'None'}")
            embed.add_field(name=f"{league} > {feed_group} > {feed_name}", value=feed_details, inline=False)

        await ctx.respond(embed=embed)
    else:
        await ctx.respond("You don't have permission to check subscriptions!")


@bot.slash_command(name="help", description="Displays help for all commands.")
async def help_command(ctx):
    # Create an embed
    embed = discord.Embed(title="Help Guide", description="Here are the available commands and how to use them:",
                          color=0x3498db)

    # Add a field for the /addfeed command
    embed.add_field(
        name="__/addfeed__",
        value=("**Description:** Adds a predefined RSS feed by group and name to a specified channel. "
               "If a role is mentioned, it will be pinged whenever the feed updates.\n"
               "**Usage:** `/addfeed <league> <channel_name> [feed_group] [feed_name] [role_name]`\n"
               "• `league`: The name of the league (e.g., ISFL, SHL). Required.\n"
               "• `channel_name`: The name of the channel. Required.\n"
               "• `feed_group`: The group of related feeds (e.g., Media, TPE). Optional.\n"
               "• `feed_name`: A specific feed from a group (e.g., PointTasks). Optional.\n"
               "• `role_name`: The name of the role to mention. Optional.\n"
               "Note: If only `feed_group` is provided, all feeds within that group will be added. If neither"
               " `feed_group` nor `feed_name` is provided, the entire group of feeds for the league will be added."),
        inline=False
    )

    # Add a field for the /removefeed command
    embed.add_field(
        name="__/removefeed__",
        value=("**Description:** Removes all RSS feeds from the specified channel.\n"
               "**Usage:** `/removefeed <channel_name>`\n"
               "• `channel_name`: The name of the channel from which to remove the feeds. Required."),
        inline=False
    )

    # Add a field for the /listfeeds command
    embed.add_field(
        name="__/listfeeds__",
        value=("**Description:** Lists all available predefined RSS feeds, organized by league and feed groups. "
               "The list format is `League > Group: Feed Name`. Use this format to help determine how to input values "
               "for the `/addfeed` command.\n"),
        inline=False
    )

    # Add a field for the /checkfeeds command
    embed.add_field(
        name="__/checkfeeds__",
        value=("**Description:** Checks the current RSS subscriptions for the server, showing which feeds are active in"
               " which channels and if any roles are pinged for those feeds."),
        inline=False
    )

    # Add a field for the /invite command
    embed.add_field(
        name="__/invite__",
        value="**Description:** Provides a link to invite the bot to another server.\n",
        inline=False
    )

    # Respond with the embed
    await ctx.respond(embed=embed)


@bot.slash_command(name="invite", description="Get the invite link for this bot.")
async def invite_command(ctx):
    link = "https://discord.com/api/oauth2/authorize?client_id=1164890740363628594&permissions=2147895296&scope=bot%20applications.commands"
    await ctx.respond(f"Invite the bot to a server you manage: {link}")


@bot.slash_command(name="serverlist", description="Displays a list of servers the bot is in.")
async def server_list(ctx):
    # Check if the user's ID matches the specified ID
    if ctx.author.id == 337055089489477643:
        guild_names = [guild.name for guild in bot.guilds]
        guild_list = "\n".join(guild_names)

        # Split the message into chunks if it's too long
        max_length = 1900
        for i in range(0, len(guild_list), max_length):
            chunk = guild_list[i:i+max_length]
            await ctx.respond(f"```\n{chunk}\n```")
    else:
        await ctx.respond("Only the bot creator has access to this command!")


@bot.slash_command(name="wiggle", description="~")
async def wiggle(ctx):
    # Generate a random number between 1 and 200
    rand_num = random.randint(1, 200)

    # 1/50 chance check
    if rand_num <= 4:
        await ctx.respond("https://cdn.discordapp.com/attachments/602893231621144588/1169105764003094610/"
                          "ezgif.com-gif-maker.gif?ex=656fe117&is=655d6c17&hm="
                          "531c5161dd44523e8cba364c83437f8dffcb46e74e011b5ff706ceec889a7856&")
    # 1/200 chance check
    elif rand_num == 69:
        await ctx.respond("https://cdn.discordapp.com/attachments/602893231621144588/1169106648174972949/"
                          "ezgif.com-gif-maker_1.gif?ex=656fe1e9&is=655d6ce9&hm="
                          "ce8cb94fd1991156291e027ab37288f5a8c66eff7aca0a361ff4bc1493460d38&")
    else:
        # Original image
        await ctx.respond("https://cdn.discordapp.com/emojis/1161116581909246052.gif?size=96&quality=lossless")
    return


bot.run(TOKEN)
