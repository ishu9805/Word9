import nltk
import asyncio
import re
import random
import os
import requests
from threading import Thread
from flask import Flask
from pymongo import MongoClient
from pyrogram import Client, filters

# Download the nltk words dataset
nltk.download("words")

# Retrieve API credentials from environment variables
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")

# Initialize the Pyrogram client
app = Client("word9", api_id=API_ID, api_hash=API_HASH, bot_token=TOKEN)

# Initialize the Flask server
server = Flask(__name__)

# MongoDB client
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["word_database"]
word_collection = db["words"]

@server.route("/")
def home():
    return "Bot is running"

# Define regex patterns
starting_letter_pattern = r"start with ([A-Z])"
min_length_pattern = r"include at least (\d+) letters"
trigger_pattern = r"Turn: .*"  # Replace "Turn: .*" with your specific trigger pattern
accepted_pattern = r"(\w+) is accepted"

# Set to keep track of used words
used_words = set()
stop_check = False  # Global variable to control the execution of the word check

# Group ID for the target group
TARGET_GROUP_ID = -1002048925723

def fetch_words():
    # Fetch words from NLTK
    nltk_words = set(nltk.corpus.words.words())
    
    # Fetch words from the external URLs
    urls = [
        "https://raw.githubusercontent.com/dwyl/english-words/master/words.txt",
        "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english.txt"
    ]
    external_words = set()
    for url in urls:
        response = requests.get(url)
        external_words.update(response.text.splitlines())
    
    # Fetch words from words_alpha.txt in the repository
    alpha_url = "https://raw.githubusercontent.com/ishu9805/Word9/main/words_alpha.txt"
    response = requests.get(alpha_url)
    words_alpha = set(response.text.splitlines())
    
    # Exclude words containing special characters
    pattern = re.compile(r"^[a-zA-Z]+$")
    words_alpha_filtered = {word for word in words_alpha if pattern.match(word)}
    
    # Combine all sets of words
    combined_words = nltk_words | external_words | words_alpha_filtered
    return combined_words

def get_combined_word_list():
    combined_words = fetch_words()
    # Fetch words from MongoDB
    mongodb_words = {word["word"] for word in word_collection.find()}
    combined_words.update(mongodb_words)
    return combined_words

@app.on_message(filters.command("ping"))
async def ping(client, message):
    await message.reply_text("pong!")

@app.on_message(filters.command("countwords"))
async def count_words_command(client, message):
    word_count = word_collection.count_documents({})
    await message.reply_text(f"The MongoDB database contains {word_count} words.")

@app.on_message(filters.command("resetwords"))
async def reset_used_words(client, message):
    global used_words
    used_words.clear()
    await message.reply_text("Used words list has been reset.")

@app.on_message(filters.command("generatewordlist"))
async def generate_wordlist(client, message):
    combined_words = get_combined_word_list()
    with open("wordlist.txt", "w") as file:
        for word in combined_words:
            file.write(word + "\n")
    await client.send_document(message.chat.id, "wordlist.txt")

@app.on_message(filters.command("clearwords"))
async def clear_words(client, message):
    word_collection.delete_many({})
    await message.reply_text("All words have been removed from the database.")

@app.on_message(filters.command("exist"))
async def exist_word(client, message):
    word = message.text.split(" ", 1)[1].strip().lower()
    word_exists = word_collection.find_one({"word": word})
    if word_exists:
        await message.reply_text(f"The word '{word}' exists in the database.")
    else:
        await message.reply_text(f"The word '{word}' does not exist in the database.")

