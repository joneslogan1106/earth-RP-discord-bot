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
        return {
            "current_date": now.isoformat(), 
            "last_run": now.date().isoformat(),
            "notifications_enabled": True,
            "time_format": "12hr",
            "command_history": []
        }

def save_state(state):
    with open(DATA_FILE, "w") as f:
        json.dump(state, f, indent=2)

state = load_state()
current_date = datetime.fromisoformat(state["current_date"])
print(f"Current in-game date: {current_date.strftime('%B %Y')}")

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
    
    save_state(state)

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
        
        # Send notification if channel is available and notifications are enabled
        if channel and state.get("notifications_enabled", True):
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
        print(f"Current date: {datetime.fromisoformat(state['current_date']).strftime('%B %Y')}")
        print(f"Notifications: {'Enabled' if state.get('notifications_enabled', True) else 'Disabled'}")
        print(f"Time format: {state.get('time_format', '12hr')}")
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
            
        # Log the command
        log_command(message.author.id, message.content)
        print(f"[{message.author}] {message.content}")
        
        # ===== MAIN COMMANDS =====
        
        if message.content == "!date":
            base_date = datetime.fromisoformat(state["current_date"])
            now = datetime.now(EST)
            time_fmt = state.get("time_format", "12hr")
            
            # Calculate approximated current date
            approx_date = approximate_current_date(base_date, now)
            
            # Calculate days until next advancement
            next_midnight = datetime.combine(now.date() + timedelta(days=1), time(0, 0, tzinfo=EST))
            time_until = next_midnight - now
            hours_until = time_until.seconds // 3600
            minutes_until = (time_until.seconds % 3600) // 60
            
            # Format the response
            response = (
                f"**Current Date:**\n"
                f"Base Period: {base_date.strftime('%B %Y')}\n"
                f"Current Approximation: {approx_date.strftime('%B %d, %Y')}\n"
                f"Real Time: {format_time(now, time_fmt)} EST\n"
                f"Next Advancement: {hours_until}h {minutes_until}m\n"
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
                
            current = datetime.fromisoformat(state["current_date"])
            new_date = current + relativedelta(months=months_to_advance)
            state["current_date"] = new_date.isoformat()
            state["last_run"] = datetime.now(EST).date().isoformat()
            save_state(state)
            
            await message.channel.send(
                f"Manual advance complete.\n"
                f"Advanced by: **{months_to_advance}** month(s)\n"
                f"New base period: **{new_date.strftime('%B %Y')}**"
            )
            
        elif message.content == "!ping":
            # Calculate uptime approximation (GitHub Actions restarts every 30 min)
            now = datetime.now(EST)
            minute_of_hour = now.minute
            uptime_minutes = minute_of_hour % 30  # Rough estimate
            await message.channel.send(
                f"Online\n"
                f"Current uptime: ~{uptime_minutes} minutes\n"
                f"Next restart: in {30 - uptime_minutes} minutes"
            )
            
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
                f"Next Auto-Advance: {hours_until}h {minutes_until}m\n"
                f"Notifications: {'✅ Enabled' if state.get('notifications_enabled', True) else '❌ Disabled'}\n"
                f"Time Format: {state.get('time_format', '12hr')}\n"
                f"Commands Today: {len([c for c in state.get('command_history', []) if datetime.fromisoformat(c['timestamp']).date() == now_date])}"
            )
            await message.channel.send(status_msg)
            
        elif message.content == "!current":
            # Detailed current date information
            base_date = datetime.fromisoformat(state["current_date"])
            now = datetime.now(EST)
            time_fmt = state.get("time_format", "12hr")
            approx_date = approximate_current_date(base_date, now)
            
            # Calculate progress through the month (0-100%)
            day_progress = (now.hour * 3600 + now.minute * 60 + now.second) / 86400.0
            month_progress = day_progress * 100
            
            # Calculate exact day of month (1-30)
            day_of_month = int(day_progress * 30) + 1
            
            response = (
                f"**Date Information**\n"
                f"Base Period: {base_date.strftime('%B %Y')}\n"
                f"Current Date: {approx_date.strftime('%B %d, %Y')}\n"
                f"Day of Month: {day_of_month}/30\n"
                f"Progress: {month_progress:.1f}% complete\n"
                f"Real Time: {format_time(now, time_fmt)} EST\n"
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
                
        elif message.content == "!notifications":
            # Toggle notifications
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("Only administrators can change notification settings.")
                return
                
            current_setting = state.get("notifications_enabled", True)
            state["notifications_enabled"] = not current_setting
            save_state(state)
            
            status = "enabled" if state["notifications_enabled"] else "disabled"
            await message.channel.send(f"Auto-advance notifications have been **{status}**.")
            
        elif message.content == "!timeformat":
            # Toggle between 12hr and 24hr time format
            current_format = state.get("time_format", "12hr")
            new_format = "24hr" if current_format == "12hr" else "12hr"
            state["time_format"] = new_format
            save_state(state)
            
            await message.channel.send(f"Time format changed to **{new_format}**.")
            
        elif message.content == "!history":
            # Show recent command history (admin only)
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("Only administrators can view command history.")
                return
                
            history = state.get("command_history", [])
            if not history:
                await message.channel.send("No command history recorded.")
                return
                
            history_text = "**Recent Commands:**\n"
            for entry in history[-5:]:  # Show last 5 commands
                dt = datetime.fromisoformat(entry["timestamp"])
                history_text += f"• <t:{int(dt.timestamp())}:R> - <@{entry['user']}>: `{entry['command']}`\n"
                
            await message.channel.send(history_text)
            
        elif message.content == "!setdate":
            # Set custom date (admin only)
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("Only administrators can set custom dates.")
                return
                
            parts = message.content.split()
            if len(parts) < 3:
                await message.channel.send("Usage: `!setdate <month> <year>`\nExample: `!setdate January 2024`")
                return
                
            try:
                month_name = parts[1]
                year = int(parts[2])
                
                # Parse the month
                month_num = datetime.strptime(month_name, "%B").month
                new_date = datetime(year, month_num, 1, tzinfo=EST)
                
                state["current_date"] = new_date.isoformat()
                save_state(state)
                
                await message.channel.send(f"Date set to **{new_date.strftime('%B %Y')}**.")
            except ValueError:
                await message.channel.send("Invalid date format. Use: `!setdate <Month> <Year>`")
                
        elif message.content.startswith("!schedule"):
            # Show upcoming schedule
            current = datetime.fromisoformat(state["current_date"])
            now = datetime.now(EST)
            
            schedule_text = "**Upcoming Date Schedule:**\n"
            for i in range(1, 13, 4):  # Show next 3 advancements
                future_date = current + relativedelta(months=i)
                real_world_date = now + timedelta(days=i)  # 1 real day = 4 months
                schedule_text += f"• **{future_date.strftime('%B %Y')}** - ~{real_world_date.strftime('%b %d')}\n"
                
            schedule_text += f"\n*4 months advance per real-world day*"
            await message.channel.send(schedule_text)
            
        elif message.content == "!info":
            # Quick info command
            current = datetime.fromisoformat(state["current_date"])
            await message.channel.send(
                f"**Government Date Bot**\n"
                f"Current: {current.strftime('%B %Y')}\n"
                f"Rate: 4 months per real day\n"
                f"Auto-advance: Midnight EST\n"
                f"Use `!help` for all commands"
            )
            
        elif message.content == "!help":
            help_text = (
                "**Main Commands:**\n"
                "`!date` - Show current approximated date\n"
                "`!current` - Detailed date information\n"
                "`!info` - Quick bot information\n"
                "`!status` - Bot status and settings\n"
                "`!schedule` - Show upcoming date schedule\n"
                "`!ping` - Check bot responsiveness\n"
                "`!auto-check` - Force auto-advance check\n"
                "\n"
                "**Administrator Commands:**\n"
                "`!advance [months]` - Advance by months (default: 4)\n"
                "`!setdate <Month> <Year>` - Set custom date\n"
                "`!notifications` - Toggle auto-advance notifications\n"
                "`!timeformat` - Toggle 12hr/24hr time format\n"
                "`!history` - View recent command history\n"
                "\n"
                "**Settings:**\n"
                "• Time progresses through each month in real-time\n"
                "• Auto-advances 4 months at midnight EST daily\n"
                "• Notifications can be toggled with `!notifications`\n"
                "\n"
                f"Admin: <@{ADMIN_USER_ID}>"
            )
            await message.channel.send(help_text)
            
        elif message.content.startswith("!"):
            # Unknown command - show suggestion
            await message.channel.send(
                f"Unknown command. Type `!help` for available commands.\n"
                f"Did you mean `!date` or `!info`?"
            )

# Run bot
if __name__ == "__main__":
    try:
        bot = GovernmentBot(intents=intents)
        bot.run(TOKEN)
    except Exception as e:
        print(f"Error: {e}")
