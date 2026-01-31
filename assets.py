import pygame
import os
import json

ASSET_DIR = "assets"
if not os.path.exists(ASSET_DIR):
    os.makedirs(ASSET_DIR)

def load_theme():
    """Load theme colors if available"""
    try:
        with open("theme.json", "r") as f:
            return json.load(f)
    except:
        return {}

def create_f1_sprite(color, filename, accent_color=None):
    """Generates a detailed F1-style car sprite."""
    w, h = 60, 100
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    
    body_col = color
    accent_col = accent_color or (min(c + 40, 255) for c in color)
    tire_col = (20, 20, 20)
    tire_rim = (80, 80, 80)
    cockpit_col = (10, 10, 10)
    helmet_col = (255, 255, 0)  # Yellow helmet like Senna
    wing_col = (40, 40, 40)
    halo_col = (60, 60, 60)
    
    # Shadow
    pygame.draw.ellipse(surf, (0, 0, 0, 40), (8, 8, w-16, h-16))
    
    # Rear Wing (DRS style)
    pygame.draw.rect(surf, wing_col, (8, 88, 44, 8))
    pygame.draw.rect(surf, (30, 30, 30), (28, 88, 4, 8))  # Center support
    
    # Rear Tires (bigger, realistic)
    for x in [2, 48]:
        pygame.draw.ellipse(surf, tire_col, (x, 58, 12, 28))
        pygame.draw.ellipse(surf, tire_rim, (x+3, 65, 6, 14))  # Rim
    
    # Sidepods (aero shape)
    pygame.draw.polygon(surf, body_col, [(12, 55), (48, 55), (46, 75), (14, 75)])
    pygame.draw.polygon(surf, accent_col if isinstance(accent_col, tuple) else body_col, 
                       [(15, 58), (45, 58), (44, 72), (16, 72)])
    
    # Main Body (sleek F1 shape)
    pygame.draw.polygon(surf, body_col, [(20, 15), (40, 15), (46, 55), (43, 90), (17, 90), (14, 55)])
    
    # Nose cone
    pygame.draw.polygon(surf, body_col, [(25, 5), (35, 5), (40, 15), (20, 15)])
    
    # Front Wing (complex modern F1 wing)
    pygame.draw.polygon(surf, wing_col, [(5, 2), (55, 2), (45, 8), (15, 8)])
    pygame.draw.polygon(surf, (60, 60, 60), (15, 8), (45, 8), (40, 12), (20, 12))
    
    # Front Tires
    for x in [0, 50]:
        pygame.draw.ellipse(surf, tire_col, (x, 12, 12, 22))
        pygame.draw.ellipse(surf, tire_rim, (x+3, 18, 6, 10))
    
    # Cockpit (open)
    pygame.draw.ellipse(surf, cockpit_col, (24, 45, 12, 20))
    
    # Halo (safety device)
    pygame.draw.arc(surf, halo_col, (22, 38, 16, 16), 0, 3.14, 2)
    
    # Driver Helmet
    pygame.draw.circle(surf, helmet_col, (30, 48), 5)
    pygame.draw.circle(surf, (0, 0, 0), (30, 48), 5, 1)  # Helmet outline
    pygame.draw.rect(surf, (255, 140, 0), (28, 46, 4, 2))  # Visor
    
    # Engine air intake (shark fin style)
    pygame.draw.polygon(surf, accent_col if isinstance(accent_col, tuple) else (min(c+30, 255) for c in body_col), 
                       [(28, 25), (32, 25), (33, 45), (27, 45)])
    
    # Sponsor/logo placeholder
    pygame.draw.rect(surf, (255, 255, 255, 180), (26, 65, 8, 4))
    
    pygame.image.save(surf, os.path.join(ASSET_DIR, filename))
    print(f"🎨 Generated F1 sprite: {filename}")
    return surf

