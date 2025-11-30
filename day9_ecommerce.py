import os
import time
import json
import requests
import pygame
import speech_recognition as sr
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# --- 🔒 SECURITY ---
load_dotenv()
MURF_API_KEY = os.getenv("MURF_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not MURF_API_KEY or not OPENAI_API_KEY:
    print("❌ Error: Keys not found. Check your .env file.")
    exit()

# --- 🛒 CONFIG ---
VOICE_ID = "en-US-natalie" 
MURF_URL = "https://api.murf.ai/v1/speech/generate"
CATALOG_FILE = "acp_catalog.json"
ORDERS_FILE = "acp_orders.json"

client = OpenAI(api_key=OPENAI_API_KEY)
pygame.mixer.init()

# --- 🏪 GLOBAL MERCHANT FUNCTIONS  ---

def load_catalog():
    """Loads the catalog directly from the JSON file"""
    if not os.path.exists(CATALOG_FILE):
        print(f"❌ Error: {CATALOG_FILE} not found! Please create it first.")
        return []
    
    try:
        print(f"📂 Loading products from {CATALOG_FILE}...")
        with open(CATALOG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error reading catalog: {e}")
        return []

# Load catalog globally ONCE at startup
CATALOG = load_catalog()

def search_products(query=None, category=None, max_price=None):
    """Simulates GET /products with filters"""
    results = CATALOG
    
    if category:
        results = [p for p in results if p.get("category", "").lower() == category.lower()]
    
    if max_price:
        results = [p for p in results if p.get("price", 0) <= max_price]
        
    if query:
        q = query.lower()
        results = [p for p in results if q in p.get("name", "").lower() or q in p.get("description", "").lower()]
        
    return results

def create_order(product_id, quantity=1):
    """Simulates POST /orders"""
    product = next((p for p in CATALOG if p["id"] == product_id), None)
    if not product:
        return {"error": "Product not found"}

    total_price = product.get("price", 0) * quantity
    
    order = {
        "order_id": f"ord_{int(time.time())}",
        "created_at": datetime.now().isoformat(),
        "status": "CONFIRMED",
        "currency": product.get("currency", "USD"),
        "total_amount": total_price,
        "line_items": [
            {
                "product_id": product["id"],
                "name": product["name"],
                "quantity": quantity,
                "unit_price": product.get("price", 0)
            }
        ]
    }

    all_orders = []
    if os.path.exists(ORDERS_FILE):
        try:
            with open(ORDERS_FILE, "r") as f:
                content = f.read()
                if content:
                    all_orders = json.loads(content)
        except: 
            all_orders = []
    
    all_orders.append(order)
    
    with open(ORDERS_FILE, "w") as f:
        json.dump(all_orders, f, indent=4)
        
    return order

def get_last_order():
    if not os.path.exists(ORDERS_FILE):
        return "No recent orders found."
    try:
        with open(ORDERS_FILE, "r") as f:
            orders = json.load(f)
            if orders:
                return orders[-1]
    except:
        pass
    return "No recent orders found."

# ==========================================
# 🤖 THE AGENT LAYER
# ==========================================

tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search the product catalog. Returns a list of products.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keywords like 'hoodie' or 'mug'"},
                    "category": {"type": "string", "description": "Category filter"},
                    "max_price": {"type": "integer", "description": "Maximum price filter"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Place an order for a specific product ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "The ID of the product to buy (e.g., prod_001)"},
                    "quantity": {"type": "integer", "description": "Number of items"}
                },
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_last_order",
            "description": "Get details of the last placed order.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

SYSTEM_PROMPT = """
You are an AI Shopping Assistant connected to a Merchant API.
1. When user asks for products, call 'search_products'. Summarize results nicely (Name + Price).
2. When user wants to buy, YOU MUST find the 'product_id' from the search results first.
3. Call 'create_order' with the ID.
4. IMPORTANT: After placing an order, YOU MUST read out the 'order_id' and Total Price clearly to the user.
5. If user asks "What did I just buy?", call 'get_last_order'.
"""

# --- AUDIO HELPERS ---
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

# --- MAIN LOOP ---
if __name__ == "__main__":
    print("--- 🛍 Agentic Commerce Assistant ---")
    
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    intro = "Welcome to the Concept Store. How can I help you shop today?"
    speak(intro)
    history.append({"role": "assistant", "content": intro})

    while True:
        user_text = listen_to_user()
        if user_text:
            if "bye" in user_text.lower():
                speak("Happy shopping!")
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
                    print(f"   ⚙ API CALL: {name}({args})")
                    
                    result = "Error"
                    
                    if name == "search_products":
                        result = search_products(args.get("query"), args.get("category"), args.get("max_price"))
                    elif name == "create_order":
                        result = create_order(args["product_id"], args.get("quantity", 1))
                        print(f"   ✅ Order Created: {result.get('order_id')}")
                    elif name == "get_last_order":
                        result = get_last_order()
                    
                    history.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": str(result)
                    })
                
                final = client.chat.completions.create(model="gpt-4o-mini", messages=history)
                speak(final.choices[0].message.content)
                history.append({"role": "assistant", "content": final.choices[0].message.content})
            else:
                speak(msg.content)
                history.append({"role": "assistant", "content":msg.content})