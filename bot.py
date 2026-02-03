import discord
import os
import json
import asyncio
import threading
import time
import subprocess
from datetime import datetime, time as dt_time, timedelta
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", 0))
ADMIN_USER_ID = 1367955172373823629
DATA_FILE = "gov_state.json"
EST = ZoneInfo("America/New_York")

print("=" * 60)
print("GOVERNMENT DATE BOT")
print("=" * 60)
print(f"Token: {'PRESENT' if TOKEN else 'MISSING'}")
print(f"Channel ID: {CHANNEL_ID}")
print(f"Admin ID: {ADMIN_USER_ID}")

# Global state and save system
state = {}
save_lock = threading.Lock()
save_interval = 60  # Auto-save every 60 seconds
last_save_time = time.time()
auto_save_thread = None
stop_event = threading.Event()

def load_state():
    global state
    try:
        with open(DATA_FILE, "r") as f:
            state = json.load(f)
            
        # Migration from old formats
        if "last_run" in state and "last_advance_date" not in state:
            print("Migrating from old state format...")
            state["last_advance_date"] = state["last_run"]
            del state["last_run"]
            
        # Ensure all required keys exist
        now = datetime.now(EST)
        defaults = {
            "current_date": now.isoformat(),
            "last_advance_date": now.date().isoformat(),
            "last_check_timestamp": now.isoformat(),
            "notifications_enabled": True,
            "time_format": "12hr",
            "command_history": [],
            "advancement_history": [],
            "settings": {
                "max_advance_per_run": 12,
                "months_per_day": 4,
                "auto_save": True,
                "debug_mode": False
            }
        }
        
        for key, default_value in defaults.items():
            if key not in state:
                state[key] = default_value
                print(f"Added missing key: {key}")
        
        save_state()
        return state
        
    except FileNotFoundError:
        print("Creating new state file...")
        now = datetime.now(EST)
        state = {
            "current_date": now.isoformat(),
            "last_advance_date": now.date().isoformat(),
            "last_check_timestamp": now.isoformat(),
            "notifications_enabled": True,
            "time_format": "12hr",
            "command_history": [],
            "advancement_history": [],
            "settings": {
                "max_advance_per_run": 12,
                "months_per_day": 4,
                "auto_save": True,
                "debug_mode": False
            }
        }
        save_state()
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
            "command_history": [],
            "advancement_history": [],
            "settings": {
                "max_advance_per_run": 12,
                "months_per_day": 4,
                "auto_save": True,
                "debug_mode": False
            }
        }
        return state

def save_state():
    global last_save_time
    with save_lock:
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(state, f, indent=2)
            last_save_time = time.time()
            print(f"State saved at {datetime.now().strftime('%H:%M:%S')}")
            return True
        except Exception as e:
            print(f"Error saving state: {e}")
            return False

def auto_save_worker():
    """Background thread for auto-saving"""
    while not stop_event.is_set():
        time.sleep(save_interval)
        if not stop_event.is_set() and state.get("settings", {}).get("auto_save", True):
            save_state()

# Initialize state
load_state()
current_date = datetime.fromisoformat(state.get("current_date", datetime.now(EST).isoformat()))
last_advance_date = datetime.fromisoformat(state.get("last_advance_date", datetime.now(EST).date().isoformat())).date()
today = datetime.now(EST).date()

print(f"Current in-game date: {current_date.strftime('%B %Y')}")
print(f"Last advance: {last_advance_date.strftime('%Y-%m-%d')}")
print(f"Today: {today.strftime('%Y-%m-%d')}")
print(f"Auto-save: Every {save_interval} seconds")

# Start auto-save thread
auto_save_thread = threading.Thread(target=auto_save_worker, daemon=True)
auto_save_thread.start()

# ==================== UTILITY FUNCTIONS ====================

def log_command(user_id, command):
    """Log command to history"""
    if "command_history" not in state:
        state["command_history"] = []
    
    state["command_history"].append({
        "user": str(user_id),
        "command": command,
        "timestamp": datetime.now(EST).isoformat()
    })
    
    # Keep only last 50 commands
    if len(state["command_history"]) > 50:
        state["command_history"] = state["command_history"][-50:]
    
    if state.get("settings", {}).get("auto_save", True):
        save_state()

