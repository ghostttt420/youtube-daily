import pygame
import math
import os
import json
import random 
import numpy as np
from scipy.interpolate import splprep, splev

# --- LOAD THEME ---
try:
    with open("theme.json", "r") as f:
        THEME = json.load(f)
except:
    THEME = {
        "map_seed": 42, 
        "physics": {"friction": 0.97, "max_speed": 35, "turn_speed": 0.22, "acceleration_rate": 1.4},
        "visuals": {
            "bg": [8, 10, 15], 
            "wall": [255, 40, 100], 
            "road": [25, 28, 35], 
            "center": [0, 255, 255],
            "leader_glow": [0, 255, 255, 120]
        }
    }

WIDTH, HEIGHT = 1080, 1920
WORLD_SIZE = 4000
SENSOR_LENGTH = THEME.get("sensors", {}).get("length", 300) if isinstance(THEME.get("sensors"), dict) else 300
FPS = 30 
COL_BG = tuple(THEME["visuals"]["bg"])
COL_WALL = tuple(THEME["visuals"]["wall"])
COL_ROAD = tuple(THEME["visuals"]["road"])
COL_CENTER = tuple(THEME["visuals"]["center"])

def load_sprite(filename, scale_size=None):
    path = os.path.join("assets", filename)
    if not os.path.exists(path):
        return pygame.Surface((scale_size if scale_size else (40, 60)))
    img = pygame.image.load(path).convert_alpha()
    if scale_size:
        img = pygame.transform.scale(img, scale_size)
    return img