def create_rally_sprite(color, filename):
    """Generates a rugged rally car sprite for off-road challenges."""
    w, h = 64, 90
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    
    body_col = color
    dark_col = tuple(max(0, c - 50) for c in color)
    tire_col = (30, 30, 30)
    window_col = (50, 60, 70)
    light_col = (255, 255, 200)
    
    # Shadow
    pygame.draw.ellipse(surf, (0, 0, 0, 40), (6, 6, w-12, h-12))
    
    # Large off-road tires
    for x in [2, 44]:
        pygame.draw.rect(surf, tire_col, (x, 20, 18, 22), border_radius=4)  # Front
        pygame.draw.rect(surf, tire_col, (x, 58, 18, 22), border_radius=4)  # Rear
    
    # Main body (boxy rally style)
    pygame.draw.polygon(surf, body_col, [(12, 25), (52, 25), (54, 70), (10, 70)])
    
    # Hood
    pygame.draw.polygon(surf, dark_col, [(12, 25), (52, 25), (50, 15), (14, 15)])
    
    # Roof/windows
    pygame.draw.polygon(surf, window_col, [(16, 30), (48, 30), (46, 45), (18, 45)])
    pygame.draw.polygon(surf, body_col, [(14, 20), (50, 20), (48, 30), (16, 30)])  # Roof
    
    # Light bar (rally style)
    pygame.draw.rect(surf, (40, 40, 40), (8, 12, 48, 6))
    pygame.draw.circle(surf, light_col, (14, 15), 3)
    pygame.draw.circle(surf, light_col, (22, 15), 3)
    pygame.draw.circle(surf, light_col, (30, 15), 3)
    pygame.draw.circle(surf, light_col, (38, 15), 3)
    pygame.draw.circle(surf, light_col, (46, 15), 3)
    
    # Spoiler
    pygame.draw.rect(surf, dark_col, (8, 72, 48, 8))
    pygame.draw.rect(surf, (60, 60, 60), (30, 72, 4, 8))
    
    # Mud flaps
    pygame.draw.rect(surf, (80, 80, 80), (6, 75, 6, 10))
    pygame.draw.rect(surf, (80, 80, 80), (52, 75, 6, 10))
    
    # Roll cage visible through windows
    pygame.draw.line(surf, (100, 100, 100), (20, 32), (20, 43), 2)
    pygame.draw.line(surf, (100, 100, 100), (44, 32), (44, 43), 2)
    pygame.draw.line(surf, (100, 100, 100), (20, 38), (44, 38), 2)
    
    pygame.image.save(surf, os.path.join(ASSET_DIR, filename))
    print(f"🎨 Generated Rally sprite: {filename}")
    return surf

def create_sportscar_sprite(color, filename):
    """Generates a sleek sports car for street racing."""
    w, h = 58, 95
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    
    body_col = color
    dark_col = tuple(max(0, c - 40) for c in color)
    tire_col = (25, 25, 25)
    window_col = (20, 25, 35)
    
    # Shadow
    pygame.draw.ellipse(surf, (0, 0, 0, 35), (8, 8, w-16, h-16))
    
    # Wide sport tires
    for x in [3, 43]:
        pygame.draw.ellipse(surf, tire_col, (x, 20, 14, 18))
        pygame.draw.ellipse(surf, tire_col, (x, 62, 14, 18))
    
    # Sleek body (low and wide)
    pygame.draw.polygon(surf, body_col, [(15, 30), (43, 30), (46, 70), (12, 70)])
    
    # Long hood
    pygame.draw.polygon(surf, body_col, [(18, 8), (40, 8), (43, 30), (15, 30)])
    pygame.draw.polygon(surf, dark_col, [(20, 12), (38, 12), (40, 28), (18, 28)])
    
    # Windshield (steep angle)
    pygame.draw.polygon(surf, window_col, [(16, 30), (42, 30), (39, 42), (19, 42)])
    
    # Cabin
    pygame.draw.polygon(surf, window_col, [(18, 42), (40, 42), (37, 52), (21, 52)])
    
    # Spoiler (sleek)
    pygame.draw.polygon(surf, dark_col, [(10, 70), (48, 70), (46, 76), (12, 76)])
    
    # Headlights (sleek LED style)
    pygame.draw.polygon(surf, (200, 220, 255), [(18, 18), (26, 18), (25, 22), (19, 22)])
    pygame.draw.polygon(surf, (200, 220, 255), [(32, 18), (40, 18), (39, 22), (33, 22)])
    
    # Tail lights
    pygame.draw.rect(surf, (220, 0, 0), (14, 72, 10, 4))
    pygame.draw.rect(surf, (220, 0, 0), (34, 72, 10, 4))
    
    # Side intake
    pygame.draw.polygon(surf, (30, 30, 30), [(12, 50), (18, 50), (17, 58), (13, 58)])
    pygame.draw.polygon(surf, (30, 30, 30), [(40, 50), (46, 50), (45, 58), (41, 58)])
    
    pygame.image.save(surf, os.path.join(ASSET_DIR, filename))
    print(f"🎨 Generated Sportscar sprite: {filename}")
    return surf

