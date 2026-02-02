#!/usr/bin/env python3
"""
Government Date Bot - PythonAnywhere Edition
24/7 Free Hosting - No Credit Card Required
"""

import discord
import os
import json
import sys
from datetime import datetime, time
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo

# ==================== CONFIGURATION ====================
# Get your username from PythonAnywhere (replace YOURUSERNAME below)
USERNAME = "loeasy68"  # CHANGE THIS to your PythonAnywhere username

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", 0))
ADMIN_USER_ID = 1367955172373823629
DATA_FILE = f"/home/{USERNAME}/gov_state.json"

# Timezone setup
EST = ZoneInfo("America/New_York")
MIDNIGHT_EST = time(0, 0, tzinfo=EST)

# Force print to show in PythonAnywhere console
print("=" * 60)
print("🤖 GOVERNMENT DATE BOT - STARTING")
print("=" * 60)
print(f"PythonAnywhere User: {USERNAME}")
print(f"Data file: {DATA_FILE}")

# ==================== STATE MANAGEMENT ====================
def load_state():
    """Load or create the state file"""
    try:
        with open(DATA_FILE, "r") as f:
            state = json.load(f)
        print(f"✅ Loaded state from {DATA_FILE}")
        return state
    except FileNotFoundError:
        now = datetime.now(EST)
        state = {
            "current_date": now.isoformat(),
            "last_run": now.date().isoformat()
        }
        save_state(state)
        print(f"✅ Created new state file")
        return state
    except Exception as e:
        print(f"❌ Error loading state: {e}")
        # Fallback to memory
        now = datetime.now(EST)
        return {
            "current_date": now.isoformat(),
            "last_run": now.date().isoformat()
        }

def save_state(state):
    """Save state to file"""
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(state, f, indent=2)
        print(f"💾 State saved to file")
    except Exception as e:
        print(f"❌ Error saving state: {e}")

# Load initial state
state = load_state()
current_date = datetime.fromisoformat(state["current_date"])
print(f"📅 Current in-game date: {current_date.strftime('%B %Y')}")
print(f"⏰ Timezone: EST (America/New_York)")

# ==================== DISCORD BOT SETUP ====================
print("\n🔧 Setting up Discord bot...")

# Configure intents
intents = discord.Intents.default()
intents.message_content = True  # Required for reading message content

class GovernmentBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.last_advance_check = datetime.now(EST)
        
    async def on_ready(self):
        """Called when bot successfully connects to Discord"""
        print("\n" + "=" * 60)
        print(f"✅ BOT IS ONLINE AND CONNECTED!")
        print(f"🤖 Name: {self.user}")
        print(f"🆔 ID: {self.user.id}")
        print(f"🏠 Host: PythonAnywhere (Free, 24/7)")
        print(f"📅 Current date: {current_date.strftime('%B %Y')}")
        print(f"🌐 Servers: {len(self.guilds)}")
        print("=" * 60)
        
        # Set custom status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="the calendar | !date"
            )
        )
        
        print("\n🎮 Available commands in Discord:")
        print("   !date     - Show current in-game date")
        print("   !advance  - Advance 4 months (admin only)")
        print("   !ping     - Test if bot is responsive")
        print("   !help     - Show all commands")
        print("   !status   - Show bot status")
        print("=" * 60)
        print("✅ Bot is ready! Commands will work in Discord.")
        
    async def on_message(self, message):
        """Handle all incoming messages"""
        # Ignore messages from bots (including ourselves)
        if message.author.bot:
            return
        
        # Log the message to PythonAnywhere console
        print(f"\n📨 [#{message.channel}] {message.author}: {message.content}")
        
        # ===== COMMAND HANDLING =====
        
        # !date - Show current date
        if message.content == "!date":
            current = datetime.fromisoformat(state["current_date"])
            response = f"🗓️ **Current in-game date:** {current.strftime('%B %Y')} (EST)"
            await message.channel.send(response)
            print(f"   📤 Sent: {current.strftime('%B %Y')}")
            
        # !ping - Test response
        elif message.content == "!ping":
            await message.channel.send("🏓 Pong from PythonAnywhere! (24/7 Free Hosting)")
            print("   📤 Sent: Pong!")
            
        # !advance - Manual advance (admin only)
        elif message.content == "!advance":
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("❌ You are not authorized to use this command.")
                print(f"   ⛔ Unauthorized attempt by: {message.author}")
                return
            
            current = datetime.fromisoformat(state["current_date"])
            new_date = current + relativedelta(months=4)
            state["current_date"] = new_date.isoformat()
            state["last_run"] = datetime.now(EST).date().isoformat()
            save_state(state)
            
            response = (
                f"⚙️ **Manual advance complete!**\n"
                f"🗓️ New in-game date: **{new_date.strftime('%B %Y')}** (EST)"
            )
            await message.channel.send(response)
            print(f"   📤 Advanced to: {new_date.strftime('%B %Y')}")
            
        # !help - Show help
        elif message.content == "!help":
            help_text = """
            **📖 Available Commands:**
            `!date` - Show current in-game date
            `!advance` - Manually advance by 4 months (Admin only)
            `!ping` - Check if bot is responsive
            `!status` - Show bot status information
            `!debug` - Show debug information
            `!help` - Show this message
            
            **Admin ID:** `1367955172373823629`
            **Host:** PythonAnywhere (Free, 24/7)
            """
            await message.channel.send(help_text)
            print("   📤 Sent help message")
            
        # !status - Show status
        elif message.content == "!status":
            current = datetime.fromisoformat(state["current_date"])
            status_text = f"""
            **🤖 Bot Status:**
            • Host: PythonAnywhere (Free Tier, 24/7)
            • Status: Online ✅
            • Uptime: Always Running
            • Current Date: {current.strftime('%B %Y')}
            • Timezone: EST (America/New_York)
            • Admin: <@{ADMIN_USER_ID}>
            """
            await message.channel.send(status_text)
            print("   📤 Sent status")
            
        # !debug - Debug information
        elif message.content == "!debug":
            current = datetime.fromisoformat(state["current_date"])
            debug_info = f"""
            **🐛 Debug Information:**
            • Bot User: {self.user}
            • Your ID: {message.author.id}
            • Your Name: {message.author}
            • Admin ID: {ADMIN_USER_ID}
            • Current Date: {current.strftime('%B %Y')}
            • State File: {DATA_FILE}
            • Channel: #{message.channel}
            • Host: PythonAnywhere Free Tier
            """
            await message.channel.send(debug_info)
            print("   📤 Sent debug info")
            
        # Unknown command
        elif message.content.startswith("!"):
            await message.channel.send(
                "❓ Unknown command. Type `!help` for a list of available commands."
            )
            print(f"   ❓ Unknown command")

# ==================== RUN BOT ====================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 CONNECTING TO DISCORD...")
    print("=" * 60)
    
    # Check for token
    if not TOKEN:
        print("❌ ERROR: DISCORD_TOKEN environment variable not set!")
        print("   Please set it in PythonAnywhere:")
        print("   1. Go to Web tab")
        print("   2. Click 'Add a new web app' (if not already)")
        print("   3. Scroll down to 'Code' section")
        print("   4. Click on the virtualenv path")
        print("   5. Add environment variable: DISCORD_TOKEN=your_token_here")
        print("   6. Also add: DISCORD_CHANNEL_ID=your_channel_id")
        sys.exit(1)
    
    print(f"✅ Discord Token: Present")
    print(f"✅ Channel ID: {CHANNEL_ID if CHANNEL_ID else 'Not set (no auto-advance)'}")
    print(f"✅ Admin ID: {ADMIN_USER_ID}")
    
    try:
        # Create bot instance and run
        bot = GovernmentBot()
        print("🤖 Starting Discord connection...")
        bot.run(TOKEN)
        
    except discord.LoginFailure:
        print("❌ ERROR: Invalid Discord token! Please check your DISCORD_TOKEN.")
    except discord.PrivilegedIntentsRequired:
        print("❌ ERROR: Message Content Intent not enabled!")
        print("   Go to: https://discord.com/developers/applications")
        print("   → Your App → Bot → Privileged Gateway Intents")
        print("   → Enable 'MESSAGE CONTENT INTENT'")
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("🛑 BOT HAS STOPPED")
    print("=" * 60)