class Car:
    def __init__(self, start_pos, start_angle):
        self.position = pygame.math.Vector2(start_pos)
        self.velocity = pygame.math.Vector2(0, 0)
        self.angle = start_angle 
        self.acceleration = 0.0
        self.steering = 0.0
        
        # Load physics from theme
        physics = THEME.get("physics", {})
        self.max_speed = physics.get("max_speed", 35)
        self.friction = physics.get("friction", 0.97)
        self.acceleration_rate = physics.get("acceleration_rate", 1.4)
        self.turn_speed = physics.get("turn_speed", 0.22)
        self.reverse_controls = physics.get("reverse_controls", False)
        
        self.alive = True
        self.distance_traveled = 0 
        self.is_leader = False
        self.gates_passed = 0
        self.next_gate_idx = 0
        self.frames_since_gate = 0
        self.fitness = 0  # For HUD display compatibility

        self.radars = [] 

        self.sprite_norm = load_sprite("car_normal.png", (50, 85))
        self.sprite_leader = load_sprite("car_leader.png", (50, 85))
        self.img_smoke = load_sprite("particle_smoke.png", (32, 32))

        self.particles = []
        self.rect = self.sprite_norm.get_rect(center=self.position)

    def get_data(self, checkpoints):
        if not self.alive: return [0, 0]

        target_idx = self.next_gate_idx % len(checkpoints)
        target_pos = pygame.math.Vector2(checkpoints[target_idx])

        dx = target_pos.x - self.position.x
        dy = target_pos.y - self.position.y
        target_rad = math.atan2(dy, dx)
        car_rad = math.radians(self.angle)

        diff = target_rad - car_rad
        while diff > math.pi: diff -= 2 * math.pi
        while diff < -math.pi: diff += 2 * math.pi

        heading_input = diff / math.pi
        dist = self.position.distance_to(target_pos)
        dist_input = min(dist / 1000.0, 1.0)

        return [heading_input, dist_input]

    def input_steer(self, left=False, right=False):
        if self.reverse_controls:
            # Swap left and right
            if left: self.steering = 1
            if right: self.steering = -1
        else:
            if left: self.steering = -1
            if right: self.steering = 1

    def input_gas(self):
        self.acceleration = self.acceleration_rate

    def check_gates(self, checkpoints):
        if not self.alive: return False

        target_idx = self.next_gate_idx % len(checkpoints)
        target_pos = pygame.math.Vector2(checkpoints[target_idx])
        distance = self.position.distance_to(target_pos)

        if distance < 300:
            self.gates_passed += 1
            self.next_gate_idx += 1
            self.frames_since_gate = 0 
            return True
        return False

    def check_car_collision(self, other_cars):
        """Check collision with other cars - funny bumper car style"""
        if not self.alive:
            return
        
        collision_distance = 35  # Car radius approx
        
        for other in other_cars:
            if other is self or not other.alive:
                continue
            
            dist = self.position.distance_to(other.position)
            if dist < collision_distance * 2 and dist > 0:  # Cars touching, but not same position
                # Calculate bounce direction
                diff = self.position - other.position
                collision_normal = diff.normalize() if diff.length() > 0 else pygame.math.Vector2(1, 0)
                
                # Bounce velocities (funny bumper car effect)
                bounce_strength = 0.5
                self.velocity += collision_normal * bounce_strength * 10
                other.velocity -= collision_normal * bounce_strength * 10
                
                # Push cars apart so they don't stick
                overlap = (collision_distance * 2 - dist) / 2
                self.position += collision_normal * overlap
                other.position -= collision_normal * overlap
                
                # Add spin for comedy
                self.angle += random.choice([-15, 15])
                other.angle += random.choice([-15, 15])
                
                # Visual effect - sparks
                for _ in range(3):
                    mid_point = (self.position + other.position) / 2
                    self.particles.append([mid_point, random.randint(10, 20)])
    
    def update(self, map_mask, other_cars=None):
        if not self.alive: return
        self.frames_since_gate += 1
        if self.frames_since_gate > 120:
            self.alive = False
            return
        
        # Check car collisions (funny bumper cars)
        if other_cars:
            self.check_car_collision(other_cars)

        self.velocity *= self.friction
        rad = math.radians(self.angle)
        self.velocity += pygame.math.Vector2(math.cos(rad), math.sin(rad)) * self.acceleration

        if self.velocity.length() > self.max_speed:
            self.velocity.scale_to_length(self.max_speed)

        if self.velocity.length() > 2:
            self.angle += self.steering * self.velocity.length() * self.turn_speed

            if abs(self.steering) > 0.5 and self.velocity.length() > 15:
                if random.random() < 0.3:
                    offset = pygame.math.Vector2(-20, 0).rotate(self.angle)
                    self.particles.append([self.position + offset, 20])

        self.position += self.velocity
        self.distance_traveled += self.velocity.length()

        self.rect.center = (int(self.position.x), int(self.position.y))
        self.acceleration = 0
        self.steering = 0

        try:
            if map_mask.get_at((int(self.position.x), int(self.position.y))) == 0:
                self.alive = False
        except: self.alive = False

    def check_radar(self, map_mask):
        self.radars.clear()
        for degree in [-60, -30, 0, 30, 60]:
            self.cast_ray(degree, map_mask)

    def cast_ray(self, degree, map_mask):
        length = 0
        rad = math.radians(self.angle + degree)
        vec = pygame.math.Vector2(math.cos(rad), math.sin(rad))
        center = self.position

        while length < SENSOR_LENGTH:
            length += 20
            check = center + vec * length
            try:
                if map_mask.get_at((int(check.x), int(check.y))) == 0: break
            except: break
        self.radars.append([(int(check.x), int(check.y)), length])

    def draw(self, screen, camera):
        if not self.alive: return
        
        # Draw glow for leader car
        if self.is_leader:
            draw_pos = camera.apply_point(self.position)
            glow_surface = pygame.Surface((120, 120), pygame.SRCALPHA)
            glow_color = THEME["visuals"].get("leader_glow", [0, 255, 255, 120])
            pygame.draw.circle(glow_surface, glow_color, (60, 60), 50)
            screen.blit(glow_surface, (draw_pos[0]-60, draw_pos[1]-60))
        
        # Draw car sprite
        img = self.sprite_leader if self.is_leader else self.sprite_norm
        rotated_img = pygame.transform.rotate(img, -self.angle - 90)

        draw_pos = camera.apply_point(self.position)
        rect = rotated_img.get_rect(center=draw_pos)
        screen.blit(rotated_img, rect.topleft)

        # Draw particles
        for i in range(len(self.particles)-1, -1, -1):
            pos, life = self.particles[i]
            life -= 1
            self.particles[i][1] = life
            if life <= 0: self.particles.pop(i)
            else:
                adj = camera.apply_point(pos)
                s = self.img_smoke.copy()
                s.set_alpha(int((life/20)*150))
                screen.blit(s, (adj[0]-16, adj[1]-16))

