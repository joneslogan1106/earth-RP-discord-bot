import discord
import os
import json
import asyncio
from datetime import datetime, time
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", 0))
ADMIN_USER_ID = 1367955172373823629
DATA_FILE = "gov_state.json"
EST = ZoneInfo("America/New_York")

print("=" * 60)
print("🤖 Government Bot - GitHub Actions Edition")
print("=" * 60)
print(f"Token present: {'✅' if TOKEN else '❌'}")
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
print(f"📅 Current in-game date: {current_date.strftime('%B %Y')}")

# Discord bot
intents = discord.Intents.default()
intents.message_content = True

class GitHubBot(discord.Client):
    async def on_ready(self):
        print("=" * 60)
        print(f"✅ Connected as {self.user}")
        print(f"🏠 Host: GitHub Actions (Free 24/7)")
        print(f"📅 Current date: {current_date.strftime('%B %Y')}")
        print("=" * 60)
        
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="GitHub Actions | !date"
        ))
        
    async def on_message(self, message):
        if message.author.bot:
            return
            
        print(f"[MSG] {message.author}: {message.content}")
        
        if message.content == "!date":
            current = datetime.fromisoformat(state["current_date"])
            await message.channel.send(f"📅 **Current in-game date:** {current.strftime('%B %Y')} (EST)")
            
        elif message.content == "!advance":
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("❌ Not authorized")
                return
                
            current = datetime.fromisoformat(state["current_date"])
            new_date = current + relativedelta(months=4)
            state["current_date"] = new_date.isoformat()
            state["last_run"] = datetime.now(EST).date().isoformat()
            save_state(state)
            
            await message.channel.send(f"⚙️ **Advanced to:** {new_date.strftime('%B %Y')} (EST)")
            
        elif message.content == "!ping":
            await message.channel.send("🏓 Pong from GitHub Actions! (24/7 Free Hosting)")
            
        elif message.content == "!status":
            await message.channel.send(
                "✅ Bot running on GitHub Actions\n"
                "⏰ Free 24/7 hosting\n"
                "🔄 Restarts every 25 minutes\n"
                "🏠 No credit card required"
            )
            
        elif message.content == "!help":
            await message.channel.send(
                "**Commands:**\n"
                "`!date` - Show current date\n"
                "`!advance` - Advance 4 months (admin)\n"
                "`!ping` - Test bot\n"
                "`!status` - Bot info\n"
                "`!help` - This message"
            )

# Run bot
if __name__ == "__main__":
    try:
        bot = GitHubBot(intents=intents)
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Error: {e}")
