import discord
import random
from discord.ext import commands
from discord import Activity, ActivityType
import yt_dlp as youtube_dl
import asyncio
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import BOT_TOKEN, YOUTUBE_API_KEY, BOT_PREFIX, EMBEDCOLOR, BOT_ACTIVITY_TYPE, BOT_ACTIVITY_NAME, PLAYLIST_SONG_COUNT

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)

queue = []

command_prefix = bot.command_prefix
bot.remove_command('help')

@bot.event
async def on_ready():
    activity_type_mapping = {
        '0': None,
        '1': ActivityType.playing,
        '2': ActivityType.listening,
        '3': ActivityType.watching,
        '4': ActivityType.streaming,
        '5': ActivityType.competing
    }

    if BOT_ACTIVITY_TYPE in activity_type_mapping:
        activity_type = activity_type_mapping[BOT_ACTIVITY_TYPE]
    else:
        activity_type = None
    
    if activity_type is not None:
        await bot.change_presence(activity=Activity(type=activity_type, name=BOT_ACTIVITY_NAME))
        print(f'We have logged in as {bot.user.name} with activity presence')
    else:
        print(f'We have logged in as {bot.user.name}')

@bot.command(name='play', aliases=['p'])
async def play_music(ctx, *, query):
    try:
        channel = ctx.author.voice.channel
    except AttributeError:
        await ctx.send(embed=discord.Embed(
            title="",
            description=f"You need to be in a voice channel to use this command.",
            color=discord.Colour(int(EMBEDCOLOR, 16))
        ))
        return
    
    # used to check if the bot can join the voice channel
    if not channel.permissions_for(ctx.guild.me).connect:
        await ctx.send(embed=discord.Embed(
            title="",
            description=f"The bot can't join the voice channel.",
            color=discord.Colour(int(EMBEDCOLOR, 16))
        ))
        return

    # check if the bot is already in a vc in the same server
    voice_channel = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    # if the bot is already in a vc, disconnect and join ur channel (will change this in the future)
    if voice_channel:
        if voice_channel.channel != channel:
            await ctx.send(embed=discord.Embed(
                title="",
                description=f"Bot is already in another voice channel.",
                color=discord.Colour(int(EMBEDCOLOR, 16))
            ))
            return
    else:
        # If the bot is not in any vc, connect to the requested vc
        voice_channel = await channel.connect()

    if 'youtu.be' in query:
        video_id = query.split('/')[-1].split('?')[0]
        url = f'https://www.youtube.com/watch?v={video_id}'
        await process_single_song(ctx, voice_channel, video_id, url)
    elif 'youtube.com/playlist?' in query:
        playlist_id = query.split('=')[1].split('&')[0]
        url = f'https://www.youtube.com/playlist?list={playlist_id}'
        playlist_songs = get_playlist_songs(playlist_id)
        if not playlist_songs:
            await ctx.send(embed=discord.Embed(
                title="",
                description=f"Failed to fetch playlist songs.",
                color=discord.Colour(int(EMBEDCOLOR, 16))
            ))
            return
        await process_playlist(ctx, voice_channel, playlist_songs)
    else:
        # Extract base URL
        if '&' in query:
            query = query.split('&')[0]
        video_id = search_youtube(query)
        if not video_id:
            await ctx.send(embed=discord.Embed(
                title="",
                description=f"No results found for the given query.",
                color=discord.Colour(int(EMBEDCOLOR, 16))
            ))
            return
        url = f'https://www.youtube.com/watch?v={video_id}'
        await process_single_song(ctx, voice_channel, video_id, url)

async def process_single_song(ctx, voice_channel, video_id, url):
    await ctx.send(embed=discord.Embed(
        title="",
        description=f"Added to queue: **{get_video_title(video_id)}**",
        color=discord.Colour(int(EMBEDCOLOR, 16))
    ))

    queue.append({
        'url': url,
        'title': get_video_title(video_id)
    })

    if not voice_channel.is_playing():
        await play_next_in_queue(voice_channel)

