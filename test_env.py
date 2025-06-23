import os
from dotenv import load_dotenv

load_dotenv()  # обов’язково

print("TOKEN:", os.getenv("TOKEN"))
print("CHAT_ID:", os.getenv("CHAT_ID"))
print("MINFIN_TOKEN:", os.getenv("MINFIN_TOKEN"))