import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

from task_managerdb import (
    print_schedule,
    load_config,
    populate_people_and_tasks,
    generate_assignments,
    swap_assignments,
    skip_assignment,
    reset_database,
    update_assignment
)

from datetime import date

# ...existing code...

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"We are ready to go in, {bot.user.name}")

@bot.event
async def on_member_join(member):
    await member.send(f"Welcome to the server {member.name}")

from task_managerdb import print_schedule
# ...existing code...

@bot.event
async def on_message(message):
    print(f"DEBUG: Received message '{message.content}' from {message.author}")
    await bot.process_commands(message)
    if message.author == bot.user:
        return
    if "schedule" in message.content.lower():
        print(f"Received message: {message.content}")
        schedule = print_schedule()
        print(schedule)
        await message.channel.send(schedule)

@bot.command(name='reset')
async def reset(ctx, start_date: str = None):        
    print(f"DEBUG: Reset command invoked with start_date={start_date}")


    # Load default config
    config = load_config()
    if not config:
        await ctx.send("Configuration not found.")
        return
   
    # Parse start date
    start = None
    if start_date:
        try:
            start = date.fromisoformat(start_date)
        except ValueError:
            await ctx.send("Invalid date format. Please use YYYY-MM-DD.")
            return
       
    # Reset DB
    success = reset_database(config, start)


    if not success:
        await ctx.send("Database reset failed — counts are zero after recreation.")
        return


    await ctx.send(
        f"Database reset and repopulated starting from **{start if start else 'today'}**."
    )

@bot.command(name='swap')
async def swap(ctx, task_name: str, taskDate1: str, taskDate2: str):        
    print(f"DEBUG: Swap command invoked with task_name={task_name}, taskDate1={taskDate1}, taskDate2={taskDate2}")
    success = swap_assignments(task_name, taskDate1, taskDate2)
    if success:
        await ctx.send(f"Successfully swapped assignments for task '{task_name}' on {taskDate1} and {taskDate2}.")
    else:
        await ctx.send(f"Failed to swap assignments for task '{task_name}' on {taskDate1} and {taskDate2}. Please check the task name and dates.")  

@bot.command(name='skip')
async def skip(ctx, task_name: str, taskDate_string: str):        
    print(f"DEBUG: Skip command invoked with task_name={task_name}, taskDate_string={taskDate_string}")
    success = skip_assignment(task_name, taskDate_string)
    if success:
        await ctx.send(f"Successfully skipped assignment for task '{task_name}' on {taskDate_string}.")
    else:
        await ctx.send(f"Failed to skipped assignment for task '{task_name}' on {taskDate_string}. Please check the task name and dates.")  

@bot.command(name="update")
async def update(ctx):
    print(">>> inside update command")   # test print
    await ctx.send("update command triggered")
    try:
        # Load your config (adjust if you load it differently)
        config = load_config()

        # Run your update function
        update_assignment(config)

        # Confirm in both terminal and Discord
        print("Update finished successfully.")
        await ctx.send("Assignments updated successfully.")

    except Exception as e:
        # Log errors to terminal and Discord
        print("Error in update_assignment:", e)
        await ctx.send(f"An error occurred while updating: `{e}`")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)

