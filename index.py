import os
import asyncio
import random
import discord
from discord.ext import commands
import instaloader
from config import discord_token
from user_agents import USER_AGENTS
from alive_progress import alive_bar

# Initialize Instaloader
L = instaloader.Instaloader()


# Initialize Discord bot
bot = commands.Bot(command_prefix='!')

def set_random_user_agent():
    L.context.user_agent = random.choice(USER_AGENTS)

# Function to load uploaded files from a file for a specific Instagram username
def load_uploaded_files(instagram_username):
    try:
        with open(f'Uploaded/{instagram_username}_uploaded_files.txt', 'r') as file:
            return file.read().splitlines()
    except FileNotFoundError:
        return []

# Function to save uploaded files to a file for a specific Instagram username
def save_uploaded_files(instagram_username, uploaded_files):
    os.makedirs('Uploaded', exist_ok=True)
    with open(f'Uploaded/{instagram_username}_uploaded_files.txt', 'w') as file:
        file.write('\n'.join(uploaded_files))

# Function to load downloaded files from a file for a specific Instagram username
def load_downloaded_files(instagram_username):
    try:
        with open(f'Downloaded/{instagram_username}_downloaded_files.txt', 'r') as file:
            return file.read().splitlines()
    except FileNotFoundError:
        return []

# Function to save downloaded files to a file for a specific Instagram username
def save_downloaded_files(instagram_username, downloaded_files):
    os.makedirs('Downloaded', exist_ok=True)
    with open(f'Downloaded/{instagram_username}_downloaded_files.txt', 'w') as file:
        file.write('\n'.join(downloaded_files))

@bot.command(name='update')
async def update_uploaded_files(ctx, num_users: int = 1):
    try:
        tasks = []

        # Get a list of all files in the Uploaded folder
        files = [file for file in os.listdir('Uploaded') if file.endswith('_uploaded_files.txt')]

        for file in files:
            file_path = os.path.join('Uploaded', file)
            print(f"{file}: {os.path.getmtime(file_path)}")
            
        # Sort the files based on modification time (oldest first)
        files.sort(key=lambda x: os.path.getmtime(os.path.join('Uploaded', x)))

        # Iterate through the sorted list of files and process the specified number of users
        for filename in files[:num_users]:
            instagram_username = filename.replace('_uploaded_files.txt', '')

            # Create a task for each username to download and upload asynchronously
            task = bot.loop.create_task(download_and_upload(ctx, instagram_username))
            tasks.append(task)
            
        await asyncio.gather(*tasks)
        print(f"Update completed for {num_users} user(s)")
    except Exception as e:
        print(f"An error occurred during the update: {str(e)}")

