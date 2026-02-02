import discord
import os
import json
import asyncio
import threading
import time
from datetime import datetime, time as dt_time, timedelta
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

# Global state and save lock
state = {}
save_lock = threading.Lock()
save_interval = 60  # Save every 60 seconds
last_save_time = time.time()

# Load state with migration support
def load_state():
    global state
    try:
        with open(DATA_FILE, "r") as f:
            state = json.load(f)
            
        # MIGRATION: Convert old state format to new format
        if "last_run" in state and "last_advance_date" not in state:
            print("Migrating from old state format...")
            state["last_advance_date"] = state["last_run"]
            state.pop("last_run", None)
            
        # Ensure all required keys exist
        now = datetime.now(EST)
        defaults = {
            "current_date": now.isoformat(),
            "last_advance_date": now.date().isoformat(),
            "last_check_timestamp": now.isoformat(),
            "notifications_enabled": True,
            "time_format": "12hr",
            "command_history": []
        }
        
        for key, default_value in defaults.items():
            if key not in state:
                state[key] = default_value
                print(f"Added missing key: {key}")
        
        save_state_internal()  # Save migrated state
        return state
        
    except FileNotFoundError:
        # Create new state file
        now = datetime.now(EST)
        state = {
            "current_date": now.isoformat(),
            "last_advance_date": now.date().isoformat(),
            "last_check_timestamp": now.isoformat(),
            "notifications_enabled": True,
            "time_format": "12hr",
            "command_history": []
        }
        save_state_internal()
        print("Created new state file")
        return state
    except Exception as e:
        print(f"Error loading state: {e}")
        now = datetime.now(EST)
        state = {
            "current_date": now.isoformat(),
            "last_advance_date": now.date().isoformat(),
            "last_check_timestamp": now.isoformat(),
            "notifications_enabled": True,
            "time_format": "12hr",
            "command_history": []
        }
        return state

def save_state_internal():
    """Save state to file (thread-safe)"""
    global last_save_time
    with save_lock:
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(state, f, indent=2)
            last_save_time = time.time()
            print(f"💾 State saved to file at {datetime.now().strftime('%H:%M:%S')}")
            return True
        except Exception as e:
            print(f"❌ Error saving state: {e}")
            return False

def auto_save_worker(stop_event):
    """Background thread that auto-saves state periodically"""
    while not stop_event.is_set():
        time.sleep(save_interval)
        if not stop_event.is_set():
            save_state_internal()

# Initialize
load_state()
current_date = datetime.fromisoformat(state.get("current_date", datetime.now(EST).isoformat()))
last_advance_date = datetime.fromisoformat(state.get("last_advance_date", datetime.now(EST).date().isoformat())).date()

print(f"Current in-game date: {current_date.strftime('%B %Y')}")
print(f"Last advance date: {last_advance_date.strftime('%Y-%m-%d')}")

# Start auto-save thread
stop_event = threading.Event()
auto_save_thread = threading.Thread(target=auto_save_worker, args=(stop_event,), daemon=True)
auto_save_thread.start()

def log_command(user_id, command):
    """Log the last 10 commands for debugging"""
    if "command_history" not in state:
        state["command_history"] = []
    
    state["command_history"].append({
        "user": str(user_id),
        "command": command,
        "timestamp": datetime.now(EST).isoformat()
    })
    
    # Keep only last 10 commands
    if len(state["command_history"]) > 10:
        state["command_history"] = state["command_history"][-10:]
    
    save_state_internal()

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
    day_progress = (reference_time.hour * 3600 + reference_time.minute * 60 + reference_time.second) / 86400.0
    
    # For simplicity, assume each month has 30 days
    days_into_month = day_progress * 30
    
    # Create the approximated date
    approximated_date = base_date + timedelta(days=days_into_month)
    
    return approximated_date

def format_time(dt, time_format="12hr"):
    """Format time in 12hr or 24hr format"""
    if time_format == "24hr":
        return dt.strftime("%H:%M")
    else:
        return dt.strftime("%I:%M %p")