def log_advancement(days_missed, months_advanced, old_date, new_date):
    """Log advancement to history"""
    if "advancement_history" not in state:
        state["advancement_history"] = []
    
    state["advancement_history"].append({
        "timestamp": datetime.now(EST).isoformat(),
        "days_missed": days_missed,
        "months_advanced": months_advanced,
        "old_date": old_date.isoformat(),
        "new_date": new_date.isoformat(),
        "type": "auto" if days_missed > 1 else "scheduled"
    })
    
    # Keep only last 100 advancements
    if len(state["advancement_history"]) > 100:
        state["advancement_history"] = state["advancement_history"][-100:]

def approximate_current_date(base_date, reference_time):
    """
    Calculate current approximation within the month
    Returns: Current approximated datetime
    """
    # Calculate progress through day (0.0 to 1.0)
    seconds_in_day = reference_time.hour * 3600 + reference_time.minute * 60 + reference_time.second
    day_progress = seconds_in_day / 86400.0
    
    # Assume 30 days per month for approximation
    days_into_month = day_progress * 30
    
    # Calculate exact date
    approximated_date = base_date + timedelta(days=days_into_month)
    
    return approximated_date

def format_time(dt, time_format=None):
    """Format time according to user preference"""
    if time_format is None:
        time_format = state.get("time_format", "12hr")
    
    if time_format == "24hr":
        return dt.strftime("%H:%M:%S")
    else:
        return dt.strftime("%I:%M:%S %p")

def format_date_long(dt):
    """Format date in long readable form"""
    return dt.strftime("%A, %B %d, %Y")

def calculate_time_until(target_time):
    """Calculate time until a target time"""
    now = datetime.now(EST)
    if target_time <= now:
        target_time += timedelta(days=1)
    
    time_diff = target_time - now
    total_seconds = int(time_diff.total_seconds())
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    return hours, minutes, seconds

async def get_notification_channel(client):
    """Get the notification channel with proper checks"""
    if not CHANNEL_ID:
        return None
    
    try:
        channel = client.get_channel(CHANNEL_ID)
        if channel is None:
            try:
                channel = await client.fetch_channel(CHANNEL_ID)
            except:
                return None
        
        # Check permissions
        if isinstance(channel, discord.TextChannel):
            permissions = channel.permissions_for(channel.guild.me)
            if not permissions.send_messages:
                print(f"No send permission in #{channel.name}")
                return None
        
        return channel
    except Exception as e:
        print(f"Error getting channel: {e}")
        return None

# ==================== ADVANCEMENT LOGIC ====================