@bot.command(name='dl')
async def download_and_upload(ctx, instagram_username):
    try:
        # Set a random user agent for Instaloader
        set_random_user_agent()
        
        downloaded_dir = f"Downloaded/{instagram_username}"
        os.makedirs(downloaded_dir, exist_ok=True)
        
        # Setting the download folder of Instaloader to clean up the main folder
        L = instaloader.Instaloader(user_agent=random.choice(USER_AGENTS), dirname_pattern=f"Downloaded/{instagram_username}", download_geotags=False, download_comments=False, save_metadata=False)
        
        profile = instaloader.Profile.from_username(L.context, instagram_username)
        post_count = sum(1 for _ in profile.get_posts())
        print(f"Downloading {post_count} posts from Instagram for {instagram_username}")

        # Load the list of downloaded files
        downloaded_files = set(load_downloaded_files(instagram_username))
        downloaded_media_ids = {os.path.splitext(file)[0] for file in os.listdir(f"Downloaded/{instagram_username}") if file.endswith(('.jpg', '.png', '.mp4', '.json'))}

        for i, post in enumerate(profile.get_posts(), start=1):
            try:
                # Check if the post has already been downloaded
                if str(post.mediaid) in downloaded_media_ids or str(post.mediaid) in downloaded_files:
                    print(f"Skipped post {i}/{post_count} (Already downloaded)")
                    continue

                # Download the post
                L.download_post(post, target=instagram_username)
                downloaded_files.add(str(post.mediaid))
                print(f"Downloaded post {i}/{post_count}")
            except instaloader.exceptions.InstaloaderException as e:
                print(f"Error downloading post {i}/{post_count}: {str(e)}")
                if "Redirected to login page" in str(e):
                    set_random_user_agent()
                    L.download_post(post, target=instagram_username)
                    downloaded_files.add(str(post.mediaid))
                    print(f"Downloaded post {i}/{post_count} after changing user agent")

        # Save the list of downloaded files
        save_downloaded_files(instagram_username, downloaded_files)

        channel_name = instagram_username
        existing_channel = discord.utils.get(ctx.guild.channels, name=channel_name, type=discord.ChannelType.text)

        if not existing_channel:
            sanitized_channel_name = ''.join(c if c.isalnum() else '_' for c in channel_name)
            existing_channel = next((channel for channel in ctx.guild.text_channels if channel.name == sanitized_channel_name), None)

            if not existing_channel:
                try:
                    new_channel = await ctx.guild.create_text_channel(sanitized_channel_name)
                    print(f"Created new channel: {new_channel.name}")
                except discord.Forbidden:
                    print(f"Error: Bot doesn't have permission to create a new channel.")
                    return
            else:
                new_channel = existing_channel
                print(f"Found existing channel: {new_channel.name}")
        else:
            new_channel = existing_channel
            print(f"Found existing channel: {new_channel.name}")
        
        downloaded_dir = f"Downloaded/{instagram_username}"
        files = [filename for filename in os.listdir(downloaded_dir) if filename.endswith((".jpg", ".png", ".mp4"))]
        file_count = len(files)

        print(f"Uploading {file_count} files to Discord in channel {new_channel.mention}")

        uploaded_files = set(map(str, load_uploaded_files(instagram_username)))
        max_file_size_bytes = 25 * 1024 * 1024  # 25 MB

        async def upload_file(queue, bar):
            while not queue.empty():
                index, filename = await queue.get()
                file_path = os.path.join(downloaded_dir, filename)

                if filename in uploaded_files:
                    print(f"Skipped file {index}/{file_count} (Already uploaded)")
                    queue.task_done()
                    bar()
                    continue

                file_size = os.path.getsize(file_path)

                if file_size <= max_file_size_bytes:
                    with open(file_path, "rb") as file:
                        try:
                            await new_channel.send(file=discord.File(file, filename=filename))
                            uploaded_files.add(filename)
                            print(f"Uploaded file {index}/{file_count} of {instagram_username}")
                        except discord.Forbidden:
                            print(f"Error: Bot doesn't have permission to send files in {new_channel.mention}.")
                            queue.task_done()
                            bar()
                            return
                        except discord.HTTPException as e:
                            if e.status == 429:  # Rate limited
                                retry_after = e.retry_after
                                print(f"Rate limited. Retrying after {retry_after} seconds.")
                                await asyncio.sleep(retry_after)
                                await new_channel.send(file=discord.File(file, filename=filename))
                                uploaded_files.add(filename)
                                print(f"Uploaded file {index}/{file_count} of {instagram_username} after retry")
                        finally:
                            file.close()
                            os.remove(file_path)  # Delete the file after successful upload
                else:
                    print(f"Skipped file {index}/{file_count} (File size exceeds Discord limit)")

                queue.task_done()
                bar()

        queue = asyncio.Queue()
        for i, filename in enumerate(files, start=1):
            await queue.put((i, filename))

        with alive_bar(file_count, title="Uploading files") as bar:
            tasks = [upload_file(queue, bar) for _ in range(10)]  # Adjust the number of concurrent tasks as needed
            await asyncio.gather(*tasks)

        save_uploaded_files(instagram_username, uploaded_files)

        # Cleanup: Delete remaining media files in the directory
        for filename in os.listdir(downloaded_dir):
            file_path = os.path.join(downloaded_dir, filename)
            try:
                if os.path.isfile(file_path) and not file_path.endswith('_downloaded_files.txt'):
                    os.remove(file_path)
                    print(f"Deleted file {file_path}")
            except Exception as e:
                print(f"Error deleting file {file_path}: {str(e)}")

        print(f"Download and upload completed for {instagram_username} in channel {new_channel.mention}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

bot.run(discord_token)