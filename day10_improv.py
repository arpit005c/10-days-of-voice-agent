import os
import time
import json
import random
import requests
import pygame
import speech_recognition as sr
from openai import OpenAI
from dotenv import load_dotenv

# --- 🔒 SECURITY ---
load_dotenv()
MURF_API_KEY = os.getenv("MURF_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not MURF_API_KEY or not OPENAI_API_KEY:
    print("❌ Error: Keys not found. Check your .env file.")
    exit()

# --- 🎭 CONFIG ---
VOICE_ID = "en-US-terrell" 
MURF_URL = "https://api.murf.ai/v1/speech/generate"
SCENARIO_FILE = "improv_scenarios.json"

client = OpenAI(api_key=OPENAI_API_KEY)
pygame.mixer.init()

# --- 🎮 GAME STATE ---
GAME_STATE = {"round": 0, "max_rounds": 3}

def load_scenarios():
    if not os.path.exists(SCENARIO_FILE):
        return [{"role": "Mime", "setting": "Box", "conflict": "Stuck."}]
    with open(SCENARIO_FILE, "r") as f:
        return json.load(f)

SCENARIOS = load_scenarios()

# --- 🛠 HELPER FUNCTIONS ---

def speak(text):
    """Host Voice Output"""
    print(f"   🎤 Host: \"{text}\"")
    headers = {"api-key": MURF_API_KEY, "Content-Type": "application/json"}
    payload = {"voiceId": VOICE_ID, "text": text, "modelVersion": "GEN2", "format": "MP3"}

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
                print(f"   ❌ Audio Error: {e}")
        else:
            print(f"   ❌ MURF ERROR: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"   ❌ Connection Error: {e}")

def listen_to_user():
    recognizer = sr.Recognizer()
    
    # 👇 KEY FIX: Allow 3 seconds of silence before cutting off
    recognizer.pause_threshold = 3.0 
    
    # Lower energy threshold for quiet acting
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True

    with sr.Microphone() as source:
        print("\n   🎭 [Action!] (Calibrating mic...)")
        recognizer.adjust_for_ambient_noise(source, duration=1.0)
        
        print("   🔴 REC (Start acting! I am listening...)")
        
        try:
            # phrase_time_limit=30 means you have 30 seconds to act
            audio = recognizer.listen(source, timeout=None, phrase_time_limit=30)
            
            print("   (Processing performance...)")
            text = recognizer.recognize_google(audio)
            print(f"   👤 You: \"{text}\"")
            return text
        except sr.WaitTimeoutError:
            print("   (Timeout: No speech detected)")
            return None
        except Exception:
            return None

def get_host_feedback(scenario, user_performance):
    print("   🧠 Host is judging you...")
    
    system_prompt = "You are the host of 'Improv Battle'. Give a score out of 10 and a funny comment."
    user_prompt = f"SCENARIO: {scenario['role']} in {scenario['setting']}. {scenario['conflict']}\nPLAYER ACTING: \"{user_performance}\""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return "Score: 5/10. Good effort."

# --- 🏁 MAIN GAME LOOP ---
if __name__ == "__main__":
    print("--- 🎭 IMPROV BATTLE ---")
    
    intro = "Welcome to Improv Battle! I'm your host. I give you a scene, you act it out. Let's go!"
    speak(intro)
    
    random.shuffle(SCENARIOS) 
    
    while GAME_STATE["round"] < GAME_STATE["max_rounds"]:
        if GAME_STATE["round"] >= len(SCENARIOS): break

        current_round = GAME_STATE["round"] + 1
        scenario = SCENARIOS[GAME_STATE["round"]]
        
        print(f"\n--- 🔔 ROUND {current_round} ---")
        
        setup = f"Round {current_round}. You are a {scenario['role']} in a {scenario['setting']}. {scenario['conflict']}... GO!"
        speak(setup)
        
        user_performance = listen_to_user()
        
        if not user_performance:
            speak("I didn't hear anything! Speak up! Let's try the next one.")
            GAME_STATE["round"] += 1
            continue
            
        feedback = get_host_feedback(scenario, user_performance)
        speak(feedback)
        
        GAME_STATE["round"] += 1
        time.sleep(1)

    speak("That's the game! Thanks for playing!")