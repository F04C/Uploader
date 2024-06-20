import os
import asyncio
import random
import discord
from discord.ext import commands
import instaloader
from config import discord_token
from user_agents import USER_AGENTS

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
        
        # Setting the download folder of Instaloader to clean up the main folder
        L = instaloader.Instaloader(user_agent=random.choice(USER_AGENTS), dirname_pattern=f"Downloaded/{instagram_username}", download_geotags=False, download_comments=False, save_metadata=False)
        
        # Equivalent of --login
        # L.login(username, passwd)
        
        # Download images from Instagram
        profile = instaloader.Profile.from_username(L.context, instagram_username)
        post_count = sum(1 for _ in profile.get_posts())
        print(f"Downloading {post_count} posts from Instagram for {instagram_username}")

        downloaded_media_ids = {os.path.splitext(file)[0] for file in os.listdir(f"Downloaded/{instagram_username}") if file.endswith(('.jpg', '.png', '.mp4', '.json'))}

        for i, post in enumerate(profile.get_posts(), start=1):
            try:
                if str(post.mediaid) in downloaded_media_ids:
                    print(f"Skipped post {i}/{post_count} (Already downloaded)")
                    continue

                L.download_post(post, target=instagram_username)
                print(f"Downloaded post {i}/{post_count}")
            except instaloader.exceptions.InstaloaderException as e:
                print(f"Error downloading post {i}/{post_count}: {str(e)}")
                if "Redirected to login page" in str(e):
                    set_random_user_agent()
                    L.download_post(post, target=instagram_username)
                    print(f"Downloaded post {i}/{post_count} after changing user agent")

        # Create or find a channel with the Instagram username
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
        
        # Initialize a variable to store the recently made 'downloaded directory'
        downloaded_dir = f"Downloaded/{instagram_username}"
        
        # Upload images to the new channel
        files = [filename for filename in os.listdir(downloaded_dir) if filename.endswith((".jpg", ".png", ".mp4"))]
        file_count = len(files)

        print(f"Uploading {file_count} files to Discord in channel {new_channel.mention}")

        # Load previously uploaded files specific to the Instagram username
        uploaded_files = set(load_uploaded_files(instagram_username))

        max_file_size_bytes = 25 * 1024 * 1024  # 25 MB

        for i, filename in enumerate(files, start=1):
            file_path = os.path.join(downloaded_dir, filename)

            if filename in uploaded_files:
                print(f"Skipped file {i}/{file_count} (Already uploaded)")
                continue

            file_size = os.path.getsize(file_path)

            if file_size <= max_file_size_bytes:
                with open(file_path, "rb") as file:
                    try:
                        await new_channel.send(file=discord.File(file, filename=filename))
                        uploaded_files.add(filename)
                        print(f"Uploaded file {i}/{file_count} of {instagram_username}")
                    except discord.Forbidden:
                        print(f"Error: Bot doesn't have permission to send files in {new_channel.mention}.")
                        return
            else:
                print(f"Skipped file {i}/{file_count} (File size exceeds Discord limit)")

        save_uploaded_files(instagram_username, uploaded_files)

        print(f"Download and upload completed for {instagram_username} in channel {new_channel.mention}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

bot.run(discord_token)


#TODO

# Need to check instaloader main repo about the error
# An error occurred: Login: Checkpoint required. Point your browser to https://www.instagram.com/challenge/action/AXFCafOiDQ_XRypUz57tb4J0shSaWvKiw_CNDaYaCWl7X4bO2hpKQqjRqVt4vtbY0qcfOmo/AfzMJ6PjvSZXM46Rc68381t_Ute8WryRwJ7hKCJIXcc7P3cJdAPcrCmBhVHZnQKHL2Kiy11cY4cpVQ/ffc_KWeTmh26zKnnfhBZWHMfv8cI5hNKFqWUhhU9hO1DfuagAbIqjnOUWmrqIn5xu7mZ/ - follow the instructions, then retry.