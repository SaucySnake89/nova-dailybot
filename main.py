import discord
from discord.ext import commands, tasks
import nest_asyncio
import logging
import datetime
import asyncio
from dotenv import load_dotenv
import os
import webserver

nest_asyncio.apply()

webserver.keep_alive()


load_dotenv()
token = os.getenv('DISCORD_TOKEN')
CHECK_IN_CHANNEL_ID = int(os.getenv('CHECK_IN_CHANNEL_ID', '0'))




CHECK_IN_TIME = datetime.time(hour=7, minute=0, second=0)

CHECK_IN_MESSAGE = (
    "👋 Good morning, everyone! Time for our daily check-in. "
    "How are you doing today? React ✅ to get your daily EXP! "
)

ALLOWED_REACTION_EMOJI = '✅'

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

bot.last_check_in_message_id = None
bot.users_who_checked_in_today = set()


# @bot.event
# async def on_ready():
#     print(f"We are ready to go in, {bot.user.name}")



@bot.event
async def on_ready():
    """
    This event fires when the bot successfully connects to Discord.
    It prints a confirmation message and starts the daily check-in task.
    """
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')
    # Start the daily check-in loop
    if not daily_check_in.is_running():
        daily_check_in.start()
        print(f"Daily check-in task initiated for {CHECK_IN_TIME} UTC.")
        await asyncio.sleep(1) # Give the task a moment to fully start
        if daily_check_in.is_running():
            print("Daily check-in task is now confirmed as running.")
        else:
            print("Warning: Daily check-in task did not confirm as running immediately after start.")
    else:
        print("Daily check-in task is already running.")
    
    
@bot.event
async def on_raw_reaction_add(payload):
    """
    This event fires when any user adds a reaction to any message.
    We use on_raw_reaction_add because it provides more raw data,
    including message_id and user_id, which is useful for messages
    that might not be in the bot's cache.
    """
    # Ignore reactions from the bot itself
    if payload.user_id == bot.user.id:
        return

    # Check if the reaction is on our specific check-in message in the correct channel
    if payload.channel_id == CHECK_IN_CHANNEL_ID and payload.message_id == bot.last_check_in_message_id:
        # Check if the added emoji is the allowed one
        if str(payload.emoji) == ALLOWED_REACTION_EMOJI:
            # Fetch the user who reacted
            user = bot.get_user(payload.user_id)
            if user:
                print(f"User {user.name} ({user.id}) reacted with {ALLOWED_REACTION_EMOJI} on the daily check-in message.")
            else:
                print(f"User with ID {payload.user_id} reacted with {ALLOWED_REACTION_EMOJI} on the daily check-in message (user object not found).")
            # You can add more advanced logging here, e.g., saving to a file or database.
        else:
            # If an unauthorized emoji is used on the check-in message, remove it.
            channel = bot.get_channel(payload.channel_id)
            if channel:
                message = await channel.fetch_message(payload.message_id)
                if message:
                    try:
                        await message.remove_reaction(payload.emoji, discord.Object(id=payload.user_id))
                        print(f"Removed unauthorized reaction {payload.emoji} from user {payload.user_id} on check-in message.")
                    except discord.Forbidden:
                        print(f"Error: Bot does not have 'Manage Messages' permission to remove reactions in channel {channel.name}.")
                    except discord.HTTPException as e:
                        print(f"Error removing reaction: {e}")


