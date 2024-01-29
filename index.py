import discord
from discord.ext import commands
import instaloader
import os
import shutil
from config import discord_token

# Initialize Instaloader
L = instaloader.Instaloader()

# Initialize Discord bot
bot = commands.Bot(command_prefix='!')

@bot.command(name='dl')
async def download_and_upload(ctx, instagram_username):
    try:
        # Download images from Instagram
        profile = instaloader.Profile.from_username(L.context, instagram_username)
        post_count = sum(1 for _ in profile.get_posts())
        await ctx.send(f"Downloading {post_count} posts from Instagram for {instagram_username}")

        for i, post in enumerate(profile.get_posts(), start=1):
            L.download_post(post, target=instagram_username)
            await ctx.send(f"Downloaded post {i}/{post_count}")

        # Create a new channel with the Instagram username
        channel_name = instagram_username.lower()  # Convert to lowercase for safety
        existing_channel = discord.utils.get(ctx.guild.channels, name=channel_name)

        if not existing_channel:
            # Create a new text channel
            new_channel = await ctx.guild.create_text_channel(channel_name)
        else:
            new_channel = existing_channel

        # Upload images to the new channel
        files = [filename for filename in os.listdir(instagram_username) if filename.endswith((".jpg", ".png"))]
        file_count = len(files)

        await ctx.send(f"Uploading {file_count} files to Discord in channel {new_channel.mention}")
        
        for i, filename in enumerate(files, start=1):
            with open(f"{instagram_username}/{filename}", "rb") as file:
                await new_channel.send(file=discord.File(file, filename=filename))
            
            await ctx.send(f"Uploaded file {i}/{file_count}")

        # Delete the entire folder after uploading all files
        shutil.rmtree(instagram_username)

        await ctx.send(f"Download, upload, and folder deletion completed for {instagram_username} in channel {new_channel.mention}")
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

# Run the Discord bot
bot.run(discord_token)
