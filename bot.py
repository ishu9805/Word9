from pyrogram import Client
from pymongo import MongoClient
import re

API_ID = 20904372
API_HASH = "3029454a7c4e0cc538818a3bf7a58336"
SESSION = "BQFbytYAh_udAGoo_IrHZUKKy48suxGDmi3srfe59QfzcFzv2F3wr2XJfXV8U6dQlHZs3AsSBWt-YzDbjqeXJs5Z16CVaWv-kbR-O377cUJJEVJeutmVqZu4SeqzbB3iwnY-GLWKiLRMp02GtweYiKIlql3JXICUl2w44QVHJrg2nKhHdW_tG-fFJA2XFX-myRS_J7ZipG3HjduLQ7EcOGzyz0ZIwZck8ciVVqHb3-yUipt7ZTIDd3JNJvmsULdPbx3ff923DWLObOLUKTcntTQ7vNIoxfzz73D45AXG49wV_ljuefIYIK1NR1ySm7_moZcNZJxcuZvjUCT8x2UcNbTVD9nKigAAAAG3yp56AA"

app = Client(
    "word9",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION
)

MONGO_URI = "mongodb+srv://naruto:hinatababy@cluster0.rqyiyzx.mongodb.net/"
client = MongoClient(MONGO_URI)
db = client['image_search_db']
images_collection = db['images']

TARGET_USER_ID = 6942284208

def extract_special_command_from_caption(caption):
    """Extract special command starting with / from the caption."""
    if not caption:
        return None
    words = caption.split()
    for word in words:
        if word.startswith('/'):
            return word.lower()  # Return the command in lowercase
    return None

@app.on_message()
async def check_caption(client, message):
    # Check if the message is a photo and from the target user with a command
    if message.photo and message.from_user.id == TARGET_USER_ID:
        command = extract_special_command_from_caption(message.caption)
        if command:
            # Fetch character name from the database
            character_data = images_collection.find_one({"file_unique_id": message.photo.file_unique_id})
            if character_data:
                # Clean character name (remove emojis and non-alphanumeric characters)
                character_name = re.sub(r'[^\w\s]', '', character_data['character_name'])
                
                # Prepare the response with the command and character name
                response_text = f"{command} {character_name}"
                await message.reply_text(response_text)  # Send the command and character name

if __name__ == "__main__":
    app.run()
