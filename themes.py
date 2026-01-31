"""
Theme Manager - Rotates visual themes to keep content fresh
"""
import json
import random
from datetime import datetime

THEMES = {
    "NEON_NIGHTS": {
        "name": "Neon Nights",
        "physics": {"friction": 0.98},
        "visuals": {
            "bg": [5, 0, 15],
            "road": [20, 20, 35],
            "wall": [0, 255, 255],
            "center": [255, 0, 255],
            "leader_glow": [0, 255, 255, 120]
        },
        "car_style": "sport",
        "description": "Cyberpunk street racing"
    },
    
    "DESERT_SUNSET": {
        "name": "Desert Sunset",
        "physics": {"friction": 0.955},
        "visuals": {
            "bg": [160, 60, 30],
            "road": [210, 140, 90],
            "wall": [90, 40, 10],
            "center": [255, 200, 150],
            "leader_glow": [255, 100, 0, 120]
        },
        "car_style": "rally",
        "description": "Dusty rally racing"
    },
    
    "ICE_STORM": {
        "name": "Ice Storm",
        "physics": {"friction": 0.93},
        "visuals": {
            "bg": [220, 245, 255],
            "road": [160, 210, 255],
            "wall": [0, 100, 220],
            "center": [200, 240, 255],
            "leader_glow": [100, 200, 255, 120]
        },
        "car_style": "rally",
        "description": "Slippery ice racing"
    },
    
    "VOLCANO": {
        "name": "Volcano",
        "physics": {"friction": 0.94},
        "visuals": {
            "bg": [40, 5, 5],
            "road": [80, 20, 20],
            "wall": [255, 80, 0],
            "center": [255, 255, 0],
            "leader_glow": [255, 100, 0, 120]
        },
        "car_style": "sport",
        "description": "Hot lava racing"
    },
    
    "SYNTHWAVE": {
        "name": "Synthwave",
        "physics": {"friction": 0.975},
        "visuals": {
            "bg": [35, 0, 50],
            "road": [60, 0, 90],
            "wall": [255, 0, 150],
            "center": [0, 255, 255],
            "leader_glow": [255, 0, 200, 120]
        },
        "car_style": "sport",
        "description": "80s retro racing"
    },
    
    "TOXIC_WASTE": {
        "name": "Toxic Waste",
        "physics": {"friction": 0.95},
        "visuals": {
            "bg": [20, 30, 10],
            "road": [40, 60, 20],
            "wall": [100, 255, 0],
            "center": [200, 0, 255],
            "leader_glow": [150, 255, 0, 120]
        },
        "car_style": "rally",
        "description": "Radioactive wasteland"
    },
    
    "DEEP_OCEAN": {
        "name": "Deep Ocean",
        "physics": {"friction": 0.96},
        "visuals": {
            "bg": [0, 20, 40],
            "road": [0, 60, 100],
            "wall": [0, 150, 200],
            "center": [100, 255, 255],
            "leader_glow": [0, 200, 255, 120]
        },
        "car_style": "sport",
        "description": "Underwater racing"
    },
    
    "GOLDEN_HOUR": {
        "name": "Golden Hour",
        "physics": {"friction": 0.97},
        "visuals": {
            "bg": [100, 80, 40],
            "road": [180, 160, 100],
            "wall": [200, 150, 50],
            "center": [255, 220, 100],
            "leader_glow": [255, 200, 50, 120]
        },
        "car_style": "f1",
        "description": "Sunset circuit racing"
    }
}

class ThemeManager:
    def __init__(self, state_file=".theme_state.json"):
        self.state_file = state_file
        self.state = self.load_state()
    
    def load_state(self):
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except:
            return {"current_theme": None, "theme_day": 0}
    
    def save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f)
    
    def should_rotate_theme(self, day_number):
        """Rotate theme every 7 days to keep content fresh"""
        return day_number % 7 == 1  # Day 1, 8, 15, 22...
    
    def get_theme_for_day(self, day_number, force_new=False):
        """Get theme for a specific day"""
        if force_new or self.should_rotate_theme(day_number) or not self.state["current_theme"]:
            # Pick new theme different from current
            available = list(THEMES.keys())
            if self.state["current_theme"] in available:
                available.remove(self.state["current_theme"])
            
            new_theme_key = random.choice(available)
            self.state["current_theme"] = new_theme_key
            self.state["theme_day"] = day_number
            self.save_state()
            
            print(f"🎨 New theme activated: {THEMES[new_theme_key]['name']}")
        
        return THEMES[self.state["current_theme"]]
    
    def apply_theme_to_config(self, theme, base_config=None):
        """Apply theme to theme.json config"""
        if base_config is None:
            try:
                with open("theme.json", 'r') as f:
                    base_config = json.load(f)
            except:
                base_config = {}
        
        # Merge theme into config
        base_config["theme_key"] = self.state["current_theme"]
        base_config["visuals"] = theme["visuals"]
        base_config["car_style"] = theme["car_style"]
        
        # Merge physics (keep existing if present)
        if "physics" not in base_config:
            base_config["physics"] = {}
        base_config["physics"].update(theme["physics"])
        
        # Add metadata
        base_config["meta"] = {
            "theme_name": theme["name"],
            "description": theme["description"],
            "updated": datetime.now().isoformat()
        }
        
        with open("theme.json", 'w') as f:
            json.dump(base_config, f, indent=2)
        
        return base_config

if __name__ == "__main__":
    # Test
    tm = ThemeManager()
    for day in [1, 7, 8, 14, 15]:
        theme = tm.get_theme_for_day(day)
        print(f"Day {day}: {theme['name']} ({theme['car_style']})")
