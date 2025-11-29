import os
import time
import json
import sqlite3
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

# --- 🏦 CONFIG ---
VOICE_ID = "en-US-terrell" # Serious, professional male voice
MURF_URL = "https://api.murf.ai/v1/speech/generate"
DB_FILE = "bank_fraud.db"

client = OpenAI(api_key=OPENAI_API_KEY)
pygame.mixer.init()

# --- 🛠 TOOLS (Database Actions) ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "verify_and_update_case",
            "description": "Updates the fraud case status in the bank database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "The customer's username"},
                    "status": {"type": "string", "description": "New status: 'safe', 'fraudulent', or 'failed_verification'"},
                    "reason": {"type": "string", "description": "Brief note on why this status was chosen"}
                },
                "required": ["username", "status", "reason"]
            }
        }
    }
]

# --- 🗄 DATABASE HELPERS ---
def get_case_by_username(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM fraud_cases WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            "username": row[0],
            "security_code": row[1],
            "card_last4": row[2],
            "merchant": row[3],
            "amount": row[4],
            "location": row[5],
            "timestamp": row[6],
            "status": row[7]
        }
    return None

def update_case_status(username, status):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE fraud_cases SET case_status=? WHERE username=?", (status, username))
    conn.commit()
    conn.close()
    print(f"\n💾 DATABASE UPDATED: User '{username}' marked as '{status.upper()}'")
    return "Case updated successfully."

# --- 🗣 VOICE & LISTEN ---
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

def speak(text):
    print(f"   🤖 Agent: \"{text}\"")
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
            except: pass
    except: pass

# --- 🏁 MAIN LOOP ---
if __name__ == "__main__":
    print("--- 🏦 Bank Fraud Alert Agent ---")
    
    # 1. Simulate Incoming Call (Ask for Username to load profile)
    username = input("Enter Username to simulate call (e.g. john_doe): ").strip()
    case_data = get_case_by_username(username)
    
    if not case_data:
        print("❌ User not found in database!")
        exit()

    # 2. Build System Prompt with Case Data
    SYSTEM_PROMPT = f"""
    You are a Fraud Prevention Officer at 'Murf Bank'.
    You are calling customer '{case_data['username']}'.
    
    CASE DETAILS:
    - Card Ending: {case_data['card_last4']}
    - Merchant: {case_data['merchant']}
    - Amount: {case_data['amount']}
    - Location: {case_data['location']}
    - Correct Security Code: {case_data['security_code']}
    
    FLOW:
    1. Introduce yourself and say you are calling about suspicious activity.
    2. VERIFICATION: Ask the user for their 4-digit Security Code.
       - If they get it WRONG (it is NOT {case_data['security_code']}), end call and mark as 'failed_verification'.
       - If RIGHT, proceed.
    3. Read the transaction details (Merchant, Amount, Location).
    4. Ask "Did you authorize this transaction?"
       - If YES: Mark as 'safe'.
       - If NO: Mark as 'fraudulent' and say you blocked the card.
    5. Call the 'verify_and_update_case' tool to save the result.
    """

    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # 3. Start Call
    intro = f"Hello, this is the Fraud Department at Murf Bank. Am I speaking with {username}?"
    speak(intro)
    history.append({"role": "assistant", "content": intro})

    while True:
        user_text = listen_to_user()
        
        if user_text:
            if "bye" in user_text.lower():
                speak("Goodbye.")
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
                
                # Execute Update
                result_msg = update_case_status(args["username"], args["status"])
                
                # Confirm to user
                final_reply = "Thank you. I have updated your account status. Goodbye."
                speak(final_reply)
                break 
            else:
                ai_reply = msg.content
                history.append({"role": "assistant", "content": ai_reply})
                speak(ai_reply)