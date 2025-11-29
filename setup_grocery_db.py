import sqlite3
import json

def create_database():
    conn = sqlite3.connect('grocery_store.db')
    c = conn.cursor()
    
    # 1. Catalog Table
    c.execute('''CREATE TABLE IF NOT EXISTS catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        category TEXT,
        price REAL
    )''')
    
    # 2. Recipes Table (Smart Feature: Ingredients for X)
    c.execute('''CREATE TABLE IF NOT EXISTS recipes (
        dish_name TEXT PRIMARY KEY,
        ingredients TEXT  -- JSON string of item names
    )''')
    
    # 3. Insert Sample Data
    items = [
        ('Milk', 'Dairy', 2.50), ('Eggs', 'Dairy', 3.00), ('Bread', 'Bakery', 2.00),
        ('Peanut Butter', 'Pantry', 4.50), ('Jelly', 'Pantry', 3.00),
        ('Pasta', 'Pantry', 1.50), ('Tomato Sauce', 'Pantry', 2.50), ('Cheese', 'Dairy', 5.00),
        ('Apple', 'Produce', 0.80), ('Banana', 'Produce', 0.50)
    ]
    c.executemany('INSERT OR IGNORE INTO catalog (name, category, price) VALUES (?,?,?)', items)

    # 4. Insert Smart Recipes
    recipes = [
        ('sandwich', json.dumps(['Bread', 'Peanut Butter', 'Jelly'])),
        ('pasta dinner', json.dumps(['Pasta', 'Tomato Sauce', 'Cheese']))
    ]
    c.executemany('INSERT OR REPLACE INTO recipes VALUES (?,?)', recipes)
    
    conn.commit()
    conn.close()
    print("✅ Grocery Database Created!")

if __name__ == "__main__":
    create_database()