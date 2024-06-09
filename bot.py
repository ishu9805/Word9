from pyrogram import Client, filters
import re
import nltk
import random
import os
import requests
from threading import Thread
from flask import Flask

# Download the nltk words dataset
nltk.download("words")

# Retrieve API credentials from environment variables
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
TOKEN = os.environ.get("BOT_TOKEN")

# Initialize the Pyrogram client
app = Client("word9", api_id=API_ID, api_hash=API_HASH, bot_token=TOKEN)

# Initialize the Flask server
server = Flask(__name__)

@server.route("/")
def home():
    return "Bot is running"

# Define regex patterns
starting_letter_pattern = r"start with ([A-Z])"
min_length_pattern = r"include at least (\d+) letters"
trigger_pattern = r"Turn: .*" # Replace "Turn: .*" with your specific trigger pattern

# Set to keep track of used words
used_words = set()

def get_combined_word_list():
    # Fetch words from NLTK
    nltk_words = set(nltk.corpus.words.words())
    
    # Fetch words from the external URL
    url = "https://raw.githubusercontent.com/dwyl/english-words/master/words.txt"
    response = requests.get(url)
    external_words = set(response.text.splitlines())
    
    # Combine both sets of words
    combined_words = nltk_words | external_words
    return combined_words

@app.on_message(filters.command("ping"))
async def start(client, message):
    await message.edit("pong!")

@app.on_message(filters.command("resetwords"))
async def reset_used_words(client, message):
    global used_words
    used_words.clear()
    await message.edit("Used words list has been reset.")

@app.on_message(filters.text)
def handle_incoming_message(client, message):
    puzzle_text = message.text
    if re.search(trigger_pattern, puzzle_text):
        starting_letter_match = re.search(starting_letter_pattern, puzzle_text)
        min_length_match = re.search(min_length_pattern, puzzle_text)

        if starting_letter_match and min_length_match:
            starting_letter = starting_letter_match.group(1)
            min_length = int(min_length_match.group(1))

            combined_words = get_combined_word_list()
            
            # Filter valid words based on criteria
            valid_words = [word for word in combined_words if "-" not in word and word.startswith(starting_letter) and len(word) >= min_length and word not in used_words]

            if valid_words:
                # Randomly choose 5 words
                selected_words = random.sample(valid_words, min(2, len(valid_words)))
                
                # Add selected words to the set of used words
                used_words.update(selected_words)
                
                response_message = "Words:\n"
                for word in selected_words:
                    response_message += f"\n- {word}\nCopy-String: {word}\n"
                client.send_message(message.chat.id, response_message)
            else:
                client.send_message(message.chat.id, "No valid words found for the given criteria.")
        else:
            client.send_message(message.chat.id, "Criteria not found in the puzzle text.")
    return

def run():
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))

if __name__ == "__main__":
    t = Thread(target=run)
    t.start()
    app.run()
        
