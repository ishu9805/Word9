from pyrogram import Client, filters
import re
import nltk
import random
import os
from threading import Thread
from flask import Flask
import pyperclip

# nltk
nltk.download("words")

API_ID = os.environ.get("API_ID") 
API_HASH = os.environ.get("API_HASH") 
TOKEN = os.environ.get("BOT_TOKEN")

# Bot
app = Client("word9", api_id=API_ID, api_hash=API_HASH, bot_token=TOKEN)

server = Flask(__name__)

@server.route("/")
def home():
    return "Bot is running"

starting_letter_pattern = r"start with ([A-Z])"
min_length_pattern = r"include at least (\d+) letters"
trigger_pattern = r"Turn: .*" # Replace "ᖇᗩᕼᑌᒪ" with your own trigger pattern (Your telegram profile name)

@app.on_message(filters.me & filters.command("ping", prefixes="!"))
async def start(client, message):
    await message.edit("pong!")

@app.on_message(filters.text)
def handle_incoming_message(client, message):
    puzzle_text = message.text
    if re.search(trigger_pattern, puzzle_text):
        starting_letter_match = re.search(starting_letter_pattern, puzzle_text)
        min_length_match = re.search(min_length_pattern, puzzle_text)

        if starting_letter_match and min_length_match:
            starting_letter = starting_letter_match.group(1)
            min_length = int(min_length_match.group(1))

            english_words = set(nltk.corpus.words.words())

            valid_words = [word for word in english_words if word.startswith(starting_letter) and len(word) >= min_length]

            if valid_words:
                # Randomly choose 5 words
                selected_words = random.sample(valid_words, min(5, len(valid_words)))
                for idx, word in enumerate(selected_words):
                    response_message = f"Word {idx + 1}: {word}"
                    client.send_message(message.chat.id, response_message)
            else:
                print("No valid words found for the given criteria.")
        else:
            print("Criteria not found in the puzzle text.")
    return
    
@app.on_message(filters.text & ~filters.me)
def handle_button_click(client, message):
    if message.text.startswith("Word"):
        word_index = re.findall(r"Word (\d+)", message.text)
        if word_index:
            word_index = int(word_index[0]) - 1
            words = message.text.split(": ")[1].split(", ")
            if len(words) > word_index:
                selected_word = words[word_index]
                pyperclip.copy(selected_word)
                client.send_message(message.chat.id, f"Word '{selected_word}' copied to clipboard!")

def run():
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))

if __name__ == "__main__":
    t = Thread(target=run)
    t.start()
    app.run()