class Camera:
    def __init__(self, width, height):
        self.camera = pygame.Rect(0, 0, width, height)
        self.width = width
        self.height = height
        self.exact_x = 0.0
        self.exact_y = 0.0

    def apply_point(self, pos):
        return (int(pos[0] + self.exact_x), int(pos[1] + self.exact_y))

    def update(self, target):
        target_x = -target.position.x + WIDTH / 2
        target_y = -target.position.y + HEIGHT / 2

        target_x = min(0, max(-(self.width - WIDTH), target_x))
        target_y = min(0, max(-(self.height - HEIGHT), target_y))

        self.exact_x += (target_x - self.exact_x) * 0.1
        self.exact_y += (target_y - self.exact_y) * 0.1

        self.camera = pygame.Rect(int(self.exact_x), int(self.exact_y), self.width, self.height)

class TrackGenerator:
    def __init__(self, seed=None):
        if seed is None:
            map_config = THEME.get("map", {})
            if isinstance(map_config, dict):
                seed = map_config.get("seed", THEME.get("map_seed", 42))
            else:
                seed = THEME.get("map_seed", 42)
        np.random.seed(seed)

    def generate_track(self):
        phys_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        vis_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))

        phys_surf.fill((0,0,0)) 
        vis_surf.fill(COL_BG) 

        points = []
        for i in range(20):
            angle = (i / 20) * 2 * math.pi
            radius = np.random.randint(1100, 1800)
            points.append((WORLD_SIZE // 2 + radius * math.cos(angle), WORLD_SIZE // 2 + radius * math.sin(angle)))
        points.append(points[0]) 

        pts = np.array(points)
        tck, u = splprep(pts.T, u=None, s=0.0, per=1)
        u_new = np.linspace(u.min(), u.max(), 5000)
        x_new, y_new = splev(u_new, tck, der=0)
        smooth_points = list(zip(x_new, y_new))

        checkpoints = smooth_points[::70]

        pygame.draw.lines(phys_surf, (255, 255, 255), True, smooth_points, 450) 

        brush_points = smooth_points[::10]
        wall_color = COL_WALL
        edge_color = (220, 220, 220)
        road_color = COL_ROAD

        for p in brush_points:
            pygame.draw.circle(vis_surf, wall_color, (int(p[0]), int(p[1])), 250)
        for p in brush_points:
            pygame.draw.circle(vis_surf, edge_color, (int(p[0]), int(p[1])), 230)
        for p in brush_points:
            pygame.draw.circle(vis_surf, road_color, (int(p[0]), int(p[1])), 210)

        pygame.draw.lines(vis_surf, COL_CENTER, True, smooth_points, 4)
        
        # Draw VISUAL ROAD BORDERS (kerbs) - makes track edges clear
        border_color = (255, 255, 255, 100)  # Semi-transparent white
        border_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE), pygame.SRCALPHA)
        
        # Draw inner and outer borders
        for p in smooth_points[::5]:  # Every 5th point for performance
            # Inner border
            pygame.draw.circle(border_surf, (255, 255, 255, 60), (int(p[0]), int(p[1])), 212, 2)
            # Outer border  
            pygame.draw.circle(border_surf, (255, 255, 255, 60), (int(p[0]), int(p[1])), 228, 2)
        
        # Blit borders onto visual surface
        vis_surf.blit(border_surf, (0, 0))

        return (int(x_new[0]), int(y_new[0])), phys_surf, vis_surf, checkpoints, math.degrees(math.atan2(y_new[5]-y_new[0], x_new[5]-x_new[0]))


