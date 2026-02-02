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

# ... (keep all your existing functions: approximate_current_date, format_time, check_and_advance_date)

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
        
        current_date_str = state.get("current_date", datetime.now(EST).isoformat())
        last_advance_str = state.get("last_advance_date", datetime.now(EST).date().isoformat())
        
        current_date = datetime.fromisoformat(current_date_str)
        last_advance = datetime.fromisoformat(last_advance_str).date()
        
        print(f"Current date: {current_date.strftime('%B %Y')}")
        print(f"Last advance: {last_advance.strftime('%Y-%m-%d')}")
        print(f"Auto-save: Every {save_interval} seconds")
        print("=" * 60)
        
        if CHANNEL_ID:
            self.advance_channel = self.get_channel(CHANNEL_ID)
            if self.advance_channel:
                print(f"Notification channel: #{self.advance_channel.name}")
        
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="the calendar | !date"
        ))
        
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
            
        log_command(message.author.id, message.content)
        print(f"[{message.author}] {message.content}")
        
        # ... (keep all your existing command handlers)
        
        # Add a new command to force save
        if message.content == "!save" and message.author.id == ADMIN_USER_ID:
            saved = save_state_internal()
            if saved:
                await message.channel.send("State saved successfully.")
            else:
                await message.channel.send("Failed to save state.")
                
        elif message.content == "!lastsave" and message.author.id == ADMIN_USER_ID:
            last_save_str = datetime.fromtimestamp(last_save_time).strftime('%Y-%m-%d %H:%M:%S')
            await message.channel.send(f"Last save: {last_save_str}")

# Run bot
if __name__ == "__main__":
    try:
        bot = GovernmentBot(intents=intents)
        
        # Save state on shutdown
        import atexit
        atexit.register(lambda: (stop_event.set(), auto_save_thread.join(timeout=5), save_state_internal()))
        
        bot.run(TOKEN)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Ensure we save before exit
        stop_event.set()
        auto_save_thread.join(timeout=5)
        save_state_internal()
        print("Bot shutdown complete")