@tasks.loop(time=CHECK_IN_TIME)
async def daily_check_in():
    """
    This task runs daily at the time specified by CHECK_IN_TIME.
    It attempts to find the specified channel and send the check-in message.
    After sending, it stores the message's ID.
    """
    if CHECK_IN_CHANNEL_ID == 0:
        print("Error: CHECK_IN_CHANNEL_ID is not set. Please set it in your environment variables or in the script.")
        return

    # Get the channel object using its ID
    channel = bot.get_channel(CHECK_IN_CHANNEL_ID)

    if channel:
        try:
            # Send the check-in message to the channel
            sent_message = await channel.send(CHECK_IN_MESSAGE)
            # Store the ID of the sent message
            bot.last_check_in_message_id = sent_message.id
            print(f"Daily check-in message sent to #{channel.name} ({channel.id}) at {datetime.datetime.now().time()}")
            print(f"Stored check-in message ID: {bot.last_check_in_message_id}")
            # Add the allowed reaction automatically to the message
            await sent_message.add_reaction(ALLOWED_REACTION_EMOJI)
        except discord.Forbidden:
            print(f"Error: Bot does not have permissions to send messages or add reactions in channel {channel.name} ({channel.id}).")
        except discord.HTTPException as e:
            print(f"Error sending message or adding reaction: {e}")
    else:
        print(f"Error: Channel with ID {CHECK_IN_CHANNEL_ID} not found. "
              "Please ensure the bot is in the server and the channel ID is correct.")
        

@bot.command(name='send_checkin_now')
async def send_checkin_now(ctx):
    """
    A command to manually trigger the daily check-in message.
    Usage: !send_checkin_now
    """
    # Optional: You can add checks here to only allow specific roles or users to use this command.
    # For example: @commands.has_permissions(administrator=True)
    # Or: if ctx.author.id == YOUR_ADMIN_USER_ID:
    print(f"Command '!send_checkin_now' invoked by {ctx.author.name} ({ctx.author.id}).")
    await ctx.send("Manually triggering daily check-in message...")
    await daily_check_in()
    await ctx.send("Daily check-in message sent!")

# --- NEW DIAGNOSTIC COMMAND: Check bot's current time and next scheduled run ---
@bot.command(name='check_time')
async def check_bot_time(ctx):
    """
    A command to check the bot's current UTC time and the next scheduled check-in time.
    Usage: !check_time
    """
    current_utc_time = datetime.datetime.utcnow()
    scheduled_utc_time = CHECK_IN_TIME

    response_message = (
        f"**Bot's Current UTC Time:** {current_utc_time.strftime('%H:%M:%S UTC')}\n"
        f"**Scheduled Check-in Time (UTC):** {scheduled_utc_time.strftime('%H:%M:%S UTC')}\n"
    )

    # Check if the task loop is running before calculating next run
    if daily_check_in.is_running():
        # Calculate time until next run
        # Get the current UTC time as a time object for comparison
        now_utc_time_only = current_utc_time.time()
        
        # Determine if scheduled time has passed for today
        if now_utc_time_only > scheduled_utc_time:
            # If time has passed today, next run is tomorrow
            next_run_datetime = datetime.datetime.combine(current_utc_time.date() + datetime.timedelta(days=1), scheduled_utc_time)
        else:
            # If time has not passed today, next run is today
            next_run_datetime = datetime.datetime.combine(current_utc_time.date(), scheduled_utc_time)

        # Calculate the timedelta
        time_until_next_run = next_run_datetime - current_utc_time
        
        # Extract hours, minutes, seconds from timedelta
        total_seconds = int(time_until_next_run.total_seconds())
        days = total_seconds // (24 * 3600)
        total_seconds %= (24 * 3600)
        hours = total_seconds // 3600
        total_seconds %= 3600
        minutes = total_seconds // 60
        seconds = total_seconds % 60

        response_message += (
            f"**Next Scheduled Run:** In {days} days, {hours} hours, {minutes} minutes, {seconds} seconds (at {next_run_datetime.strftime('%Y-%m-%d %H:%M:%S UTC')})\n"
            f"**Daily Check-in Task Status:** Running."
        )
    else:
        response_message += "**Daily Check-in Task Status:** Not running."

    await ctx.send(response_message)





    

# @bot.event
# async def on_message(message):
#     if message.author == bot.user:
#         return
    
#     if "goon" in message.content.lower():
#         await message.delete()
#         await message.channel.send(f"{message.author.mention} STOP GOONING!")
        
#     await bot.process_commands(message)

bot.run(token, log_handler=handler, log_level=logging.DEBUG)


