import os
import time
import json
import random
import requests
import pygame
import speech_recognition as sr
from openai import OpenAI
from dotenv import load_dotenv  

# --- 🔒 SECURITY SETUP ---
load_dotenv()  # Load keys from .env file

MURF_API_KEY = os.getenv("MURF_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not MURF_API_KEY or not OPENAI_API_KEY:
    print("❌ Error: Keys not found! Make sure they are in your .env file.")
    exit()

# --- 🎲 CONFIG ---
VOICE_ID = "en-US-natalie" 
MURF_URL = "https://api.murf.ai/v1/speech/generate"
GAME_STATE_FILE = "game_state.json"

client = OpenAI(api_key=OPENAI_API_KEY)
pygame.mixer.init()

# --- 🌍 WORLD STATE MANAGEMENT ---
DEFAULT_STATE = {
    "health": 100,
    "inventory": ["Flashlight", "Datapad"],
    "location": "Neon Alley",
    "turn_count": 0,
    "is_game_over": False
}

def load_game_state():
    if not os.path.exists(GAME_STATE_FILE):
        return DEFAULT_STATE
    try:
        with open(GAME_STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return DEFAULT_STATE

def save_game_state(state):
    with open(GAME_STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

# Load state on startup
GAME_STATE = load_game_state()

# --- 🎲 GAME MECHANICS (TOOLS) ---

def roll_dice(action_description):
    """Rolls a d20 to determine success/failure"""
    roll = random.randint(1, 20)
    result = "FAIL" if roll < 10 else "SUCCESS"
    
    outcome = f"Dice Roll: {roll}/20 ({result})"
    print(f"   🎲 {outcome} for '{action_description}'")
    
    return f"ACTION: {action_description}. RESULT: {outcome}."

def update_inventory(item, action):
    """Adds or removes items"""
    if action == "add":
        GAME_STATE["inventory"].append(item)
        msg = f"Added {item} to inventory."
    elif action == "remove":
        if item in GAME_STATE["inventory"]:
            GAME_STATE["inventory"].remove(item)
            msg = f"Removed {item} from inventory."
        else:
            msg = f"Could not find {item}."
    
    save_game_state(GAME_STATE)
    print(f"   🎒 {msg}")
    return msg

def update_health(amount):
    """Changes HP"""
    GAME_STATE["health"] += amount
    if GAME_STATE["health"] > 100: GAME_STATE["health"] = 100
    if GAME_STATE["health"] <= 0:
        GAME_STATE["health"] = 0
        GAME_STATE["is_game_over"] = True
    
    save_game_state(GAME_STATE)
    msg = f"Health changed by {amount}. Current HP: {GAME_STATE['health']}"
    print(f"   ❤ {msg}")
    return msg

def check_status():
    """Returns current player stats"""
    status = f"LOCATION: {GAME_STATE['location']} | HP: {GAME_STATE['health']} | INVENTORY: {', '.join(GAME_STATE['inventory'])}"
    return status

# --- 🧠 OPENAI TOOLS ---
tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "roll_dice",
            "description": "Call this when player does something risky (fighting, jumping, hacking).",
            "parameters": {
                "type": "object", 
                "properties": {"action_description": {"type": "string"}}, 
                "required": ["action_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_inventory",
            "description": "Add or remove items from player inventory.",
            "parameters": {
                "type": "object", 
                "properties": {"item": {"type": "string"}, "action": {"type": "string", "enum": ["add", "remove"]}}, 
                "required": ["item", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_health",
            "description": "Change player health (negative for damage, positive for healing).",
            "parameters": {
                "type": "object", 
                "properties": {"amount": {"type": "integer"}}, 
                "required": ["amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_status",
            "description": "Get current health, location, and inventory.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }
]

SYSTEM_PROMPT = """
You are the Game Master (GM) for a Cyberpunk RPG.
SETTING: Neo-Tokyo, Year 2099. Rain-slicked streets, neon lights, corrupt corps.

RULES:
1. Describe the scene vividly but briefly (2-3 sentences).
2. Ask "What do you do?" at the end of every turn.
3. If the player tries something risky, CALL THE 'roll_dice' TOOL.
   - If the result is FAIL -> Describe a bad outcome (and maybe reduce health).
   - If SUCCESS -> Describe a cool victory.
4. Track items using 'update_inventory'.
5. If Health reaches 0, narrate a dramatic death and say "GAME OVER".

CURRENT STATE:
You must check the player's status at the start of every turn to see what they have.
"""

# --- 🗣 AUDIO & LISTEN ---
def speak(text):
    print(f"   🤖 GM: \"{text}\"")
    headers = {"api-key": MURF_API_KEY, "Content-Type": "application/json"}
    payload = {"voiceId": VOICE_ID, "text": text, "modelVersion": "GEN2", "format": "MP3"}
    
    try:
        res = requests.post(MURF_URL, json=payload, headers=headers)
        
        if res.status_code == 200:

            # Get the URL properly
            data = res.json()
            audio_url = data.get("audioFile")
            
            if audio_url:
                with open("response.mp3", "wb") as f:
                    f.write(requests.get(audio_url).content)
                
                try:
                    pygame.mixer.music.load("response.mp3")
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                    pygame.mixer.music.unload()
                except Exception as e:
                    print(f"   ❌ Audio Player Error: {e}")
            else:
                print("   ❌ Error: No audio URL in response!")
        else:
            # THIS WILL TELL US THE PROBLEM
            print(f"   ❌ MURF ERROR: {res.status_code}")
            print(f"   ❌ DETAILS: {res.text}")

    except Exception as e:
        print(f"   ❌ Network/Connection Error: {e}")

def listen_to_user():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("\n👂 Listening... (What do you do?)")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=8)
            text = recognizer.recognize_google(audio)
            print(f"   👤 You: \"{text}\"")
            return text
        except:
            return None

# --- 🏁 MAIN LOOP ---
if __name__ == "__main__":
    print("--- 🎲 Cyberpunk Game Master ---")
    
    current_status = check_status()
    history = [{"role": "system", "content": SYSTEM_PROMPT + f"\nPLAYER STATUS: {current_status}"}]
    
    if GAME_STATE["turn_count"] == 0:
        intro = "You wake up in a rainy alleyway in Neo-Tokyo. Your head hurts. You check your pockets and find a Flashlight and a Datapad. A Cyber-cop is walking towards you. What do you do?"
    else:
        intro = f"Welcome back to Neo-Tokyo. {current_status}. What do you want to do next?"

    speak(intro)
    history.append({"role": "assistant", "content": intro})

    while not GAME_STATE["is_game_over"]:
        user_text = listen_to_user()
        
        if user_text:
            if "exit" in user_text.lower() or "save" in user_text.lower():
                GAME_STATE["turn_count"] += 1
                save_game_state(GAME_STATE)
                speak("Game saved. See you next time, runner.")
                break

            history.append({"role": "user", "content": user_text})
            print("   🧠 Thinking...")

            response = client.chat.completions.create(
                model="gpt-4o-mini", messages=history,
                tools=tools_schema, tool_choice="auto" 
            )

            msg = response.choices[0].message

            if msg.tool_calls:
                history.append(msg)
                
                for call in msg.tool_calls:
                    name = call.function.name
                    args = json.loads(call.function.arguments)
                    
                    result = "Error"
                    if name == "roll_dice":
                        result = roll_dice(args["action_description"])
                    elif name == "update_inventory":
                        result = update_inventory(args["item"], args["action"])
                    elif name == "update_health":
                        result = update_health(args["amount"])
                    elif name == "check_status":
                        result = check_status()
                    
                    history.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": str(result)
                    })
                
                final_res = client.chat.completions.create(model="gpt-4o-mini", messages=history)
                ai_reply = final_res.choices[0].message.content
                speak(ai_reply)
                history.append({"role": "assistant", "content": ai_reply})
            else:
                speak(msg.content)
                history.append({"role": "assistant", "content":msg.content})