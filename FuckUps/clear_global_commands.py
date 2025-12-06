import requests
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

BOT_TOKEN = TOKEN  # Replace securely or load from env
APPLICATION_ID = "1446151775932383324"

url = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/commands"

headers = {
    "Authorization": f"Bot {BOT_TOKEN}"
}

# Empty list = wipe all global commands
response = requests.put(url, headers=headers, json=[])

print("Status:", response.status_code)
print("Response:", response.text)