@app.on_message(filters.command("checkwords ?(.*)"))
async def check_words(client, message):
    global stop_check
    stop_check = False

    # Get the last processed word from the command argument
    last_word = message.command[1].strip().lower()

    # Set chat IDs
    wordchainbot_chat_id = 'on9wordchainbot'  # Replace with actual chat ID or username

    await client.send_message(TARGET_GROUP_ID, "Starting word existence check...")

    # Get all English words from NLTK corpus and convert to lowercase
    english_words = sorted(word.lower() for word in fetch_words())

    # Find the starting index based on the last word provided
    start_index = 0
    if last_word:
        try:
            start_index = english_words.index(last_word) + 1
        except ValueError:
            await client.send_message(TARGET_GROUP_ID, f"Word '{last_word}' not found in the word list. Starting from the beginning.")
            start_index = 0

    async def event_handler(event_response):
        if event_response.chat.id == (await client.get_peer_id(wordchainbot_chat_id)):
            if "is in my dictionary" in event_response.text:
                word = event_response.text.split()[0].lower()
                if not word_collection.find_one({"word": word}):
                    word_collection.update_one({"word": word}, {"$set": {"word": word}}, upsert=True)
                    await client.send_message(TARGET_GROUP_ID, f"The word '{word}' has been added to the database.")
                else:
                    await client.send_message(TARGET_GROUP_ID, f"The word '{word}' is already in the database.")

    # Add the event handler for new messages
    client.add_handler(event_handler, filters.new_message)

    try:
        word_count = 0
        for index in range(start_index, len(english_words)):
            if stop_check:
                await client.send_message(TARGET_GROUP_ID, "Word existence check stopped.")
                break

            word = english_words[index]
            # Construct the command
            command = f"/exist {word}"
            
            # Send command to the on9wordchainbot
            await client.send_message(wordchainbot_chat_id, command)
            
            # Add a delay to avoid rate limits
            await asyncio.sleep(2)  # Increased delay between each message

            word_count += 1
            if word_count >= 30:
                await asyncio.sleep(60)  # Wait for 1 minute after every 30 words
                word_count = 0
    
    except Exception as e:
        await client.send_message(TARGET_GROUP_ID, f"An error occurred: {e}")
    
    finally:
        # Remove the event handler after processing
        client.remove_handler(event_handler, filters.new_message)

    if not stop_check:
        await client.send_message(TARGET_GROUP_ID, "Word existence check completed.")

@app.on_message(filters.command("stopwords"))
async def stop_words(client, message):
    global stop_check
    stop_check = True
    await client.send_message(TARGET_GROUP_ID, "Stopping the word existence check...")

@app.on_message(filters.text)
async def handle_incoming_message(client, message):
    puzzle_text = message.text
    
    # Check if the message matches the accepted pattern
    accepted_match = re.search(accepted_pattern, puzzle_text)
    if accepted_match:
        accepted_word = accepted_match.group(1).lower()
        word_exists = word_collection.find_one({"word": accepted_word})
        if word_exists:
            await message.reply_text("👍👍👍")
        else:
            word_collection.update_one({"word": accepted_word}, {"$set": {"word": accepted_word}}, upsert=True)
            await message.reply_text(f"The word '{accepted_word}' has been added to the database.")
        return
    
    # Proceed with normal word generation if the message matches the trigger pattern
    if re.search(trigger_pattern, puzzle_text):
        starting_letter_match = re.search(starting_letter_pattern, puzzle_text)
        min_length_match = re.search(min_length_pattern, puzzle_text)

        if starting_letter_match and min_length_match:
            starting_letter = starting_letter_match.group(1).lower()
            min_length = int(min_length_match.group(1))

            combined_words = get_combined_word_list()
            
            # Filter valid words based on criteria
            valid_words = [word for word in combined_words if word.startswith(starting_letter) and len(word) >= min_length and word not in used_words]

            if valid_words:
                # Randomly choose 1 word
                selected_word = random.choice(valid_words)
                
                # Add selected word to the set of used words
                used_words.add(selected_word)
                
                response_message = f"Word:\n\n- {selected_word}\nCopy-String: {selected_word}\n"
                # Check if the word already exists in MongoDB
                word_exists = word_collection.find_one({"word": selected_word})
                if word_exists:
                    response_message += f"The word '{selected_word}' is already in the database.\n"
                else:
                    # Add the selected word to MongoDB
                    word_collection.update_one({"word": selected_word}, {"$set": {"word": selected_word}}, upsert=True)
                    response_message += f"The word '{selected_word}' has been added to the database.\n"
                await client.send_message(message.chat.id, response_message)
            else:
                await client.send_message(message.chat.id, "No valid words found for the given criteria.")
        else:
            await client.send_message(message.chat.id, "Criteria not found in the puzzle text.")
    return

def run():
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))

if __name__ == "__main__":
    t = Thread(target=run)
    t.start()
    app.run()