def get_playlist_songs(playlist_id):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    songs = []

    try:
        request = youtube.playlistItems().list(part='snippet', playlistId=playlist_id, maxResults=50)
        response = request.execute()
        for item in response['items']:
            video_id = item['snippet']['resourceId']['videoId']
            title = item['snippet']['title']
            url = f'https://www.youtube.com/watch?v={video_id}'
            songs.append({'video_id': video_id, 'url': url, 'title': title})
        return songs
    except HttpError as e:
        print(f'An error occurred: {e}')
        return None
    
async def process_playlist(ctx, voice_channel, playlist_songs, max_songs=PLAYLIST_SONG_COUNT):
    max_songs = int(max_songs) if max_songs is not None else None
    num_songs = min(len(playlist_songs), max_songs) if max_songs else len(playlist_songs)
    await ctx.send(embed=discord.Embed(
        title="",
        description=f"{num_songs} songs added to the queue from the playlist!",
        color=discord.Colour(int(EMBEDCOLOR, 16))
    ))

    for song in playlist_songs:
        queue.append({
            'url': song['url'],
            'title': song['title']
        })

    if not voice_channel.is_playing():
        await play_next_in_queue(voice_channel)

def search_youtube(query):
    ydl = youtube_dl.YoutubeDL({'format': 'best'})
    try:
        with ydl:
            result = ydl.extract_info(f'ytsearch:{query}', download=False)
            return result['entries'][0]['id']
    except youtube_dl.DownloadError:
        return None
    
@bot.command(name='queuelist', aliases=['qlist'])
async def display_queue(ctx):
    if not queue:
        await ctx.send(embed=discord.Embed(
        title="",
        description=f"The queue is empty.",
        color=discord.Colour(int(EMBEDCOLOR, 16))
        ))
        return

    embed = discord.Embed(
        title="Queue List",
        color=discord.Colour(int(EMBEDCOLOR, 16))
    )

    for index, song in enumerate(queue):
        embed.add_field(name=f"{index + 1}. {song['title']}", value=" ", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='clearqueue', aliases=['clearq'])
async def clear_queue(message):
    global queue
    if queue:
        queue.clear()
        await message.channel.send(embed=discord.Embed(
        title="",
        description=f"Queue cleared.",
        color=discord.Colour(int(EMBEDCOLOR, 16))
        ))
    else:
        await message.channel.send(embed=discord.Embed(
        title="",
        description=f"The queue is already empty.",
        color=discord.Colour(int(EMBEDCOLOR, 16))
        ))

@bot.command(name='skip') 
async def skip_song(message):
    voice_channel = discord.utils.get(bot.voice_clients, guild=message.guild)
    if voice_channel.is_playing():
        voice_channel.stop()
        await message.channel.send(embed=discord.Embed(
        title="",
        description=f"Skipped the currently playing song.",
        color=discord.Colour(int(EMBEDCOLOR, 16))
        ))
        await play_next_in_queue(voice_channel)
    else:
        await message.channel.send(embed=discord.Embed(
        title="",
        description=f"There is no song currently playing.",
        color=discord.Colour(int(EMBEDCOLOR, 16))
        ))

@bot.command(name='pause') 
async def pause_song(message):
    voice_channel = discord.utils.get(bot.voice_clients, guild=message.guild)
    if voice_channel.is_playing():
        voice_channel.pause()
        await message.channel.send(embed=discord.Embed(
        title="",
        description=f"Paused the currently playing song.",
        color=discord.Colour(int(EMBEDCOLOR, 16))
        ))
    else:
        await message.channel.send(embed=discord.Embed(
        title="",
        description=f"There is no song currently playing.",
        color=discord.Colour(int(EMBEDCOLOR, 16))
        ))

