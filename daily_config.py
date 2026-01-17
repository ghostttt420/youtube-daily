import json
import random
import os

# --- THEMES CONFIGURATION ---
THEMES = {
    "CIRCUIT": {
        "name": "Circuit",
        "friction": 0.97,  # Standard Grip
        "colors": {
            "bg": [30, 35, 30],       # Dark Grass
            "road": [50, 50, 55],     # Asphalt
            "wall": [200, 0, 0],      # Red Curb
            "center": [80, 80, 80]
        },
        "title": "AI Learns to Race F1 Style 🏎️",
        "tags": ["f1", "racing", "motorsport"]
    },
    "ICE": {
        "name": "Ice World",
        "friction": 0.94,  # SLIPPERY! AI will struggle
        "colors": {
            "bg": [200, 240, 255],    # Light Blue Snow
            "road": [150, 200, 255],  # Blue Ice
            "wall": [0, 100, 200],    # Dark Blue Wall
            "center": [255, 255, 255]
        },
        "title": "AI Tries Drifting on ICE ❄️",
        "tags": ["drift", "ice", "winter", "rally"]
    },
    "DESERT": {
        "name": "Mars Rally",
        "friction": 0.96,  # Loose Gravel
        "colors": {
            "bg": [180, 80, 40],      # Red Sand
            "road": [210, 150, 100],  # Dust Road
            "wall": [100, 50, 20],    # Rock Wall
            "center": [180, 120, 80]
        },
        "title": "AI Rallies on MARS 🚀",
        "tags": ["rally", "offroad", "mars"]
    },
    "NIGHT": {
        "name": "Cyber City",
        "friction": 0.98,  # High Grip
        "colors": {
            "bg": [10, 0, 20],        # Void Purple
            "road": [20, 20, 30],     # Dark
            "wall": [0, 255, 255],    # Neon Cyan
            "center": [255, 0, 128]   # Neon Pink
        },
        "title": "AI Street Racing at NIGHT 🌃",
        "tags": ["cyberpunk", "neon", "drift"]
    }
}

def generate_daily_theme():
    # Pick a random theme
    theme_key = random.choice(list(THEMES.keys()))
    theme_data = THEMES[theme_key]
    
    # Generate a random seed for the track so the map changes daily
    # This prevents the AI from just memorizing one specific left turn
    map_seed = random.randint(0, 999999)
    
    config = {
        "theme_key": theme_key,
        "map_seed": map_seed,
        "physics": {"friction": theme_data["friction"]},
        "visuals": theme_data["colors"],
        "meta": {
            "title": f"{theme_data['title']} (Gen {{gen}})",
            "tags": theme_data["tags"]
        }
    }
    
    with open("theme.json", "w") as f:
        json.dump(config, f, indent=4)
    
    print(f"🌍 Daily Theme Selected: {theme_key} (Seed: {map_seed})")

if __name__ == "__main__":
    generate_daily_theme()