def draw_text_with_outline(screen, text, pos, size=100, color=(255,255,255), outline_color=(0,0,0), outline_width=3):
    """Draw text with outline for better readability"""
    font = pygame.font.SysFont("arial", size, bold=True)
    
    # Draw outline
    for dx in range(-outline_width, outline_width+1):
        for dy in range(-outline_width, outline_width+1):
            if dx != 0 or dy != 0:
                outline = font.render(text, True, outline_color)
                screen.blit(outline, (pos[0]+dx, pos[1]+dy))
    
    # Draw main text
    main = font.render(text, True, color)
    screen.blit(main, pos)


def draw_hud(screen, car, generation, frame_count, checkpoints, challenge_name=None):
    """Draw dynamic HUD that tells a story"""
    
    # Challenge name (top center)
    if challenge_name:
        draw_text_with_outline(
            screen, 
            challenge_name.upper(), 
            (WIDTH//2 - 200, 30), 
            size=60, 
            color=(255, 200, 0)
        )
    
    # Gen number (top left)
    draw_text_with_outline(
        screen, 
        f"GEN {generation}", 
        (30, 120 if challenge_name else 30), 
        size=90, 
        color=(255, 255, 255)
    )
    
    # Time elapsed (top left, below gen)
    seconds = int(frame_count / FPS)
    draw_text_with_outline(
        screen, 
        f"{seconds}s", 
        (30, 230 if challenge_name else 140), 
        size=60, 
        color=(200, 200, 200)
    )
    
    # Speed (top right) - color coded
    speed_kmh = int(car.velocity.length() * 3.6)
    if speed_kmh > 80:
        speed_color = (0, 255, 100)  # Green - fast
    elif speed_kmh > 50:
        speed_color = (255, 255, 0)  # Yellow - medium
    else:
        speed_color = (255, 100, 100)  # Red - slow
    
    draw_text_with_outline(
        screen, 
        f"{speed_kmh} km/h", 
        (WIDTH - 300, 30), 
        size=70, 
        color=speed_color
    )
    
    # Gates passed (top right, below speed)
    draw_text_with_outline(
        screen, 
        f"Gates: {car.gates_passed}", 
        (WIDTH - 300, 120), 
        size=60, 
        color=(0, 255, 255)
    )
    
    # Progress bar (bottom of screen)
    if checkpoints and len(checkpoints) > 0:
        progress = min(car.gates_passed / len(checkpoints), 1.0)
        bar_width = WIDTH - 100
        bar_height = 40
        bar_x = 50
        bar_y = HEIGHT - 100
        
        # Background bar
        pygame.draw.rect(screen, (40, 40, 50), (bar_x, bar_y, bar_width, bar_height), border_radius=20)
        
        # Progress fill (gradient effect) - FIX: Ensure integers
        if progress > 0:
            fill_width = int(bar_width * progress)
            # Color transitions from red -> yellow -> green
            if progress < 0.33:
                fill_color = (255, int(progress * 3 * 255), 0)  # Red to Yellow
            elif progress < 0.66:
                fill_color = (int((1 - (progress - 0.33) * 3) * 255), 255, 0)  # Yellow to Green
            else:
                fill_color = (0, 255, int((progress - 0.66) * 3 * 255))  # Green to Cyan
            
            # Ensure all color values are valid integers
            fill_color = tuple(max(0, min(255, int(c))) for c in fill_color)
            
            pygame.draw.rect(screen, fill_color, (bar_x, bar_y, fill_width, bar_height), border_radius=20)
        
        # Progress percentage text
        progress_text = f"{int(progress * 100)}%"
        draw_text_with_outline(
            screen,
            progress_text,
            (WIDTH//2 - 60, HEIGHT - 105),
            size=50,
            color=(255, 255, 255)
        )