def generate_fx_assets():
    """Simple smoke puff, no more distracting neon."""
    surf = pygame.Surface((32, 32), pygame.SRCALPHA)
    
    for i in range(16, 0, -1):
        alpha = int(150 * (1 - (i / 16)))
        pygame.draw.circle(surf, (200, 200, 200, alpha), (16, 16), i)
        
    pygame.image.save(surf, os.path.join(ASSET_DIR, "particle_smoke.png"))
    print("✨ Generated FX assets: Smoke Only")

def generate_tire_trail():
    """Tire marks for drift effects."""
    surf = pygame.Surface((20, 40), pygame.SRCALPHA)
    for i in range(20, 0, -1):
        alpha = int(100 * (1 - (i / 20)))
        pygame.draw.ellipse(surf, (40, 40, 40, alpha), (2, 0, 16, 40))
    pygame.image.save(surf, os.path.join(ASSET_DIR, "tire_trail.png"))
    print("✨ Generated tire trail effect")

def get_car_style_from_theme():
    """Determine car style from theme.json or challenges.json"""
    theme = load_theme()
    
    # First check if theme has explicit car_style
    if "car_style" in theme:
        return theme["car_style"]
    
    # Check active challenge for car_style
    try:
        import json
        with open("challenges.json", "r") as f:
            challenges = json.load(f)
            active = challenges.get("active_challenge")
            if active and "car_style" in active:
                return active["car_style"]
    except:
        pass
    
    # Fall back to theme_key mapping
    theme_key = theme.get("theme_key", "CIRCUIT")
    style_map = {
        "CIRCUIT": "f1",
        "ICE": "rally",
        "DESERT": "rally",
        "CYBER": "sport",
        "TOXIC": "rally",
        "LAVA": "rally",
        "RETRO": "sport",
        "JUNGLE": "rally",
        "MIDNIGHT": "sport"
    }
    
    return style_map.get(theme_key, "f1")

def generate_all_assets():
    pygame.init()
    
    # Determine car style based on theme
    car_style = get_car_style_from_theme()
    print(f"🚗 Car style for this theme: {car_style.upper()}")
    
    if car_style == "f1":
        # F1 cars - red leader, blue pack
        create_f1_sprite((220, 0, 0), "car_leader.png", (255, 50, 50))  # Ferrari red
        create_f1_sprite((0, 0, 220), "car_normal.png", (50, 100, 255))  # RB blue
    elif car_style == "rally":
        # Rally cars - works better on dirt/ice
        create_rally_sprite((220, 100, 0), "car_leader.png")  # Orange
        create_rally_sprite((0, 100, 220), "car_normal.png")  # Blue
    elif car_style == "sport":
        # Sports cars - sleek for street racing
        create_sportscar_sprite((220, 0, 50), "car_leader.png")  # Pink/red
        create_sportscar_sprite((50, 50, 220), "car_normal.png")  # Blue
    else:
        # Default to F1
        create_f1_sprite((220, 0, 0), "car_leader.png")
        create_f1_sprite((0, 0, 220), "car_normal.png")
    
    # FX
    generate_fx_assets()
    generate_tire_trail()
    
    print("✅ All assets generated.")

if __name__ == "__main__":
    generate_all_assets()
