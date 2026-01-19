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
    THEME = {"map_seed": 42, "physics": {"friction": 0.97}, "visuals": {"bg": [30,35,30], "wall":[200,0,0], "road":[50,50,55], "center":[80,80,80]}}

WIDTH, HEIGHT = 1080, 1920
WORLD_SIZE = 4000
SENSOR_LENGTH = 300
FPS = 30 
COL_BG = THEME["visuals"]["bg"]

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
        self.max_speed = 28      
        self.friction = THEME["physics"]["friction"] 
        self.acceleration_rate = 1.2
        self.turn_speed = 0.18   
        self.alive = True
        self.distance_traveled = 0 
        self.is_leader = False
        self.gates_passed = 0
        self.next_gate_idx = 0
        self.frames_since_gate = 0
        
        self.sprite_norm = load_sprite("car_normal.png", (50, 85))
        self.sprite_leader = load_sprite("car_leader.png", (50, 85))
        self.img_smoke = load_sprite("particle_smoke.png", (32, 32))
        
        self.particles = []
        # We don't rely on rect for physics anymore, only for drawing
        self.rect = self.sprite_norm.get_rect(center=self.position)

    def update(self, map_mask):
        if not self.alive: return
        self.frames_since_gate += 1
        if self.frames_since_gate > 90:
            self.alive = False
            return

        self.velocity *= self.friction
        rad = math.radians(self.angle)
        self.velocity += pygame.math.Vector2(math.cos(rad), math.sin(rad)) * self.acceleration

        if self.velocity.length() > self.max_speed:
            self.velocity.scale_to_length(self.max_speed)
            
        if self.velocity.length() > 2:
            # Steering
            self.angle += self.steering * self.velocity.length() * self.turn_speed
            
            # Drift Smoke Logic
            if abs(self.steering) > 0.5 and self.velocity.length() > 15:
                if random.random() < 0.3:
                    offset = pygame.math.Vector2(-20, 0).rotate(self.angle)
                    self.particles.append([self.position + offset, 20])

        self.position += self.velocity
        self.distance_traveled += self.velocity.length()
        
        # Update Rect for drawing only
        self.rect.center = (int(self.position.x), int(self.position.y))
        self.acceleration = 0
        self.steering = 0
        
        # Collision Check
        try:
            if map_mask.get_at((int(self.position.x), int(self.position.y))) == 0:
                self.alive = False
        except: self.alive = False

    def draw(self, screen, camera):
        if not self.alive: return
        img = self.sprite_leader if self.is_leader else self.sprite_norm
        rotated_img = pygame.transform.rotate(img, -self.angle - 90)
        
        # Draw Car
        # Important: We calculate position manually from camera to avoid rect-rounding jitter
        draw_pos = camera.apply_point(self.position)
        rect = rotated_img.get_rect(center=draw_pos)
        screen.blit(rotated_img, rect.topleft)
        
        # Draw Smoke
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
        # Float precision coordinates to prevent "grid snapping"
        self.exact_x = 0.0
        self.exact_y = 0.0

    def apply_point(self, pos):
        # Returns the screen coordinates for a world position
        return (int(pos[0] + self.exact_x), int(pos[1] + self.exact_y))

    def update(self, target):
        # 1. Target the TRUE float position, not the wobbling bounding box center
        target_x = -target.position.x + WIDTH / 2
        target_y = -target.position.y + HEIGHT / 2
        
        # 2. Clamp to map bounds
        target_x = min(0, max(-(self.width - WIDTH), target_x))
        target_y = min(0, max(-(self.height - HEIGHT), target_y))

        # 3. Butter Smooth Lerp
        # We move 10% of the way to the target every frame.
        # This eats the micro-jitters.
        self.exact_x += (target_x - self.exact_x) * 0.1
        self.exact_y += (target_y - self.exact_y) * 0.1
        
        # We maintain the rect for compatibility, but mainly use exact_x/y
        self.camera = pygame.Rect(int(self.exact_x), int(self.exact_y), self.width, self.height)

class TrackGenerator:
    def __init__(self, seed):
        np.random.seed(seed)
    
    def generate_track(self):
        phys_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        vis_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        
        phys_surf.fill((0,0,0)) 
        vis_surf.fill(THEME["visuals"]["bg"]) 
        
        points = []
        for i in range(20):
            angle = (i / 20) * 2 * math.pi
            radius = np.random.randint(1100, 1800)
            points.append((WORLD_SIZE // 2 + radius * math.cos(angle), WORLD_SIZE // 2 + radius * math.sin(angle)))
        points.append(points[0]) 
        
        pts = np.array(points)
        tck, u = splprep(pts.T, u=None, s=0.0, per=1)
        # Increased resolution to 5000 for smoother curves
        u_new = np.linspace(u.min(), u.max(), 5000)
        x_new, y_new = splev(u_new, tck, der=0)
        smooth_points = list(zip(x_new, y_new))
        
        checkpoints = smooth_points[::70]
        
        # --- PHYSICS LAYER ---
        # Drawing one big line is fine for the collision mask
        pygame.draw.lines(phys_surf, (255, 255, 255), True, smooth_points, 450) 
        
        # --- VISUAL LAYER (BRUSH STROKE METHOD) ---
        # Instead of drawing lines (which glitch at sharp turns), we draw circles.
        # This guarantees perfect round walls with no tearing.
        
        # Optimization: Don't draw every single point, skip some to save startup time
        # Since our brush is huge (250px), stepping by 10 points (approx 20px) is fine.
        brush_points = smooth_points[::10]
        
        wall_color = THEME["visuals"]["wall"]
        edge_color = (220, 220, 220)
        road_color = THEME["visuals"]["road"]
        
        # 1. Base Wall (Widest)
        for p in brush_points:
            pygame.draw.circle(vis_surf, wall_color, (int(p[0]), int(p[1])), 250)
            
        # 2. White Edge/Curb
        for p in brush_points:
            pygame.draw.circle(vis_surf, edge_color, (int(p[0]), int(p[1])), 230)
            
        # 3. Asphalt (Road)
        for p in brush_points:
            pygame.draw.circle(vis_surf, road_color, (int(p[0]), int(p[1])), 210)
            
        # 4. Center Line (Lines work fine for thin things)
        pygame.draw.lines(vis_surf, THEME["visuals"]["center"], True, smooth_points, 4)
        
        return (int(x_new[0]), int(y_new[0])), phys_surf, vis_surf, checkpoints, math.degrees(math.atan2(y_new[5]-y_new[0], x_new[5]-x_new[0]))
