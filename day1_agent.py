import os
import time
import requests
import pygame  # <--- NEW: Using Pygame for smooth audio
from openai import OpenAI
import os
from dotenv import load_dotenv  

# Load the keys from the .env file
load_dotenv()

# Get the keys securely
MURF_API_KEY = os.getenv("MURF_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- ⚙ CONFIG ---
VOICE_ID = "en-US-natalie" 
MURF_URL = "https://api.murf.ai/v1/speech/generate"

client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize the audio mixer once at the start
pygame.mixer.init()

def get_brain_response(text):
    """Get a smart answer from ChatGPT"""
    print("\n🧠 AI is thinking...")
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[
                {"role": "system", "content": "You are a helpful voice assistant. Keep answers strictly under 1 sentence."},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error with OpenAI: {e}")
        return "I couldn't think of an answer."

def speak_with_murf(text):
    """Generate audio with Murf and play it internally"""
    print(f"🗣 AI Saying: {text}")

    headers = {
        "api-key": MURF_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "voiceId": VOICE_ID,
        "text": text,
        "modelVersion": "GEN2", 
        "format": "MP3",
        "channel": "MONO"
    }

    try:
        # 1. Send request to Murf
        response = requests.post(MURF_URL, json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            audio_url = data.get("audioFile")
            
            if audio_url:
                # 2. Download audio to a file
                audio_data = requests.get(audio_url).content
                with open("response.mp3", "wb") as f:
                    f.write(audio_data)
                
                # 3. Play using Pygame (No popups, no OneDrive errors)
                try:
                    pygame.mixer.music.load("response.mp3")
                    pygame.mixer.music.play()
                    
                    # Wait for audio to finish
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                        
                    # Unload the file so we can overwrite it next time
                    pygame.mixer.music.unload()
                    
                except Exception as e:
                    print(f"Pygame Error: {e}")

            else:
                print("❌ Error: Murf didn't send an audio link.")
        else:
            print(f"❌ Murf API Error: {response.status_code}")
            print(f"   Message: {response.text}")

    except Exception as e:
        print(f"❌ Playback Error: {e}")

# --- 🏁 MAIN LOOP ---
if __name__ == "__main__":
    print("--- 🤖 Voice Agent Started (Pygame Mode) ---")
    print("Type 'exit' to stop.")
    
    while True:
        user_input = input("\n👉 You: ")
        
        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
            
        ai_reply = get_brain_response(user_input)
        print(f"🤖 AI Text: {ai_reply}")
        
        speak_with_murf(ai_reply)