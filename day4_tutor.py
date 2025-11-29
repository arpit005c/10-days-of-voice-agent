import os
import time
import json
import requests
import pygame
import speech_recognition as sr
from openai import OpenAI
from dotenv import load_dotenv  

# Load the keys from the .env file
load_dotenv()

# Get the keys securely
MURF_API_KEY = os.getenv("MURF_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- 🎭 VOICE CONFIG  ---
VOICES = {
    "learn": "en-US-ken",      # Ken (The Teacher)
    "quiz": "en-US-amara",     # Amara (The Examiner - Replaces Alicia)
    "teach_back": "en-US-maverick" # Maverick (The Coach - Distinct Male Voice)
}

MURF_URL = "https://api.murf.ai/v1/speech/generate"

# Initialize Clients
client = OpenAI(api_key=OPENAI_API_KEY)
pygame.mixer.init()

# --- 📂 LOAD CONTENT ---
def load_content():
    try:
        with open("day4_tutor_content.json", "r") as f:
            return json.load(f)
    except:
        print("❌ Error: day4_tutor_content.json not found!")
        return []

COURSE_CONTENT = load_content()
CONTENT_TEXT = json.dumps(COURSE_CONTENT) 

# --- 🧠 DYNAMIC PROMPTS ---
def get_system_prompt(mode, topic):
    """Returns the instructions based on mode AND current topic"""
    
    base_info = f"You are an Active Recall Tutor. The user is currently studying: {topic}. Here is the course content: {CONTENT_TEXT}"

    if mode == "learn":
        return base_info + """
        MODE: LEARN (Voice: Ken)
        GOAL: Explain concepts clearly.
        INSTRUCTIONS: 
        1. If the topic is 'General', ask them to choose Variables or Loops.
        2. If a topic is selected, explain it simply using the 'summary' in the content.
        3. Ask if they are ready for a quiz.
        """
    elif mode == "quiz":
        return base_info + f"""
        MODE: QUIZ (Voice: Amara)
        GOAL: Test the user's knowledge on {topic}.
        INSTRUCTIONS: 
        1. Ask a specific question about {topic} based on the content.
        2. Wait for their answer.
        3. Tell them if they are right or wrong.
        """
    elif mode == "teach_back":
        return base_info + f"""
        MODE: TEACH-BACK (Voice: Maverick)
        GOAL: Rate the user's explanation of {topic}.
        INSTRUCTIONS: 
        1. Ask the user to explain {topic} back to you.
        2. Grade their explanation on a scale of 1-10.
        3. Give constructive feedback.
        """
    else:
        return base_info + "You are a helpful receptionist. Ask the user to choose a mode: Learn, Quiz, or Teach-Back."

# --- 👂 LISTEN ---
def listen_to_user():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("\n👂 Listening...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=8)
            text = recognizer.recognize_google(audio)
            print(f"   👤 You: \"{text}\"")
            return text
        except:
            return None

# --- 🗣 SPEAK ---
def speak(text, mode):
    voice_id = VOICES.get(mode, "en-US-ken") 
    
    print(f"   🤖 AI ({mode.upper()} - {voice_id}): \"{text}\"")
    
    headers = {"api-key": MURF_API_KEY, "Content-Type": "application/json"}
    payload = {
        "voiceId": voice_id,
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
            print(f"   ❌ Murf Error: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"   ❌ Network Error: {e}")

# --- 🏁 MAIN LOOP ---
if __name__ == "__main__":
    print("--- 🎓 Active Recall Coach ---")
    print("Modes: [1] Learn (Ken) | [2] Quiz (Amara) | [3] Teach-Back (Maverick)")
    
    current_mode = "greeting"
    current_topic = "General Programming" # <--- NEW: Tracks the topic
    
    # Initialize prompt with topic
    history = [{"role": "system", "content": get_system_prompt(current_mode, current_topic)}]
    
    intro = "Welcome to the Active Recall Coach. Would you like to start with Learn, Quiz, or Teach-Back mode?"
    speak(intro, "learn")
    history.append({"role": "assistant", "content": intro})

    while True:
        user_text = listen_to_user()
        
        if user_text:
            user_lower = user_text.lower()

            # --- 🕵 DETECT TOPIC ---
            if "loop" in user_lower:
                current_topic = "Loops"
                print(f"   📝 Topic Detected: {current_topic}")
            elif "variable" in user_lower:
                current_topic = "Variables"
                print(f"   📝 Topic Detected: {current_topic}")

            # --- 🔀 MODE SWITCHING ---
            new_mode = None
            if "learn" in user_lower: new_mode = "learn"
            elif "quiz" in user_lower: new_mode = "quiz"
            elif "teach" in user_lower or "back" in user_lower: new_mode = "teach_back"
            
            if new_mode and new_mode != current_mode:
                print(f"\n🔄 SWITCHING MODE: {current_mode} -> {new_mode} (Topic: {current_topic})\n")
                current_mode = new_mode
                
                # Update System Prompt with the CURRENT TOPIC
                history = [{"role": "system", "content": get_system_prompt(current_mode, current_topic)}]
                
                # Add a silent system instruction to force the AI to acknowledge the switch immediately
                history.append({"role": "system", "content": f"User switched to {current_mode} mode. Topic is {current_topic}. Start immediately."})
            
            # --- 🧠 GET AI RESPONSE ---
            history.append({"role": "user", "content": user_text})
            
            print("   🧠 Thinking...")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=history
            )
            
            ai_reply = response.choices[0].message.content
            history.append({"role": "assistant", "content": ai_reply})
            
            speak(ai_reply,current_mode)