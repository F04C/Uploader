import os
import random #this is for randomizing useragents
import discord
from discord.ext import commands
import instaloader
# import shutil
from config import discord_token
from user_agents import USER_AGENTS #importing useragents

# Initialize Instaloader
L = instaloader.Instaloader()

# Initialize Discord bot
bot = commands.Bot(command_prefix='!')

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
async def update_uploaded_files(ctx):
    try:
        # Iterate through all text files in the Uploaded folder
        for filename in os.listdir('Uploaded'):
            if filename.endswith('_uploaded_files.txt'):
                instagram_username = filename.replace('_uploaded_files.txt', '')

                # Download images from Instagram for the current username
                await download_and_upload(ctx, instagram_username)

        print("Update completed for all users.")
    except Exception as e:
        print(f"An error occurred during the update: {str(e)}")




@bot.command(name='dl')
async def download_and_upload(ctx, instagram_username):
    try:
        # Set a custom user agent for Instaloader
        L.context.user_agent = random.choice(USER_AGENTS)
        # Download images from Instagram
        profile = instaloader.Profile.from_username(L.context, instagram_username)
        post_count = sum(1 for _ in profile.get_posts())
        print(f"Downloading {post_count} posts from Instagram for {instagram_username}")

        for i, post in enumerate(profile.get_posts(), start=1):
            try:
                L.download_post(post, target=instagram_username)
                print(f"Downloaded post {i}/{post_count}")
            except instaloader.exceptions.InstaloaderException as e:
                print(f"Error downloading post {i}/{post_count}: {str(e)}")

        # Create or find a channel with the Instagram username
        channel_name = instagram_username
        existing_channel = discord.utils.get(ctx.guild.channels, name=channel_name, type=discord.ChannelType.text)

        if not existing_channel:
            # Replace special characters with underscores for channel name
            sanitized_channel_name = ''.join(c if c.isalnum() else '_' for c in channel_name)

            # Check for an existing text channel with the sanitized name
            existing_channel = next((channel for channel in ctx.guild.text_channels if channel.name == sanitized_channel_name), None)

            if not existing_channel:
                # Create a new text channel if no existing channel is found
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


        # Upload images to the new channel
        files = [filename for filename in os.listdir(instagram_username) if filename.endswith((".jpg", ".png", ".mp4"))]
        file_count = len(files)

        print(f"Uploading {file_count} files to Discord in channel {new_channel.mention}")

        # Load previously uploaded files specific to the Instagram username
        uploaded_files = set(load_uploaded_files(instagram_username))

        # Adjusted file size limit for Discord's increased limit
        max_file_size_bytes = 25 * 1024 * 1024  # 25 MB

        for i, filename in enumerate(files, start=1):
            file_path = f"{instagram_username}/{filename}"

            # Check if the file has already been uploaded
            if filename in uploaded_files:
                print(f"Skipped file {i}/{file_count} (Already uploaded)")
                continue

            # Check file size before uploading
            file_size = os.path.getsize(file_path)

            if file_size <= max_file_size_bytes:
                with open(file_path, "rb") as file:
                    try:
                        await new_channel.send(file=discord.File(file, filename=filename))
                        uploaded_files.add(filename)  # Add the filename to the set of uploaded files
                        print(f"Uploaded file {i}/{file_count}")
                    except discord.Forbidden:
                        print(f"Error: Bot doesn't have permission to send files in {new_channel.mention}.")
                        return
            else:
                print(f"Skipped file {i}/{file_count} (File size exceeds Discord limit)")

        # Save the updated list of uploaded files specific to the Instagram username
        save_uploaded_files(instagram_username, uploaded_files)

        # Delete the entire folder after uploading all files
        # shutil.rmtree(instagram_username)

        print(f"Download, upload, and folder deletion completed for {instagram_username} in channel {new_channel.mention}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

# Run the Discord bot
bot.run(discord_token)


# add an option like update function to update all txt files and download them