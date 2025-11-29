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

# --- 🛒 CONFIG ---
VOICE_ID = "en-US-natalie" 
MURF_URL = "https://api.murf.ai/v1/speech/generate"
CATALOG_FILE = "grocery_catalog.json"
ORDER_FILE = "placed_order.json"

client = OpenAI(api_key=OPENAI_API_KEY)
pygame.mixer.init()

# --- 🍎 SETUP CATALOG ---
DEFAULT_CATALOG = [
    {"name": "Milk", "category": "Dairy", "price": 2.50},
    {"name": "Eggs", "category": "Dairy", "price": 3.00},
    {"name": "Bread", "category": "Bakery", "price": 2.00},
    {"name": "Peanut Butter", "category": "Pantry", "price": 4.50},
    {"name": "Jelly", "category": "Pantry", "price": 3.00},
    {"name": "Pasta", "category": "Pantry", "price": 1.50},
    {"name": "Tomato Sauce", "category": "Pantry", "price": 2.50},
    {"name": "Cheese", "category": "Dairy", "price": 5.00},
    {"name": "Apple", "category": "Produce", "price": 0.80}
]

RECIPES = {
    "sandwich": ["Bread", "Peanut Butter", "Jelly"],
    "pasta": ["Pasta", "Tomato Sauce", "Cheese"],
    "omelet": ["Eggs", "Cheese", "Milk"]
}

def load_catalog():
    if not os.path.exists(CATALOG_FILE):
        with open(CATALOG_FILE, "w") as f:
            json.dump(DEFAULT_CATALOG, f, indent=4)
        return DEFAULT_CATALOG
    with open(CATALOG_FILE, "r") as f:
        return json.load(f)

CATALOG = load_catalog()

# --- 🛒 CART FUNCTIONS ---
CART = {}

def get_item_details(name):
    for item in CATALOG:
        if item["name"].lower() == name.lower():
            return item
    return None

def add_to_cart(item_name: str, quantity: int):
    # Smart Recipe Logic
    recipe_hit = None
    for r_key in RECIPES:
        if r_key in item_name.lower():
            recipe_hit = r_key
            break
            
    if recipe_hit:
        ingredients = RECIPES[recipe_hit]
        added_list = []
        for ing in ingredients:
            details = get_item_details(ing)
            if details:
                if ing in CART:
                    CART[ing]['qty'] += quantity
                else:
                    CART[ing] = {'qty': quantity, 'price': details['price']}
                added_list.append(ing)
        return f"I've added the ingredients for {recipe_hit} ({', '.join(added_list)}) to your cart."

    # Normal Item Logic
    details = get_item_details(item_name)
    if not details:
        return f"Sorry, I don't have '{item_name}' in the catalog."
    
    real_name = details['name']
    if real_name in CART:
        CART[real_name]['qty'] += quantity
    else:
        CART[real_name] = {'qty': quantity, 'price': details['price']}
        
    return f"Added {quantity} {real_name}(s) to your cart."

# 👇 UPDATED: Supports quantity removal 👇
def remove_from_cart(item_name: str, quantity: int = None):
    found_key = None
    for key in CART:
        if key.lower() == item_name.lower():
            found_key = key
            break
            
    if found_key:
        # If no quantity specified, delete entire item
        if quantity is None:
            del CART[found_key]
            return f"Removed all {found_key} from cart."
        
        # Subtract quantity
        CART[found_key]['qty'] -= quantity
        
        # If 0 or less, delete it
        if CART[found_key]['qty'] <= 0:
            del CART[found_key]
            return f"Removed {found_key} from cart."
            
        remaining = CART[found_key]['qty']
        return f"Removed {quantity} {found_key}. You have {remaining} left."
        
    return "That item isn't in your cart."

def view_cart():
    if not CART:
        return "Your cart is empty."
    summary = "Here is your cart:\n"
    total = 0.0
    for name, data in CART.items():
        cost = data['qty'] * data['price']
        total += cost
        summary += f"- {data['qty']} x {name}: ${cost:.2f}\n"
    summary += f"Total: ${total:.2f}"
    return summary

def place_order():
    if not CART:
        return "Your cart is empty!"
    order_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cart_contents": CART,
        "total_bill": sum(d['qty'] * d['price'] for d in CART.values())
    }
    with open(ORDER_FILE, "w") as f:
        json.dump(order_data, f, indent=4)
    CART.clear()
    return "Order placed! I've saved the receipt to your file."

# --- 🧠 OPENAI TOOLS ---
tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": "Add item or recipe to cart.",
            "parameters": {
                "type": "object", 
                "properties": {"item_name": {"type": "string"}, "quantity": {"type": "integer"}}, 
                "required": ["item_name", "quantity"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_from_cart",
            "description": "Remove item from cart. Specify quantity to remove partial amount.",
            "parameters": {
                "type": "object", 
                "properties": {
                    "item_name": {"type": "string"},
                    "quantity": {"type": "integer", "description": "Optional: amount to remove"} # Added this
                }, 
                "required": ["item_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "view_cart",
            "description": "Read cart contents",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": "Finalize and save order",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }
]

catalog_str = ", ".join([f"{i['name']} (${i['price']})" for i in CATALOG])
SYSTEM_PROMPT = f"""
You are a Grocery Assistant.
CATALOG: {catalog_str}
KNOWN RECIPES: Sandwich, Pasta, Omelet.
INSTRUCTIONS:
1. If user wants "ingredients for a sandwich", call add_to_cart with item_name="sandwich".
2. If user says "remove 3 apples", pass quantity=3 to remove_from_cart.
3. If user says "place order", call place_order.
"""

# --- 🗣 AUDIO ---
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

# --- 🏁 MAIN LOOP ---
if __name__ == "__main__":
    print("--- 🛒 Grocery Agent (Smarter Version) ---")
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    intro = "Welcome to the grocery store. What do you need today?"
    speak(intro)
    history.append({"role": "assistant", "content": intro})

    while True:
        user_text = listen_to_user()
        if user_text:
            if "bye" in user_text.lower():
                speak("Goodbye!")
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
                    print(f"   ⚙ Executing {name}...")
                    
                    result = "Error"
                    if name == "add_to_cart":
                        result = add_to_cart(args["item_name"], args.get("quantity", 1))
                    elif name == "remove_from_cart":
                        # Now handles quantity!
                        result = remove_from_cart(args["item_name"], args.get("quantity"))
                    elif name == "view_cart":
                        result = view_cart()
                    elif name == "place_order":
                        result = place_order()
                        speak(result)
                        print(f"\n✅ Order saved to {ORDER_FILE}")
                        exit()
                    
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