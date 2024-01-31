import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='+', intents=intents)

YOUTUBE_API_KEY = 'AIzaSyDfEis1F2ZFGsOssyzTXXbSY6q5dhk_ydw'


queue = []

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user.name}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.lower().startswith('+play') or message.content.lower().startswith('+p'):
        await play_music(message)

    elif message.content.lower() == '+stop':
        await stop_music(message)

    elif message.content.lower() == '+queuelist' or message.content.lower() == '+qlist':
        await display_queue(message)

    elif message.content.lower() == '+clearqueue' or message.content.lower() == '+clearq':
        await clear_queue(message)

    elif message.content.lower() == '+skip':
        await skip_song(message)

    elif message.content.lower() == '+pause':
        await pause_song(message)

    elif message.content.lower() == '+resume':
        await resume_song(message)

    await bot.process_commands(message)

async def play_music(message):
    try:
        channel = message.author.voice.channel
    except AttributeError:
        await message.channel.send("You need to be in a voice channel to use this command.")
        return

    # Check if the bot is already in a voice channel in the same guild
    voice_channel = discord.utils.get(bot.voice_clients, guild=message.guild)

    # If the bot is already in a voice channel, use that channel
    if voice_channel:
        if voice_channel.channel != channel:
            await message.channel.send("Bot is in another voice channel. Disconnecting and connecting to your channel.")
            await voice_channel.disconnect()
            voice_channel = await channel.connect()
    else:
        # If the bot is not in any voice channel, connect to the requested channel
        voice_channel = await channel.connect()

    if message.content.lower().startswith('+play'):
        query = message.content[len('+play '):].strip()
    elif message.content.lower().startswith('+p'):
        query = message.content[len('+p '):].strip()
    else:
        return

    # Search for the song
    video_id = search_youtube(query)
    if not video_id:
        await message.channel.send("No results found for the given query.")
        return

    url = f'https://www.youtube.com/watch?v={video_id}'

    # Send "Added to queue" message immediately
    await message.channel.send(f'Added to queue: {get_video_title(video_id)}')

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

    # Run the download_song function in the background
    await asyncio.gather(download_song())

    # Add the song to the queue
    queue.append({
        'url': url,
        'title': get_video_title(video_id)
    })

    # Check if the bot is not currently playing any song
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
    
async def display_queue(message):
    if not queue:
        await message.channel.send("The queue is empty.")
        return

    queue_list = '\n'.join([f'{index + 1}. {song["title"]}' for index, song in enumerate(queue)])
    await message.channel.send(f'Queue:\n{queue_list}')

async def clear_queue(message):
    global queue
    if queue:
        queue.clear()
        await message.channel.send("Queue cleared.")
    else:
        await message.channel.send("The queue is already empty.")

async def skip_song(message):
    voice_channel = discord.utils.get(bot.voice_clients, guild=message.guild)
    if voice_channel.is_playing():
        voice_channel.stop()
        await message.channel.send("Skipped the currently playing song.")
        await play_next_in_queue(voice_channel)
    else:
        await message.channel.send("There is no song currently playing.")

async def pause_song(message):
    voice_channel = discord.utils.get(bot.voice_clients, guild=message.guild)
    if voice_channel.is_playing():
        voice_channel.pause()
        await message.channel.send("Paused the currently playing song.")
    else:
        await message.channel.send("There is no song currently playing.")

async def resume_song(message):
    voice_channel = discord.utils.get(bot.voice_clients, guild=message.guild)
    if voice_channel.is_paused():
        voice_channel.resume()
        await message.channel.send("Resumed the currently paused song.")
    else:
        await message.channel.send("The song is not paused.")

async def stop_music(message):
    voice_channel = discord.utils.get(bot.voice_clients, guild=message.guild)
    
    if voice_channel.is_playing():
        voice_channel.pause()
        await message.channel.send("Music stopped.")

    await voice_channel.disconnect()
    

async def play_next_in_queue(voice_channel):
    # Check if there are songs in the queue
    if queue:
        next_song = queue[0]  # Get the next song without removing it from the queue

        # Check if the bot is not currently playing any song
        if not voice_channel.is_playing():
            queue.pop(0)  # Remove the song from the queue now that we are going to play it
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

bot.run('MTIwMTQ4MzIxNDcyOTAwNzE0NA.GrBIA0.2to-Dy7iSR7OoRBHm0yuUfcF1pOlnccl3EY61A')
