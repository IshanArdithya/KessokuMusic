import discord
import random
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import BOT_TOKEN, YOUTUBE_API_KEY, BOT_PREFIX

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)


queue = []

command_prefix = bot.command_prefix

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user.name}')

@bot.command(name='play', aliases=['p'])
async def play_music(ctx, *, query):
    try:
        channel = ctx.author.voice.channel
    except AttributeError:
        await ctx.send("You need to be in a voice channel to use this command.")
        return

    # Check if the bot is already in a vc in the same server
    voice_channel = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    # If the bot is already in a vc, use that channel (might change this in the future)
    if voice_channel:
        if voice_channel.channel != channel:
            await ctx.send("Bot is in another voice channel. Disconnecting and connecting to your channel.")
            await voice_channel.disconnect()
            voice_channel = await channel.connect()
    else:
        # If the bot is not in any vc, connect to the requested vc
        voice_channel = await channel.connect()

    # Extract video ID
    if 'youtu.be' in query:
        video_id = query.split('/')[-1].split('?')[0]
    else:
        # Search for the song
        video_id = search_youtube(query)

    if not video_id:
        await ctx.send("No results found for the given query.")
        return

    url = f'https://www.youtube.com/watch?v={video_id}'

    await ctx.send(f'Added to queue: {get_video_title(video_id)}')

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    # Download the song details in the background
    async def download_song():
        nonlocal url
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            url = info_dict.get('url', '')

    await asyncio.gather(download_song())

    # Add the song to the queue
    queue.append({
        'url': url,
        'title': get_video_title(video_id)
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
async def display_queue(message):
    if not queue:
        await message.channel.send("The queue is empty.")
        return

    queue_list = '\n'.join([f'{index + 1}. {song["title"]}' for index, song in enumerate(queue)])
    await message.channel.send(f'Queue:\n{queue_list}')

@bot.command(name='clearqueue', aliases=['clearq'])
async def clear_queue(message):
    global queue
    if queue:
        queue.clear()
        await message.channel.send("Queue cleared.")
    else:
        await message.channel.send("The queue is already empty.")

@bot.command(name='skip') 
async def skip_song(message):
    voice_channel = discord.utils.get(bot.voice_clients, guild=message.guild)
    if voice_channel.is_playing():
        voice_channel.stop()
        await message.channel.send("Skipped the currently playing song.")
        await play_next_in_queue(voice_channel)
    else:
        await message.channel.send("There is no song currently playing.")

@bot.command(name='pause') 
async def pause_song(message):
    voice_channel = discord.utils.get(bot.voice_clients, guild=message.guild)
    if voice_channel.is_playing():
        voice_channel.pause()
        await message.channel.send("Paused the currently playing song.")
    else:
        await message.channel.send("There is no song currently playing.")

@bot.command(name='resume') 
async def resume_song(message):
    voice_channel = discord.utils.get(bot.voice_clients, guild=message.guild)
    if voice_channel.is_paused():
        voice_channel.resume()
        await message.channel.send("Resumed the currently paused song.")
    else:
        await message.channel.send("The song is not paused.")

@bot.command(name='stop')
async def stop_music(message):
    voice_channel = discord.utils.get(bot.voice_clients, guild=message.guild)
    
    if voice_channel.is_playing():
        voice_channel.stop()
        await message.channel.send("Music stopped.")
    queue.clear()
    await voice_channel.disconnect()
    
async def play_next_in_queue(voice_channel):
    
    if queue:
        next_song = queue[0]

        if not voice_channel.is_playing():
            queue.pop(0)
            voice_channel.play(discord.FFmpegPCMAudio(next_song['url'], before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn"), after=lambda e: asyncio.run_coroutine_threadsafe(play_next_in_queue(voice_channel), bot.loop))

            await voice_channel.guild.get_channel(voice_channel.channel.id).send(f'Now playing: {next_song["title"]}')

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

    await message.channel.send("Queue shuffled.")

bot.run(BOT_TOKEN)