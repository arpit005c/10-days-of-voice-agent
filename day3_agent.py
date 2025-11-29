import os
import time
import json
import requests
import pygame
import speech_recognition as sr
from datetime import datetime
from openai import OpenAI
import os
from dotenv import load_dotenv  

# Load the keys from the .env file
load_dotenv()

# Get the keys securely
MURF_API_KEY = os.getenv("MURF_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- 🧘 CONFIG ---
# "en-US-natalie" or "en-US-julie" are good, soft voices for wellness
VOICE_ID = "en-US-natalie" 
MURF_URL = "https://api.murf.ai/v1/speech/generate"
LOG_FILE = "wellness_log.json"

# Initialize Clients
client = OpenAI(api_key=OPENAI_API_KEY)
pygame.mixer.init()

# --- 🛠 TOOL DEFINITION (Saving Data) ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "log_daily_checkin",
            "description": "Saves the user's mood and goals to the wellness log.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mood": {"type": "string", "description": "User's current mood (e.g. Energetic, Anxious)"},
                    "energy_level": {"type": "string", "description": "Low, Medium, or High"},
                    "goals": {
                        "type": "array", 
                        "items": {"type": "string"},
                        "description": "List of 1-3 simple goals for the day"
                    },
                    "summary": {"type": "string", "description": "A brief, supportive summary of the conversation."}
                },
                "required": ["mood", "energy_level", "goals", "summary"]
            }
        }
    }
]

def load_history():
    """Reads the JSON log to get past context"""
    if not os.path.exists(LOG_FILE):
        return None
    try:
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
            if data:
                return data[-1] # Return the most recent entry
    except:
        return None
    return None

def generate_system_prompt(last_entry):
    """Creates a prompt based on whether we have spoken before"""
    base_prompt = """
    You are a supportive, grounded Health & Wellness Companion.
    Your goal is to check in on the user's mood and help them set 1-3 simple goals.
    
    GUIDELINES:
    1. Be empathetic but NOT a doctor. Do not diagnose.
    2. Keep advice small and actionable (e.g., "Take a 5-min walk", "Drink water").
    3. Ask: "How are you feeling?" and "What are your goals for today?"
    4. Once you have the Mood, Energy, and Goals, SUMMARIZE them back to the user.
    5. After the user confirms the summary, call the 'log_daily_checkin' function.
    """
    
    if last_entry:
        context = f"""
        CONTEXT FROM LAST SESSION ({last_entry['date']}):
        - User was feeling: {last_entry['mood']}
        - Energy was: {last_entry['energy_level']}
        - Past Goals: {', '.join(last_entry['goals'])}
        
        INSTRUCTION: Start by briefly mentioning their last check-in (e.g., "Last time you were feeling... how is today?")
        """
        return base_prompt + context
    else:
        return base_prompt + "\nINSTRUCTION: This is your first meeting. Introduce yourself warmly."

def listen_to_user():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("\n👂 Listening... (Speak now)")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=8)
            text = recognizer.recognize_google(audio)
            print(f"   👤 You: \"{text}\"")
            return text
        except:
            return None

def speak(text):
    print(f"   🤖 Companion: \"{text}\"")
    headers = {"api-key": MURF_API_KEY, "Content-Type": "application/json"}
    payload = {
        "voiceId": VOICE_ID,
        "text": text,
        "modelVersion": "GEN2", 
        "format": "MP3"
    }
    try:
        res = requests.post(MURF_URL, json=payload, headers=headers)
        if res.status_code == 200:
            with open("response.mp3", "wb") as f:
                f.write(requests.get(res.json()["audioFile"]).content)
            try:
                pygame.mixer.music.load("response.mp3")
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                pygame.mixer.music.unload()
            except Exception as e:
                print(f"   ❌ Pygame Error: {e}")
        else:
            print(f"   ❌ Murf Error: {res.status_code}")
    except Exception as e:
        print(f"   ❌ Network Error: {e}")

def save_entry(args):
    """Saves the entry to JSON"""
    print("\n💾 SAVING ENTRY TO JOURNAL...")
    
    # Add timestamp
    entry = args
    entry["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Read existing data
    data = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                data = json.load(f)
        except:
            data = []
            
    # Append new entry
    data.append(entry)
    
    # Write back
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=4)
        
    print(f"✅ Saved: Mood={entry['mood']}, Goals={entry['goals']}")
    return "I've logged that for you. Have a wonderful day!"

# --- 🏁 MAIN LOOP ---
if __name__ == "__main__":
    print("--- 🧘 Day 3: Wellness Companion ---")
    
    # 1. Load Context
    last_entry = load_history()
    system_prompt = generate_system_prompt(last_entry)
    history = [{"role": "system", "content": system_prompt}]
    
    # 2. Dynamic Intro
    if last_entry:
        intro = f"Welcome back! Last time we spoke, you were feeling {last_entry['mood']}. How are you doing today?"
    else:
        intro = "Hello! I am your wellness companion. How are you feeling today?"
        
    speak(intro)
    history.append({"role": "assistant", "content": intro})

    while True:
        user_text = listen_to_user()
        
        if user_text:
            if "bye" in user_text.lower():
                speak("Take care.")
                break

            history.append({"role": "user", "content": user_text})
            print("   🧠 Thinking...")

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=history,
                tools=tools,
                tool_choice="auto" 
            )

            msg = response.choices[0].message

            if msg.tool_calls:
                args = json.loads(msg.tool_calls[0].function.arguments)
                final_response = save_entry(args)
                speak(final_response)
                break 
            else:
                ai_reply = msg.content
                history.append({"role": "assistant", "content": ai_reply})
                speak(ai_reply)