async def check_and_advance_date(client, notification_channel=None):
    """
    Check if date needs advancement and perform it
    Returns: (advanced, days_missed, months_advanced, new_date)
    """
    now = datetime.now(EST)
    today = now.date()
    
    last_advance_str = state.get("last_advance_date", today.isoformat())
    last_advance = datetime.fromisoformat(last_advance_str).date()
    
    days_missed = (today - last_advance).days
    
    if state.get("settings", {}).get("debug_mode", False):
        print(f"DEBUG Advance Check:")
        print(f"   Last advance: {last_advance}")
        print(f"   Today: {today}")
        print(f"   Days missed: {days_missed}")
        print(f"   Current time: {now.strftime('%H:%M:%S EST')}")
    
    # Advance if we've missed days
    if days_missed > 0:
        print(f"ADVANCE NEEDED: {days_missed} day(s) missed")
        
        # Calculate advancement
        months_per_day = state.get("settings", {}).get("months_per_day", 4)
        max_per_run = state.get("settings", {}).get("max_advance_per_run", 12)
        months_to_advance = min(months_per_day * days_missed, max_per_run)
        
        current_date_str = state.get("current_date", now.isoformat())
        current = datetime.fromisoformat(current_date_str)
        new_date = current + relativedelta(months=months_to_advance)
        
        # Log before updating
        log_advancement(days_missed, months_to_advance, current, new_date)
        
        # Update state
        state["current_date"] = new_date.isoformat()
        state["last_advance_date"] = today.isoformat()
        state["last_check_timestamp"] = now.isoformat()
        
        if state.get("settings", {}).get("auto_save", True):
            save_state()
        
        print(f"ADVANCED: {current.strftime('%B %Y')} -> {new_date.strftime('%B %Y')}")
        print(f"   Months: {months_to_advance}")
        print(f"   Real days: {days_missed}")
        
        # Send notification
        if notification_channel and state.get("notifications_enabled", True):
            try:
                if days_missed == 1:
                    message = (
                        f"Government Time Advancement\n"
                        f"1 real day has passed\n"
                        f"Advanced by {months_to_advance} in-game months\n"
                        f"New in-game date: {new_date.strftime('%B %Y')}\n"
                        f"Time: {now.strftime('%I:%M:%S %p EST')}\n"
                        f"--------------------------------"
                    )
                else:
                    remaining_days = days_missed - (months_to_advance // months_per_day)
                    message = (
                        f"Government Time Advancement\n"
                        f"Real days passed: {days_missed}\n"
                        f"In-game months advanced: {months_to_advance}\n"
                        f"New in-game date: {new_date.strftime('%B %Y')}\n"
                        f"Time: {now.strftime('%I:%M:%S %p EST')}\n"
                    )
                    if remaining_days > 0:
                        message += f"Note: {remaining_days} day(s) will advance tomorrow\n"
                    message += "--------------------------------"
                
                await notification_channel.send(message)
                print(f"Notification sent to channel")
            except discord.Forbidden:
                print(f"No permission to send in channel")
            except Exception as e:
                print(f"Failed to send notification: {e}")
        
        return True, days_missed, months_to_advance, new_date
    
    # Update timestamp even if no advancement
    state["last_check_timestamp"] = now.isoformat()
    if state.get("settings", {}).get("auto_save", True):
        save_state()
    
    return False, 0, 0, None

# ==================== DISCORD BOT ====================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # REMEMBER: You must enable "Server Members Intent" in Discord Developer Portal

class GovernmentBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.notification_channel = None
        self.start_time = datetime.now(EST)
        
    async def on_ready(self):
        print("=" * 60)
        print(f"BOT CONNECTED: {self.user}")
        print(f"Bot ID: {self.user.id}")
        print(f"Start time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S EST')}")
        print(f"Servers: {len(self.guilds)}")
        print("=" * 60)
        
        # Get current state
        current = datetime.fromisoformat(state.get("current_date", datetime.now(EST).isoformat()))
        last_adv = datetime.fromisoformat(state.get("last_advance_date", datetime.now(EST).date().isoformat())).date()
        
        print(f"Current date: {current.strftime('%B %Y')}")
        print(f"Last advance: {last_adv.strftime('%Y-%m-%d')}")
        print(f"Notifications: {'ON' if state.get('notifications_enabled', True) else 'OFF'}")
        
        # Get notification channel
        self.notification_channel = await get_notification_channel(self)
        if self.notification_channel:
            print(f"Notification channel: #{self.notification_channel.name}")
        else:
            print(f"No notification channel or no permissions")
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{current.strftime('%B %Y')} | !help"
            )
        )
        
        # Check for advancements
        print("Checking for missed advancements...")
        advanced, days_missed, months_advanced, new_date = await check_and_advance_date(
            self, self.notification_channel
        )
        
        if advanced:
            print(f"Auto-advance completed: {months_advanced} months")
            # Update status with new date
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{new_date.strftime('%B %Y')} | !help"
                )
            )
        else:
            print("No advancement needed")
        
        print("=" * 60)
        
    async def on_message(self, message):
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Log command
        log_command(message.author.id, message.content)
        
        # Debug logging
        if state.get("settings", {}).get("debug_mode", False):
            print(f"[DEBUG] {message.author} in #{message.channel}: {message.content}")
        else:
            print(f"[{message.author}]: {message.content}")
        
        # ==================== COMMAND HANDLING ====================
        
        # !date - Show current date
        if message.content == "!date":
            current = datetime.fromisoformat(state["current_date"])
            now = datetime.now(EST)
            approx_date = approximate_current_date(current, now)
            time_fmt = state.get("time_format", "12hr")
            
            last_adv = datetime.fromisoformat(state["last_advance_date"]).date()
            days_since = (now.date() - last_adv).days
            
            # Calculate next midnight
            next_midnight = datetime.combine(now.date() + timedelta(days=1), dt_time(0, 0, tzinfo=EST))
            hours, minutes, seconds = calculate_time_until(next_midnight)
            
            response = (
                f"Current Date Information\n"
                f"--------------------------------\n"
                f"Base Period: {current.strftime('%B %Y')}\n"
                f"Current Approximation: {approx_date.strftime('%B %d, %Y')}\n"
                f"Real Time: {format_time(now, time_fmt)} EST\n"
                f"\n"
                f"Advancement Status\n"
                f"--------------------------------\n"
                f"Last Advance: {last_adv.strftime('%Y-%m-%d')} ({days_since} day{'s' if days_since != 1 else ''} ago)\n"
                f"Next Auto-Advance: {hours}h {minutes}m {seconds}s\n"
                f"Rate: {state.get('settings', {}).get('months_per_day', 4)} months per real day\n"
                f"Max per run: {state.get('settings', {}).get('max_advance_per_run', 12)} months\n"
                f"\n"
                f"The date progresses through {current.strftime('%B %Y')} in real-time."
            )
            await message.channel.send(response)

        # Add this to your command handling section (around line where !advance is)

        elif message.content == "!send":
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("You are not authorized to use this command.")
                return
            
            # Get notification channel
            channel = await get_notification_channel(self)
            if not channel:
                await message.channel.send("ERROR: Cannot access notification channel. Check permissions and channel ID.")
                return
            
            # Get current date info
            current = datetime.fromisoformat(state["current_date"])
            now = datetime.now(EST)
            
            # Create the message to send
            message_content = (
                f"Government Time Advancement\n"
                f"1 real day has passed\n"
                f"Advanced by 4 in-game months\n"
                f"New in-game date: {current.strftime('%B %Y')}\n"
                f"Time: {now.strftime('%I:%M:%S %p EST')}\n"
                f"--------------------------------"
            )
            
            try:
                # Force send to notification channel
                await channel.send(message_content)
                await message.channel.send(f"✅ Message sent to #{channel.name}")
                print(f"FORCE SENT: Message sent to #{channel.name}")
            except discord.Forbidden:
                await message.channel.send("❌ ERROR: Bot doesn't have permission to send messages in that channel.")
            except Exception as e:
                await message.channel.send(f"❌ ERROR: Failed to send message: {str(e)}")
            
        # !advance [months] - Manual advance (admin)
        elif message.content.startswith("!advance"):
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("You are not authorized to use this command.")
                return
            
            parts = message.content.split()
            months_to_advance = state.get("settings", {}).get("months_per_day", 4)
            
            if len(parts) > 1:
                try:
                    months_to_advance = int(parts[1])
                    # Limit to reasonable amount
                    max_months = state.get("settings", {}).get("max_advance_per_run", 12) * 3
                    months_to_advance = min(max(1, months_to_advance), max_months)
                except ValueError:
                    await message.channel.send("Invalid number. Usage: !advance [months]")
                    return
            
            current = datetime.fromisoformat(state["current_date"])
            new_date = current + relativedelta(months=months_to_advance)
            
            # Log the manual advancement
            log_advancement(0, months_to_advance, current, new_date)
            
            # Update state
            state["current_date"] = new_date.isoformat()
            state["last_advance_date"] = datetime.now(EST).date().isoformat()
            save_state()
            
            # Update bot status
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{new_date.strftime('%B %Y')} | !help"
                )
            )
            
            response = (
                f"Manual Advance Complete\n"
                f"--------------------------------\n"
                f"Advanced by: {months_to_advance} month{'s' if months_to_advance != 1 else ''}\n"
                f"New date: {new_date.strftime('%B %Y')}\n"
                f"Time: {datetime.now(EST).strftime('%I:%M:%S %p EST')}\n"
                f"By: {message.author.mention}\n"
                f"\n"
                f"Next auto-advance will occur at midnight EST."
            )
            await message.channel.send(response)
            
        # !force - Force advance check (admin)
        elif message.content == "!force":
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("You are not authorized to use this command.")
                return
            
            await message.channel.send("Force checking for advancements...")
            advanced, days_missed, months_advanced, new_date = await check_and_advance_date(
                self, message.channel  # Use command channel
            )
            
            if advanced:
                response = (
                    f"Force Advance Completed\n"
                    f"--------------------------------\n"
                    f"Days missed: {days_missed}\n"
                    f"Months advanced: {months_advanced}\n"
                    f"New date: {new_date.strftime('%B %Y')}\n"
                    f"Time: {datetime.now(EST).strftime('%I:%M:%S %p EST')}"
                )
            else:
                last_adv = datetime.fromisoformat(state["last_advance_date"]).date()
                response = (
                    f"No Advancement Needed\n"
                    f"--------------------------------\n"
                    f"Last advance: {last_adv.strftime('%Y-%m-%d')}\n"
                    f"Today: {datetime.now(EST).date().strftime('%Y-%m-%d')}\n"
                    f"Current time: {datetime.now(EST).strftime('%I:%M:%S %p EST')}"
                )
            
            await message.channel.send(response)  # Always post response here
                    
        # !setdate <Month> <Year> - Set custom date (admin)
        elif message.content.startswith("!setdate"):
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("You are not authorized to use this command.")
                return
            
            parts = message.content.split()
            if len(parts) != 3:
                await message.channel.send(
                    "Usage: !setdate <Month> <Year>\n"
                    "Example: !setdate May 2026\n"
                    "Example: !setdate December 2027"
                )
                return
            
            try:
                month_name = parts[1]
                year = int(parts[2])
                
                # Parse month
                month_num = datetime.strptime(month_name, "%B").month
                new_date = datetime(year, month_num, 1, tzinfo=EST)
                
                # Get old date for logging
                old_date = datetime.fromisoformat(state["current_date"])
                
                # Update state
                state["current_date"] = new_date.isoformat()
                state["last_advance_date"] = datetime.now(EST).date().isoformat()
                save_state()
                
                # Update bot status
                await self.change_presence(
                    activity=discord.Activity(
                        type=discord.ActivityType.watching,
                        name=f"{new_date.strftime('%B %Y')} | !help"
                    )
                )
                
                response = (
                    f"Date Successfully Set\n"
                    f"--------------------------------\n"
                    f"New date: {new_date.strftime('%B %Y')}\n"
                    f"Previous date: {old_date.strftime('%B %Y')}\n"
                    f"Last advance reset to: {datetime.now(EST).date().strftime('%Y-%m-%d')}\n"
                    f"By: {message.author.mention}"
                )
                await message.channel.send(response)
                
            except ValueError:
                await message.channel.send(
                    "Invalid date format.\n"
                    "Valid months: January, February, March, April, May, June, July, "
                    "August, September, October, November, December\n"
                    "Example: !setdate May 2026"
                )
                
        # !status - Bot status
        elif message.content == "!status":
            current = datetime.fromisoformat(state["current_date"])
            last_adv = datetime.fromisoformat(state["last_advance_date"]).date()
            today = datetime.now(EST).date()
            days_since = (today - last_adv).days
            
            # Calculate next midnight
            next_midnight = datetime.combine(today + timedelta(days=1), dt_time(0, 0, tzinfo=EST))
            hours, minutes, seconds = calculate_time_until(next_midnight)
            
            # Calculate uptime
            uptime = datetime.now(EST) - self.start_time
            uptime_str = f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds%3600)//60}m"
            
            response = (
                f"Bot Status\n"
                f"--------------------------------\n"
                f"Bot: {self.user}\n"
                f"ID: {self.user.id}\n"
                f"Uptime: {uptime_str}\n"
                f"Servers: {len(self.guilds)}\n"
                f"\n"
                f"Date Status\n"
                f"--------------------------------\n"
                f"Current date: {current.strftime('%B %Y')}\n"
                f"Last advance: {last_adv.strftime('%Y-%m-%d')}\n"
                f"Days since advance: {days_since}\n"
                f"Next auto-advance: {hours}h {minutes}m {seconds}s\n"
                f"\n"
                f"Settings\n"
                f"--------------------------------\n"
                f"Notifications: {'ON' if state.get('notifications_enabled', True) else 'OFF'}\n"
                f"Time format: {state.get('time_format', '12hr')}\n"
                f"Rate: {state.get('settings', {}).get('months_per_day', 4)} months/day\n"
                f"Max/run: {state.get('settings', {}).get('max_advance_per_run', 12)} months\n"
                f"Auto-save: {'ON' if state.get('settings', {}).get('auto_save', True) else 'OFF'}\n"
                f"\n"
                f"Admin: <@{ADMIN_USER_ID}>"
            )
            await message.channel.send(response)
            
        # !notifications [on/off] - Toggle notifications (admin)
        elif message.content.startswith("!notifications"):
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("You are not authorized to use this command.")
                return
            
            parts = message.content.split()
            if len(parts) > 1:
                setting = parts[1].lower()
                if setting in ["on", "enable", "yes", "true"]:
                    state["notifications_enabled"] = True
                    response = "Notifications ENABLED"
                elif setting in ["off", "disable", "no", "false"]:
                    state["notifications_enabled"] = False
                    response = "Notifications DISABLED"
                else:
                    response = f"Invalid setting. Use !notifications on or !notifications off"
            else:
                # Toggle
                current = state.get("notifications_enabled", True)
                state["notifications_enabled"] = not current
                response = f"Notifications {'ENABLED' if not current else 'DISABLED'}"
            
            save_state()
            await message.channel.send(response)
            
        # !timeformat [12hr/24hr] - Change time format
        elif message.content.startswith("!timeformat"):
            parts = message.content.split()
            if len(parts) > 1:
                new_format = parts[1].lower()
                if new_format in ["12hr", "12", "12h"]:
                    state["time_format"] = "12hr"
                    response = "Time format set to 12-hour (AM/PM)"
                elif new_format in ["24hr", "24", "24h"]:
                    state["time_format"] = "24hr"
                    response = "Time format set to 24-hour"
                else:
                    response = "Invalid format. Use 12hr or 24hr"
            else:
                # Toggle
                current = state.get("time_format", "12hr")
                state["time_format"] = "24hr" if current == "12hr" else "12hr"
                response = f"Time format changed to {state['time_format']}"
            
            save_state()
            await message.channel.send(response)
            
        # !save - Manual save
        elif message.content == "!save":
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("You are not authorized to use this command.")
                return
            
            if save_state():
                last_save = datetime.fromtimestamp(last_save_time).strftime('%Y-%m-%d %H:%M:%S')
                await message.channel.send(f"State saved successfully at {last_save}")
            else:
                await message.channel.send("Failed to save state")
                
        # !debug [on/off] - Toggle debug mode (admin)
        elif message.content.startswith("!debug"):
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("You are not authorized to use this command.")
                return
            
            if "settings" not in state:
                state["settings"] = {}
            
            parts = message.content.split()
            if len(parts) > 1:
                setting = parts[1].lower()
                if setting in ["on", "enable", "yes", "true"]:
                    state["settings"]["debug_mode"] = True
                    response = "Debug mode ENABLED"
                elif setting in ["off", "disable", "no", "false"]:
                    state["settings"]["debug_mode"] = False
                    response = "Debug mode DISABLED"
                else:
                    current = state["settings"].get("debug_mode", False)
                    response = f"Debug mode is currently {'ENABLED' if current else 'DISABLED'}"
            else:
                # Toggle
                current = state["settings"].get("debug_mode", False)
                state["settings"]["debug_mode"] = not current
                response = f"Debug mode {'ENABLED' if not current else 'DISABLED'}"
            
            save_state()
            await message.channel.send(response)
            
        # !history [commands/advances] - View history (admin)
        elif message.content.startswith("!history"):
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("You are not authorized to use this command.")
                return
            
            parts = message.content.split()
            history_type = "commands" if len(parts) < 2 else parts[1].lower()
            
            if history_type in ["cmd", "commands", "command"]:
                history = state.get("command_history", [])
                if not history:
                    await message.channel.send("No command history recorded.")
                    return
                
                # Show last 10 commands
                recent = history[-10:]
                response = "Recent Commands (Last 10)\n--------------------------------\n"
                for entry in recent:
                    dt = datetime.fromisoformat(entry["timestamp"])
                    response += f"• <t:{int(dt.timestamp())}:R> - <@{entry['user']}>: {entry['command']}\n"
                
            elif history_type in ["adv", "advance", "advances", "advancement"]:
                history = state.get("advancement_history", [])
                if not history:
                    await message.channel.send("No advancement history recorded.")
                    return
                
                # Show last 5 advancements
                recent = history[-5:]
                response = "Recent Advancements (Last 5)\n--------------------------------\n"
                for entry in recent:
                    dt = datetime.fromisoformat(entry["timestamp"])
                    old_date = datetime.fromisoformat(entry["old_date"])
                    new_date = datetime.fromisoformat(entry["new_date"])
                    response += (
                        f"• <t:{int(dt.timestamp())}:R>\n"
                        f"  {old_date.strftime('%B %Y')} -> {new_date.strftime('%B %Y')}\n"
                        f"  {entry['months_advanced']} months ({entry['days_missed']} days)\n"
                        f"  Type: {entry['type']}\n"
                    )
            else:
                response = "Invalid history type. Use !history commands or !history advances"
            
            await message.channel.send(response)
            
        # !ping - Check latency
        elif message.content == "!ping":
            latency = round(self.latency * 1000, 2)
            await message.channel.send(f"Pong! Latency: {latency}ms")
            
        # !help - Show help
        elif message.content == "!help":
            response = (
                "Government Date Bot - Help\n"
                "--------------------------------\n"
                "Date Commands:\n"
                "!date - Show current date information\n"
                "!status - Show bot status\n"
                "!ping - Check bot latency\n"
                "\n"
                "Admin Commands:\n"
                "!advance [months] - Manually advance date\n"
                "!force - Force auto-advance check\n"
                "!setdate <Month> <Year> - Set custom date\n"
                "!notifications [on/off] - Toggle notifications\n"
                "!timeformat [12hr/24hr] - Change time format\n"
                "!save - Manually save state\n"
                "!debug [on/off] - Toggle debug mode\n"
                "!history [commands/advances] - View history\n"
                "\n"
                "Settings:\n"
                "• Auto-advance: 4 months per real day at midnight EST\n"
                "• Max advance per run: 12 months\n"
                "• Date progresses in real-time through each month\n"
                "\n"
                f"Admin: <@{ADMIN_USER_ID}>"
            )
            await message.channel.send(response)
            
        # Unknown command
        elif message.content.startswith("!"):
            await message.channel.send(
                f"Unknown command. Type !help for available commands.\n"
                f"Did you mean !date or !status?"
            )

# ==================== MAIN EXECUTION ====================

if __name__ == "__main__":
    try:
        bot = GovernmentBot()
        
        # Clean shutdown handler
        import atexit
        def shutdown():
            print("\n" + "=" * 60)
            print("Shutting down bot...")
            stop_event.set()
            if auto_save_thread:
                auto_save_thread.join(timeout=5)
            save_state()
            print("Shutdown complete")
            print("=" * 60)
        
        atexit.register(shutdown)
        
        print("Starting bot...")
        bot.run(TOKEN)
        
    except discord.LoginFailure:
        print("ERROR: Invalid Discord token!")
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        shutdown()
