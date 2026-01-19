import json
import random
import os

# --- EXPANDED THEMES CONFIGURATION ---
THEMES = {
    "CIRCUIT": {
        "name": "Circuit",
        "friction": 0.97,  # Standard Grip
        "colors": {
            "bg": [30, 35, 30],       # Dark Grass
            "road": [50, 50, 55],     # Asphalt
            "wall": [200, 0, 0],      # Red Curb
            "center": [255, 255, 255]
        },
        "title": "AI Learns to Race F1 Style 🏎️",
        "tags": ["f1", "racing", "motorsport"]
    },
    "ICE": {
        "name": "Ice World",
        "friction": 0.93,  # VERY SLIPPERY! Good for drift content
        "colors": {
            "bg": [220, 245, 255],    # White/Blue Snow
            "road": [160, 210, 255],  # Blue Ice
            "wall": [0, 100, 220],    # Deep Blue Wall
            "center": [200, 240, 255]
        },
        "title": "AI Tries Drifting on ICE ❄️",
        "tags": ["drift", "ice", "winter", "rally"]
    },
    "DESERT": {
        "name": "Mars Rally",
        "friction": 0.955,  # Loose Gravel/Dust
        "colors": {
            "bg": [160, 60, 30],      # Red Mars Sand
            "road": [210, 140, 90],   # Dust Road
            "wall": [90, 40, 10],     # Dark Rock
            "center": [255, 200, 150]
        },
        "title": "AI Rallies on MARS 🚀",
        "tags": ["rally", "offroad", "mars", "space"]
    },
    "CYBER": {
        "name": "Cyber City",
        "friction": 0.98,  # High Grip (Arcade style)
        "colors": {
            "bg": [5, 0, 15],         # Void Purple
            "road": [20, 20, 35],     # Dark Blue Asphalt
            "wall": [0, 255, 255],    # Neon Cyan
            "center": [255, 0, 255]   # Neon Pink
        },
        "title": "AI Street Racing at NIGHT 🌃",
        "tags": ["cyberpunk", "neon", "drift", "night"]
    },
    "TOXIC": {
        "name": "Toxic Wasteland",
        "friction": 0.95,  # Sludge (sluggish)
        "colors": {
            "bg": [20, 30, 10],       # Dark Swamp
            "road": [40, 60, 20],     # Sludge Road
            "wall": [100, 255, 0],    # Radioactive Green
            "center": [200, 0, 255]   # Poison Purple
        },
        "title": "AI Survives the WASTELAND ☢️",
        "tags": ["post-apocalyptic", "zombie", "survival"]
    },
    "LAVA": {
        "name": "Volcano",
        "friction": 0.94,  # Slippery/Dangerous
        "colors": {
            "bg": [40, 5, 5],         # Dark Magma
            "road": [80, 20, 20],     # Hardened Lava
            "wall": [255, 80, 0],     # Bright Orange Lava
            "center": [255, 255, 0]   # Yellow Spark
        },
        "title": "AI Races on LAVA 🔥",
        "tags": ["lava", "hot", "danger", "volcano"]
    },
    "RETRO": {
        "name": "Synthwave",
        "friction": 0.975,  # Smooth
        "colors": {
            "bg": [35, 0, 50],        # Deep Indigo
            "road": [60, 0, 90],      # Purple Road
            "wall": [255, 0, 150],    # Hot Pink
            "center": [0, 255, 255]   # Cyan
        },
        "title": "AI 80s Retro Run 🕹️",
        "tags": ["synthwave", "80s", "retro", "arcade"]
    },
    "JUNGLE": {
        "name": "Deep Jungle",
        "friction": 0.96,  # Muddy
        "colors": {
            "bg": [0, 40, 0],         # Deep Green
            "road": [90, 70, 40],     # Brown Mud
            "wall": [30, 100, 30],    # Light Green Bush
            "center": [200, 200, 150]
        },
        "title": "AI Offroad JUNGLE Run 🌴",
        "tags": ["jungle", "offroad", "4x4", "mud"]
    },
    "MIDNIGHT": {
        "name": "Tokyo Drift",
        "friction": 0.965, # Street
        "colors": {
            "bg": [10, 10, 10],       # Pitch Black
            "road": [40, 40, 40],     # Grey Asphalt
            "wall": [255, 215, 0],    # Gold/Yellow Guardrail
            "center": [255, 255, 255]
        },
        "title": "AI Tokyo Drift Run 🇯🇵",
        "tags": ["jdm", "tokyo", "drift", "japan"]
    }
}

def generate_daily_theme():
    # Pick a random theme
    theme_key = random.choice(list(THEMES.keys()))
    theme_data = THEMES[theme_key]

    # Generate a random seed for the track so the map changes daily
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
