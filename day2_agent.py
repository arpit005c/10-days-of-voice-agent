import os
import time
import json
import requests
import pygame
import speech_recognition as sr
from openai import OpenAI
import os
from dotenv import load_dotenv  

# Load the keys from the .env file
load_dotenv()

# Get the keys securely
MURF_API_KEY = os.getenv("MURF_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- ☕ CONFIG ---
VOICE_ID = "en-US-natalie" 
MURF_URL = "https://api.murf.ai/v1/speech/generate"

# Initialize Clients
client = OpenAI(api_key=OPENAI_API_KEY)
pygame.mixer.init()

# --- 🛠 ORDER STATE DEFINITION (The "Form" the AI must fill) ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "save_order",
            "description": "Call this when the user has provided ALL order details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drinkType": {"type": "string", "description": "Type of coffee (e.g. Latte, Cappuccino)"},
                    "size": {"type": "string", "description": "Size of drink (Small, Medium, Large)"},
                    "milk": {"type": "string", "description": "Type of milk (Whole, Oat, Almond, None)"},
                    "extras": {
                        "type": "array", 
                        "items": {"type": "string"},
                        "description": "List of extras (e.g. Sugar, Vanilla Syrup, Extra hot)"
                    },
                    "name": {"type": "string", "description": "Customer's name for the order"}
                },
                "required": ["drinkType", "size", "milk", "name"]
            }
        }
    }
]

SYSTEM_PROMPT = """
You are a friendly barista at 'Cosmic Coffee'. 
Your goal is to complete an order by collecting: Drink Type, Size, Milk preference, Extras, and Customer Name.

Rules:
1. Ask one clarifying question at a time.
2. Be brief and friendly.
3. Once you have ALL details, call the 'save_order' function immediately.
4. Don't assume details (e.g., don't assume milk type unless told).
"""

def listen_to_user():
    """Listens to the microphone"""
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
    """Speaks using Murf AI"""
    print(f"   🤖 Barista: \"{text}\"")
    
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

def save_order_to_json(args):
    """Saves the completed order to a file"""
    print("\n📝 SAVING ORDER TO FILE...")
    filename = "order.json"
    with open(filename, "w") as f:
        json.dump(args, f, indent=4)
    print(f"✅ Order saved to {filename}")
    print(args)
    return "Order confirmed! I've saved that for you. Thanks for visiting Cosmic Coffee!"

# --- 🏁 MAIN LOOP ---
if __name__ == "__main__":
    print("--- ☕ Cosmic Coffee Barista Agent ---")
    
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    intro = "Hi! Welcome to Cosmic Coffee. What can I get started for you?"
    speak(intro)
    history.append({"role": "assistant", "content": intro})

    while True:
        user_text = listen_to_user()
        
        if user_text:
            if "exit" in user_text.lower():
                speak("Goodbye!")
                break

            history.append({"role": "user", "content": user_text})
            print("   🧠 Thinking...")

            # Call OpenAI with Tools enabled
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=history,
                tools=tools,
                tool_choice="auto" 
            )

            msg = response.choices[0].message

            # CASE 1: AI wants to call a function (Order Complete)
            if msg.tool_calls:
                # Get arguments from the tool call
                args = json.loads(msg.tool_calls[0].function.arguments)
                
                # Run our save function
                final_response = save_order_to_json(args)
                
                # Speak the confirmation
                speak(final_response)
                break # End the program after successful order

            # CASE 2: AI just wants to talk (Asking clarifying questions)
            else:
                ai_reply = msg.content
                history.append({"role": "assistant", "content": ai_reply})
                speak(ai_reply)