async def check_and_advance_date(channel):
    """Check if we need to advance the date and do it if needed"""
    now = datetime.now(EST)
    today = now.date()
    
    # Get the last advance date with safe access
    last_advance_str = state.get("last_advance_date", today.isoformat())
    last_advance = datetime.fromisoformat(last_advance_str).date()
    
    # Get the last check timestamp
    last_check_str = state.get("last_check_timestamp", now.isoformat())
    last_check = datetime.fromisoformat(last_check_str)
    
    # Only advance if:
    # 1. It's past midnight (hour 0-1)
    # 2. AND we haven't advanced today yet
    # 3. AND last advance was yesterday or earlier
    should_advance = (
        now.time().hour == 0 and 
        now.time().minute <= 1 and
        last_advance < today
    )
    
    # Also check if we missed any days (bot was offline)
    days_missed = (today - last_advance).days
    
    if should_advance and days_missed > 0:
        print(f"Midnight detected. Days since last advance: {days_missed}")
        
        # Calculate months to advance (4 months per day missed, max 12)
        months_to_advance = min(4 * days_missed, 12)
        
        # Get current date with safe access
        current_date_str = state.get("current_date", now.isoformat())
        current = datetime.fromisoformat(current_date_str)
        new_date = current + relativedelta(months=months_to_advance)
        
        # Update state
        state["current_date"] = new_date.isoformat()
        state["last_advance_date"] = today.isoformat()
        state["last_check_timestamp"] = now.isoformat()
        save_state_internal()
        
        print(f"Advanced from {current.strftime('%B %Y')} to {new_date.strftime('%B %Y')}")
        
        # Send notification if channel is available and notifications are enabled
        if channel and state.get("notifications_enabled", True):
            await channel.send(
                f"**Government Time Advancement**\n"
                f"Real days passed: **{days_missed}**\n"
                f"In-game months advanced: **{months_to_advance}**\n"
                f"New in-game date: **{new_date.strftime('%B %Y')}** (EST)"
            )
        
        return True, days_missed, months_to_advance
    else:
        # Update last check timestamp
        state["last_check_timestamp"] = now.isoformat()
        
        # If it's midnight but we already advanced today, just log it
        if now.time().hour == 0 and now.time().minute <= 1:
            if last_advance == today:
                print(f"Already advanced today at {state.get('last_check_timestamp', 'unknown')}")
            else:
                print(f"Not midnight yet or already advanced. Last advance: {last_advance}")
        
        save_state_internal()
        return False, 0, 0

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True

