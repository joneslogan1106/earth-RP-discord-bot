import discord
import os
import json
import asyncio
from datetime import datetime, time, timedelta
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", 0))
ADMIN_USER_ID = 1367955172373823629
DATA_FILE = "gov_state.json"
EST = ZoneInfo("America/New_York")

print("=" * 60)
print("Government Date Bot - Online")
print("=" * 60)
print(f"Token: {'Present' if TOKEN else 'Missing'}")
print(f"Channel ID: {CHANNEL_ID}")

# Load state
def load_state():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        now = datetime.now(EST)
        return {"current_date": now.isoformat(), "last_run": now.date().isoformat()}

def save_state(state):
    with open(DATA_FILE, "w") as f:
        json.dump(state, f, indent=2)

state = load_state()
current_date = datetime.fromisoformat(state["current_date"])
print(f"Current in-game date: {current_date.strftime('%B %Y')}")

def approximate_current_date(base_date, reference_time):
    """
    Approximate the current date based on a reference time.
    
    Args:
        base_date: The date at the start of the period (datetime)
        reference_time: Current real-world time (datetime)
    
    Returns:
        Approximated current date (datetime)
    """
    # Calculate how far we are through the current day
    # (0.0 = midnight, 0.5 = noon, 1.0 = next midnight)
    day_progress = (reference_time.hour * 3600 + reference_time.minute * 60 + reference_time.second) / 86400.0
    
    # For simplicity, assume each month has 30 days
    # This gives a rough approximation throughout the month
    days_into_month = day_progress * 30
    
    # Create the approximated date
    approximated_date = base_date + timedelta(days=days_into_month)
    
    return approximated_date

async def check_and_advance_date(channel):
    """Check if we need to advance the date and do it if needed"""
    now = datetime.now(EST)
    
    # Get the last run date from state
    last_run_str = state.get("last_run", now.date().isoformat())
    last_run = datetime.fromisoformat(last_run_str).date()
    
    # Calculate days missed
    days_missed = (now.date() - last_run).days
    
    if days_missed > 0:
        print(f"{days_missed} day(s) missed since last run")
        
        # Calculate months to advance (4 months per day missed, max 12)
        months_to_advance = min(4 * days_missed, 12)
        
        # Advance the date
        current = datetime.fromisoformat(state["current_date"])
        new_date = current + relativedelta(months=months_to_advance)
        
        # Update state
        state["current_date"] = new_date.isoformat()
        state["last_run"] = now.date().isoformat()
        save_state(state)
        
        print(f"Advanced from {current.strftime('%B %Y')} to {new_date.strftime('%B %Y')}")
        
        # Send notification if channel is available
        if channel:
            await channel.send(
                f"**Government Time Advancement**\n"
                f"Days processed: **{days_missed}**\n"
                f"New in-game date: **{new_date.strftime('%B %Y')}** (EST)"
            )
        
        return True
    else:
        # Check if it's currently midnight (± 1 minute to account for timing)
        if now.time().hour == 0 and now.time().minute <= 1:
            print("Midnight check")
            # Even if no days missed, update last_run to today
            state["last_run"] = now.date().isoformat()
            save_state(state)
            print("Updated last_run timestamp")
        
        return False

# Discord bot
intents = discord.Intents.default()
intents.message_content = True

class GovernmentBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.advance_channel = None
        
    async def on_ready(self):
        print("=" * 60)
        print(f"Connected as {self.user}")
        print(f"Current date: {datetime.fromisoformat(state['current_date']).strftime('%B %Y')}")
        print("=" * 60)
        
        # Get the notification channel
        if CHANNEL_ID:
            self.advance_channel = self.get_channel(CHANNEL_ID)
            if self.advance_channel:
                print(f"Notification channel: #{self.advance_channel.name}")
            else:
                print(f"Channel {CHANNEL_ID} not found")
        else:
            print("No channel ID set - auto-advance notifications disabled")
        
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="the calendar | !date"
        ))
        
        # Check and perform auto-advance immediately on startup
        print("Checking for missed advancements...")
        advanced = await check_and_advance_date(self.advance_channel)
        if advanced:
            print("Auto-advance completed")
        
    async def on_message(self, message):
        if message.author.bot:
            return
            
        print(f"[{message.author}] {message.content}")
        
        if message.content == "!date":
            base_date = datetime.fromisoformat(state["current_date"])
            now = datetime.now(EST)
            
            # Calculate approximated current date
            approx_date = approximate_current_date(base_date, now)
            
            # Format the response
            response = (
                f"**Current Date Approximation:**\n"
                f"Base Period: {base_date.strftime('%B %Y')}\n"
                f"Current Approximation: {approx_date.strftime('%B %d, %Y')}\n"
                f"Real Time: {now.strftime('%I:%M %p EST')}\n"
                f"\n"
                f"The date progresses through {base_date.strftime('%B %Y')} in real-time."
            )
            await message.channel.send(response)
            
        elif message.content == "!advance":
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("You are not authorized to use this command.")
                return
                
            current = datetime.fromisoformat(state["current_date"])
            new_date = current + relativedelta(months=4)
            state["current_date"] = new_date.isoformat()
            state["last_run"] = datetime.now(EST).date().isoformat()
            save_state(state)
            
            await message.channel.send(f"Manual advance complete. New base period: **{new_date.strftime('%B %Y')}**")
            
        elif message.content == "!ping":
            await message.channel.send("Online")
            
        elif message.content == "!status":
            current = datetime.fromisoformat(state["current_date"])
            last_run = datetime.fromisoformat(state["last_run"]).date()
            now_date = datetime.now(EST).date()
            days_since = (now_date - last_run).days
            
            # Calculate next advancement time
            next_midnight = datetime.combine(now_date + timedelta(days=1), time(0, 0, tzinfo=EST))
            time_until = next_midnight - datetime.now(EST)
            hours_until = time_until.seconds // 3600
            minutes_until = (time_until.seconds % 3600) // 60
            
            status_msg = (
                f"**Bot Status**\n"
                f"Current Base Period: {current.strftime('%B %Y')}\n"
                f"Last Auto-Check: {last_run.strftime('%Y-%m-%d')}\n"
                f"Next Auto-Advance: In {hours_until}h {minutes_until}m\n"
                f"Admin ID: {ADMIN_USER_ID}"
            )
            await message.channel.send(status_msg)
            
        elif message.content == "!current":
            # Detailed current date information
            base_date = datetime.fromisoformat(state["current_date"])
            now = datetime.now(EST)
            approx_date = approximate_current_date(base_date, now)
            
            # Calculate progress through the month (0-100%)
            day_progress = (now.hour * 3600 + now.minute * 60 + now.second) / 86400.0
            month_progress = day_progress * 100
            
            response = (
                f"**Date Information**\n"
                f"Base Period: {base_date.strftime('%B %Y')}\n"
                f"Current Approximation: {approx_date.strftime('%B %d, %Y')}\n"
                f"Time in {base_date.strftime('%B')}: {month_progress:.1f}% complete\n"
                f"Real World Time: {now.strftime('%I:%M:%S %p EST')}\n"
                f"Next Advancement: Tomorrow at midnight EST"
            )
            await message.channel.send(response)
            
        elif message.content == "!auto-check":
            # Manual trigger of auto-advance check
            advanced = await check_and_advance_date(message.channel)
            if advanced:
                await message.channel.send("Auto-advance check completed. Date was advanced.")
            else:
                await message.channel.send("No advancement needed at this time.")
                
        elif message.content == "!help":
            await message.channel.send(
                "**Available Commands:**\n"
                "!date - Show approximated current date\n"
                "!current - Detailed date information\n"
                "!advance - Advance base period by 4 months (admin)\n"
                "!status - Bot status information\n"
                "!auto-check - Force auto-advance check\n"
                "!ping - Check if bot is responsive\n"
                "!help - Show this message"
            )

# Run bot
if __name__ == "__main__":
    try:
        bot = GovernmentBot(intents=intents)
        bot.run(TOKEN)
    except Exception as e:
        print(f"Error: {e}")