@bot.command(name='resume') 
async def resume_song(message):
    voice_channel = discord.utils.get(bot.voice_clients, guild=message.guild)
    if voice_channel.is_paused():
        voice_channel.resume()
        await message.channel.send(embed=discord.Embed(
        title="",
        description=f"Resumed the currently paused song.",
        color=discord.Colour(int(EMBEDCOLOR, 16))
        ))
    else:
        await message.channel.send(embed=discord.Embed(
        title="",
        description=f"The song is not paused.",
        color=discord.Colour(int(EMBEDCOLOR, 16))
        ))

@bot.command(name='stop')
async def stop_music(message):
    voice_channel = discord.utils.get(bot.voice_clients, guild=message.guild)
    
    if voice_channel.is_playing():
        voice_channel.stop()
    await message.channel.send(embed=discord.Embed(
    title="",
    description=f"Player has been stopped.",
    color=discord.Colour(int(EMBEDCOLOR, 16))
    ))
    queue.clear()
    await voice_channel.disconnect()
    
async def play_next_in_queue(voice_channel):
    if queue:
        next_song = queue[0]

        if not voice_channel.is_playing():
            song_url = next_song['url']

            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }

            async def download_song():
                nonlocal song_url
                with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(song_url, download=False)
                    song_url = info_dict.get('url', '')

            await asyncio.gather(download_song())

            voice_channel.play(discord.FFmpegPCMAudio(song_url, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn"), after=lambda e: asyncio.run_coroutine_threadsafe(play_next_in_queue(voice_channel), bot.loop))

            await voice_channel.guild.get_channel(voice_channel.channel.id).send(f'Now playing: {next_song["title"]}')

        queue.pop(0)

    else:
        # If queue is empty, disconnect from voice channel
        await voice_channel.disconnect()

def get_video_title(video_id):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

    try:
        request = youtube.videos().list(part='snippet', id=video_id)
        response = request.execute()
        return response['items'][0]['snippet']['title']

    except HttpError as e:
        print(f'An error occurred: {e}')
        return 'Unknown Title'

@bot.command(name='shuffle')    
async def shuffle_queue(message):
    global queue
    if len(queue) < 2:
        await message.channel.send("There are not enough songs in the queue to shuffle.")
        return

    random.shuffle(queue)

    await message.channel.send(embed=discord.Embed(
        title="",
        description=f"Queue Shuffled.",
        color=discord.Colour(int(EMBEDCOLOR, 16))
        ))

@bot.command(name='help')
async def help(ctx):
    view = HelpView()
    await ctx.send("Here are the commands:", view=view)

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__()

        self.add_item(CategorySelect())

class CategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Music", value="music", description="Music commands"),
        ]
        super().__init__(placeholder="Select a category", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_category = self.values[0]
        if selected_category == "music":
            embed = discord.Embed(
                title="Music Commands",
                color=discord.Colour(int(EMBEDCOLOR, 16))
            )

            embed.add_field(name=f"{BOT_PREFIX}play [song/link] | {BOT_PREFIX}p [song/link]", value="Play a song from YouTube.", inline=False)
            embed.add_field(name=f"{BOT_PREFIX}queuelist |  {BOT_PREFIX}qlist", value="Display the current queue.", inline=False)
            embed.add_field(name=f"{BOT_PREFIX}clearqueue | {BOT_PREFIX}clearq", value="Clear the current queue.", inline=False)
            embed.add_field(name=f"{BOT_PREFIX}skip", value="Skip the currently playing song.", inline=False)
            embed.add_field(name=f"{BOT_PREFIX}pause", value="Pause the currently playing song.", inline=False)
            embed.add_field(name=f"{BOT_PREFIX}resume", value="Resume the currently paused song.", inline=False)
            embed.add_field(name=f"{BOT_PREFIX}stop", value="Stop the player and clear the queue.", inline=False)
            embed.add_field(name=f"{BOT_PREFIX}shuffle", value="Shuffle the current queue.", inline=False)
            await interaction.response.send_message(embed=embed)

bot.run(BOT_TOKEN)