class GovernmentBot(discord.Client):
    def __init__(self, intents):
        super().__init__(intents=intents)
        self.advance_channel = None
        
    async def on_ready(self):
        print("=" * 60)
        print(f"Connected as {self.user}")
        
        # Safe access to state values
        current_date_str = state.get("current_date", datetime.now(EST).isoformat())
        last_advance_str = state.get("last_advance_date", datetime.now(EST).date().isoformat())
        
        current_date = datetime.fromisoformat(current_date_str)
        last_advance = datetime.fromisoformat(last_advance_str).date()
        
        print(f"Current date: {current_date.strftime('%B %Y')}")
        print(f"Last advance: {last_advance.strftime('%Y-%m-%d')}")
        print(f"Auto-save: Every {save_interval} seconds")
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
        now = datetime.now(EST)
        print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S EST')}")
        
        advanced, days_missed, months_advanced = await check_and_advance_date(self.advance_channel)
        if advanced:
            print(f"Auto-advance completed: {days_missed} days -> {months_advanced} months")
        else:
            print("No advancement needed at this time")
        
    async def on_message(self, message):
        if message.author.bot:
            return
            
        # Log the command
        log_command(message.author.id, message.content)
        print(f"[{message.author}] {message.content}")
        
        # ===== MAIN COMMANDS =====
        
        if message.content == "!date":
            # Safe access to state values
            current_date_str = state.get("current_date", datetime.now(EST).isoformat())
            last_advance_str = state.get("last_advance_date", datetime.now(EST).date().isoformat())
            
            base_date = datetime.fromisoformat(current_date_str)
            last_advance = datetime.fromisoformat(last_advance_str).date()
            now = datetime.now(EST)
            time_fmt = state.get("time_format", "12hr")
            
            # Calculate approximated current date
            approx_date = approximate_current_date(base_date, now)
            
            # Calculate time until next advancement (midnight)
            next_midnight = datetime.combine(now.date() + timedelta(days=1), dt_time(0, 0, tzinfo=EST))
            time_until = next_midnight - now
            hours_until = time_until.seconds // 3600
            minutes_until = (time_until.seconds % 3600) // 60
            
            # Calculate days since last advance
            days_since_last = (now.date() - last_advance).days
            
            # Format the response
            response = (
                f"**Current Date:**\n"
                f"Base Period: {base_date.strftime('%B %Y')}\n"
                f"Current Approximation: {approx_date.strftime('%B %d, %Y')}\n"
                f"Real Time: {format_time(now, time_fmt)} EST\n"
                f"\n"
                f"**Advancement Info:**\n"
                f"Last Advance: {last_advance.strftime('%Y-%m-%d')} ({days_since_last} day{'s' if days_since_last != 1 else ''} ago)\n"
                f"Next Auto-Advance: {hours_until}h {minutes_until}m\n"
                f"Rate: 4 in-game months per real day\n"
                f"\n"
                f"The date progresses through {base_date.strftime('%B %Y')} in real-time."
            )
            await message.channel.send(response)
            
        elif message.content.startswith("!advance"):
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("You are not authorized to use this command.")
                return
            
            # Check for custom advancement amount
            parts = message.content.split()
            months_to_advance = 4  # Default
            
            if len(parts) > 1 and parts[1].isdigit():
                months_to_advance = int(parts[1])
                # Limit to reasonable amount
                months_to_advance = min(max(1, months_to_advance), 48)
                
            current_date_str = state.get("current_date", datetime.now(EST).isoformat())
            current = datetime.fromisoformat(current_date_str)
            new_date = current + relativedelta(months=months_to_advance)
            
            state["current_date"] = new_date.isoformat()
            state["last_advance_date"] = datetime.now(EST).date().isoformat()
            save_state_internal()
            
            await message.channel.send(
                f"Manual advance complete.\n"
                f"Advanced by: **{months_to_advance}** month(s)\n"
                f"New base period: **{new_date.strftime('%B %Y')}**\n"
                f"Next auto-advance: Tomorrow at midnight EST"
            )
            
        elif message.content == "!ping":
            # Calculate uptime approximation
            now = datetime.now(EST)
            minute_of_hour = now.minute
            uptime_minutes = minute_of_hour % 30
            last_advance_str = state.get("last_advance_date", datetime.now(EST).date().isoformat())
            last_advance = datetime.fromisoformat(last_advance_str).strftime('%Y-%m-%d')
            
            await message.channel.send(
                f"**Bot Status**\n"
                f"Online\n"
                f"Current uptime: ~{uptime_minutes} minutes\n"
                f"Last advance: {last_advance}\n"
                f"Next restart: in {30 - uptime_minutes} minutes"
            )
            
        elif message.content == "!status":
            # Safe access to state values
            current_date_str = state.get("current_date", datetime.now(EST).isoformat())
            last_advance_str = state.get("last_advance_date", datetime.now(EST).date().isoformat())
            
            current = datetime.fromisoformat(current_date_str)
            last_advance = datetime.fromisoformat(last_advance_str).date()
            now_date = datetime.now(EST).date()
            days_since = (now_date - last_advance).days
            
            # Calculate next advancement time
            next_midnight = datetime.combine(now_date + timedelta(days=1), dt_time(0, 0, tzinfo=EST))
            time_until = next_midnight - datetime.now(EST)
            hours_until = time_until.seconds // 3600
            minutes_until = (time_until.seconds % 3600) // 60
            
            # Calculate when next advance will occur
            next_advance_date = last_advance + timedelta(days=1)
            next_advance_days = (next_advance_date - now_date).days
            
            status_msg = (
                f"**Bot Status**\n"
                f"Current Base Period: {current.strftime('%B %Y')}\n"
                f"Last Auto-Advance: {last_advance.strftime('%Y-%m-%d')}\n"
                f"Days since last advance: {days_since}\n"
                f"Next Auto-Advance: {'Today' if next_advance_days == 0 else f'In {next_advance_days} day(s)'}\n"
                f"Time until midnight: {hours_until}h {minutes_until}m\n"
                f"Notifications: {'✅ Enabled' if state.get('notifications_enabled', True) else '❌ Disabled'}\n"
                f"Time Format: {state.get('time_format', '12hr')}"
            )
            await message.channel.send(status_msg)
            
        elif message.content == "!save" and message.author.id == ADMIN_USER_ID:
            saved = save_state_internal()
            if saved:
                await message.channel.send("State saved successfully.")
            else:
                await message.channel.send("Failed to save state.")
                
        elif message.content == "!lastsave" and message.author.id == ADMIN_USER_ID:
            last_save_str = datetime.fromtimestamp(last_save_time).strftime('%Y-%m-%d %H:%M:%S')
            await message.channel.send(f"Last save: {last_save_str}")
            
        elif message.content == "!help":
            await message.channel.send(
                "**Main Commands:**\n"
                "`!date` - Show current approximated date\n"
                "`!status` - Bot status and settings\n"
                "`!ping` - Check bot responsiveness\n"
                "`!advance [months]` - Advance by months (admin, default: 4)\n"
                "`!save` - Manually save state (admin)\n"
                "`!lastsave` - Show last save time (admin)\n"
                "\n"
                f"Admin: <@{ADMIN_USER_ID}>"
            )

# Run bot
if __name__ == "__main__":
    try:
        bot = GovernmentBot(intents=intents)
        
        # Save state on shutdown
        import atexit
        def shutdown():
            stop_event.set()
            auto_save_thread.join(timeout=5)
            save_state_internal()
            print("Bot shutdown complete")
        
        atexit.register(shutdown)
        
        bot.run(TOKEN)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        shutdown()
