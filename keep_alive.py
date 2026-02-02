#!/usr/bin/env python3
"""
Keep Discord Bot Alive on PythonAnywhere Free Tier
Uses scheduled tasks to restart bot periodically
"""

import discord
import os
import json
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ==================== CONFIG ====================
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", 0))
ADMIN_USER_ID = 1367955172373823629
DATA_FILE = "gov_state.json"

print("=" * 60)
print("🤖 Government Bot - PythonAnywhere Free Edition")
print("=" * 60)

# ==================== STATE ====================
def load_state():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        now = datetime.now()
        return {
            "current_date": now.isoformat(),
            "last_run": now.date().isoformat()
        }

def save_state(state):
    with open(DATA_FILE, "w") as f:
        json.dump(state, f, indent=2)

state = load_state()

# ==================== DISCORD BOT ====================
intents = discord.Intents.default()
intents.message_content = True

class KeepAliveBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.start_time = datetime.now()
        
    async def on_ready(self):
        print(f"✅ Bot connected as {self.user}")
        print(f"⏰ Started at: {self.start_time}")
        print(f"📅 Current date: {datetime.fromisoformat(state['current_date']).strftime('%B %Y')}")
        
        # Keep running for 3 hours (PythonAnywhere free task limit)
        # Then the scheduled task will restart us
        print("⏳ Will run for 3 hours, then scheduled task will restart...")
        
    async def on_message(self, message):
        if message.author.bot:
            return
            
        print(f"[{message.channel}] {message.author}: {message.content}")
        
        if message.content == "!date":
            current = datetime.fromisoformat(state["current_date"])
            await message.channel.send(f"📅 **Current date:** {current.strftime('%B %Y')}")
            
        elif message.content == "!advance":
            if message.author.id != ADMIN_USER_ID:
                await message.channel.send("❌ Not authorized")
                return
                
            current = datetime.fromisoformat(state["current_date"])
            new_date = current + relativedelta(months=4)
            state["current_date"] = new_date.isoformat()
            save_state(state)
            
            await message.channel.send(f"⚙️ **Advanced to:** {new_date.strftime('%B %Y')}")
            
        elif message.content == "!ping":
            await message.channel.send(f"🏓 Pong! Running for {(datetime.now() - self.start_time).seconds//60} minutes")
            
        elif message.content == "!status":
            uptime = datetime.now() - self.start_time
            await message.channel.send(f"✅ Bot is alive!\n⏰ Uptime: {uptime.seconds//60} minutes\n🏠 Host: PythonAnywhere Free")

# ==================== RUN WITH TIMEOUT ====================
if __name__ == "__main__":
    bot = KeepAliveBot()
    
    # Run for 3 hours (10800 seconds) then exit
    # Scheduled task will restart us
    try:
        import asyncio
        
        async def run_with_timeout():
            # Start the bot
            task = asyncio.create_task(bot.start(TOKEN))
            
            # Wait for 3 hours, then stop
            await asyncio.sleep(10800)  # 3 hours
            
            # Stop the bot
            await bot.close()
            print("⏰ 3 hours elapsed, stopping for scheduled restart...")
            
        asyncio.run(run_with_timeout())
        
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Error: {e}")