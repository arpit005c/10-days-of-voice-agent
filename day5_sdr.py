import os
import time
import json
import requests
import pygame
import speech_recognition as sr
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv  

# Load the keys from the .env file
load_dotenv()

# Get the keys securely
MURF_API_KEY = os.getenv("MURF_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- 🏢 CONFIG ---
VOICE_ID = "en-US-natalie" # Professional SDR voice
MURF_URL = "https://api.murf.ai/v1/speech/generate"
LEAD_FILE = "razorpay_leads.json"

client = OpenAI(api_key=OPENAI_API_KEY)
pygame.mixer.init()

# --- 📚 RAZORPAY KNOWLEDGE BASE ---
COMPANY_INFO = """
COMPANY: Razorpay (Indian Fintech)
PRODUCT: Payment Gateway & Banking Suite for Business.
PRICING: 
- Standard Plan: 2% platform fee per transaction. No setup fee. No annual maintenance fee.
- Enterprise Plan: Custom pricing for high volumes.
FEATURES:
- Accepts UPI, Credit/Debit Cards, Netbanking, Wallets.
- "RazorpayX" for business banking and payroll.
- International payments supported.
TARGET AUDIENCE: Startups, SMEs, and Enterprises in India.
"""

# --- 🛠 TOOL: LEAD CAPTURE ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "save_lead",
            "description": "Call this when the conversation ends to save the lead details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Prospect's name"},
                    "company": {"type": "string", "description": "Prospect's company name"},
                    "email": {"type": "string", "description": "Email address"},
                    "role": {"type": "string", "description": "Job title/Role"},
                    "use_case": {"type": "string", "description": "Why they need Razorpay (e.g., e-commerce, payroll)"},
                    "team_size": {"type": "string", "description": "Number of employees"},
                    "timeline": {"type": "string", "description": "When they want to start (Now, Soon, Later)"}
                },
                "required": ["name", "company"] 
            }
        }
    }
]

SYSTEM_PROMPT = f"""
You are "Neha", a Sales Development Rep (SDR) for Razorpay.
Your goal is to answer questions and qualify the lead.

KNOWLEDGE BASE:
{COMPANY_INFO}

INSTRUCTIONS:
1. Greet the user warmly and ask what brings them to Razorpay.
2. Answer their questions about pricing/features using the KNOWLEDGE BASE.
3. *Pivoting:* After answering, always ask a qualification question. 
   - Example: "The fee is 2%. By the way, how large is your team right now?"
4. Try to collect: Name, Company, Email, Role, Use Case, Team Size, Timeline.
5. Don't ask for everything at once. Keep it conversational.
6. When the user says "That's all" or "Goodbye", call the 'save_lead' tool with whatever info you gathered.
"""

def listen_to_user():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("\n👂 Listening... (Ask about Razorpay)")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=8)
            text = recognizer.recognize_google(audio)
            print(f"   👤 You: \"{text}\"")
            return text
        except:
            return None

def speak(text):
    print(f"   🤖 Neha (SDR): \"{text}\"")
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
            except:
                pass
    except Exception as e:
        print(f"   ❌ Error: {e}")

def save_lead_to_json(args):
    """Saves the lead to a JSON file"""
    print("\n📝 CAPTURING LEAD...")
    
    # Load existing or create new list
    leads = []
    if os.path.exists(LEAD_FILE):
        try:
            with open(LEAD_FILE, "r") as f:
                leads = json.load(f)
        except:
            leads = []
    
    # Add timestamp
    args["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    leads.append(args)
    
    with open(LEAD_FILE, "w") as f:
        json.dump(leads, f, indent=4)
        
    # Generate a verbal summary string
    summary = f"Thanks {args.get('name', 'there')}. I've noted that you are from {args.get('company', 'your company')} " \
              f"and you are looking at Razorpay for {args.get('use_case', 'payments')}. " \
              f"I have your timeline as {args.get('timeline', 'undecided')}. Our sales team will email you at {args.get('email', 'your email')} shortly."
    return summary

# --- 🏁 MAIN LOOP ---
if __name__ == "__main__":
    print("--- 💼 Razorpay SDR Agent ---")
    
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    intro = "Hi, this is Neha from Razorpay. Thanks for reaching out. What brings you to our website today?"
    speak(intro)
    history.append({"role": "assistant", "content": intro})

    while True:
        user_text = listen_to_user()
        
        if user_text:
            history.append({"role": "user", "content": user_text})
            print("   🧠 Thinking...")

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=history,
                tools=tools,
                tool_choice="auto" 
            )

            msg = response.choices[0].message

            # CASE 1: Tool Call (End of Call / Save Lead)
            if msg.tool_calls:
                args = json.loads(msg.tool_calls[0].function.arguments)
                
                # Save to JSON
                summary_text = save_lead_to_json(args)
                
                # Speak Summary
                speak(summary_text)
                
                print(f"\n✅ Lead Saved to {LEAD_FILE}")
                break # End session

            # CASE 2: Normal Conversation
            else:
                ai_reply = msg.content
                history.append({"role": "assistant", "content": ai_reply})
                speak(ai_reply)