from pyrogram import Client, filters
import re
import nltk
import os
import requests
from threading import Thread
from flask import Flask
from pymongo import MongoClient
import random

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
dictionary_response_pattern = r"(\w+) is in my dictionary"

# Set to keep track of used words
used_words = set()

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
    alpha_url = "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt"
    response = requests.get(alpha_url)
    words_alpha = set(response.text.splitlines())
    
    # Exclude words containing special characters
    pattern = re.compile(r"^[a-zA-Z]+$")
    words_alpha_filtered = {word for word in words_alpha if pattern.match(word)}
    
    # Combine all sets of words
    combined_words = nltk_words | external_words | words_alpha_filtered
    return combined_words

def get_combined_word_list():
    # Fetch words from MongoDB
    mongodb_words = {word["word"] for word in word_collection.find()}
    
    # Fetch words from NLTK and external sources
    nltk_and_external_words = fetch_words()
    
    # Combine all words
    combined_words = mongodb_words | nltk_and_external_words
    return combined_words

@app.on_message(filters.command("ping", prefixes=["/", "!", "."]))
async def ping(client, message):
    await message.reply_text("pong!")

@app.on_message(filters.command("countwords", prefixes=["/", "!", "."]))
async def count_words_command(client, message):
    word_count = word_collection.count_documents({})
    await message.reply_text(f"The MongoDB database contains {word_count} words.")

@app.on_message(filters.command("resetwords", prefixes=["/", "!", "."]))
async def reset_used_words(client, message):
    global used_words
    used_words.clear()
    await message.reply_text("Used words list has been reset.")

@app.on_message(filters.command("generatewordlist", prefixes=["/", "!", "."]))
async def generate_wordlist(client, message):
    combined_words = get_combined_word_list()
    with open("wordlist.txt", "w") as file:
        for word in combined_words:
            file.write(word + "\n")
    await client.send_document(message.chat.id, "wordlist.txt")

@app.on_message(filters.command("clearwords", prefixes=["/", "!", "."]))
async def clear_words(client, message):
    word_collection.delete_many({})
    await message.reply_text("All words have been removed from the database.")

@app.on_message(filters.command("existwords", prefixes=["/", "!", "."]))
async def exist_words(client, message):
    nltk_words = sorted(nltk.corpus.words.words())
    
    batch_size = 1 # Number of words per message
    for i in range(0, len(nltk_words), batch_size):
        batch = nltk_words[i:i + batch_size]
        response_message = "\n".join(f"/exist {word}" for word in batch)
        await message.reply_text(response_message)

@app.on_message(filters.text)
async def handle_incoming_message(client, message):
    puzzle_text = message.text

    # Check if the message matches the accepted pattern
    accepted_match = re.search(accepted_pattern, puzzle_text)
    if accepted_match:
        accepted_word = accepted_match.group(1).lower()
        word_exists = word_collection.find_one({"word": accepted_word})
        if word_exists:
            await message.reply_text(f"👍👍👍")
        else:
            word_collection.update_one({"word": accepted_word}, {"$set": {"word": accepted_word}}, upsert=True)
            await message.reply_text(f"The word '{accepted_word}' has been added to the database.")
        return

    # Check for the dictionary response pattern
    dictionary_response_match = re.search(dictionary_response_pattern, puzzle_text)
    if dictionary_response_match:
        word_to_check = dictionary_response_match.group(1).lower()
        word_exists = word_collection.find_one({"word": word_to_check})
        if word_exists:
            await message.reply_text(f"'{word_to_check}' is already in the database.")
        else:
            word_collection.update_one({"word": word_to_check}, {"$set": {"word": word_to_check}}, upsert=True)
            await message.reply_text(f"The word '{word_to_check}' has been added to the database.")
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
                selected_words = random.sample(valid_words, min(1, len(valid_words)))
                
                # Add selected words to the set of used words
                used_words.update(selected_words)
                
                response_message = "Words:\n"
                for word in selected_words:
                    response_message += f"\n- {word}\nCopy-String: {word}\n"
                    # Check if the word already exists in MongoDB
                    word_exists = word_collection.find_one({"word": word})
                    if word_exists:
                        response_message += f"The word '{word}' is already in the database.\n"
                    else:
                        # Add each selected word to MongoDB
                        word_collection.update_one({"word": word}, {"$set": {"word": word}}, upsert=True)
                        response_message += f"The word '{word}' has been added to the database.\n"
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
