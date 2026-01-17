import pygame
import math
import os
import numpy as np
from scipy.interpolate import splprep, splev

# --- CONFIGURATION ---
WIDTH, HEIGHT = 1080, 1920
WORLD_SIZE = 4000
SENSOR_LENGTH = 300
FPS = 30 

# --- VISUAL CONSTANTS (Restored for ai_brain.py) ---
# These are used by the brain script for the HUD and background clearing
COL_BG = (30, 35, 30)      # Dark Grass
COL_WALL = (200, 0, 0)     # Red (High contrast for text)

# --- ASSET LOADING HELPER ---
def load_sprite(filename, scale_size=None):
    """Safely loads assets, creating a placeholder if missing."""
    path = os.path.join("assets", filename)
    
    # Fallback if assets.py wasn't run (prevents crashes during local tests)
    if not os.path.exists(path):
        surf = pygame.Surface((scale_size if scale_size else (40, 60)))
        surf.fill((255, 0, 255)) # Bright pink missing texture
        return surf
        
    img = pygame.image.load(path)
    if scale_size:
        img = pygame.transform.scale(img, scale_size)
    return img

class Car:
    def __init__(self, start_pos):
        # 1. Physics State
        self.position = pygame.math.Vector2(start_pos)
        self.velocity = pygame.math.Vector2(0, 0)
        self.angle = -90 # Pointing Up in Pygame (270 deg)
        self.acceleration = 0.0
        self.steering = 0.0
        
        # 2. Handling Tuning (Drift Physics)
        self.max_speed = 28      
        self.friction = 0.97     # High friction = Grip, Low = Ice
        self.acceleration_rate = 1.2
        self.turn_speed = 0.18   
        
        # 3. Game State
        self.radars = []
        self.alive = True
        self.distance_traveled = 0
        self.is_leader = False
        
        # 4. Visual Assets
        # We load these ONCE per car.
        self.sprite_norm = load_sprite("car_normal.png", (50, 85))
        self.sprite_leader = load_sprite("car_leader.png", (50, 85))
        
        # Create Shadow (Generic black blob)
        self.shadow_surf = pygame.Surface((50, 85), pygame.SRCALPHA)
        pygame.draw.ellipse(self.shadow_surf, (0, 0, 0, 80), (0, 0, 50, 85))

        self.skid_marks = [] # Stores tire tracks
        self.rect = self.sprite_norm.get_rect(center=self.position)

    def input_steer(self, left=False, right=False):
        if left: self.steering = -1
        if right: self.steering = 1
        
    def input_gas(self):
        self.acceleration = self.acceleration_rate

    def update(self, map_mask):
        if not self.alive: return

        # --- PHYSICS ENGINE ---
        self.velocity *= self.friction
        
        # Acceleration Vector
        rad = math.radians(self.angle)
        accel_vec = pygame.math.Vector2(math.cos(rad), math.sin(rad)) * self.acceleration
        self.velocity += accel_vec

        # Speed Cap
        if self.velocity.length() > self.max_speed:
            self.velocity.scale_to_length(self.max_speed)
            
        # Turning Logic (Only turn if moving)
        if self.velocity.length() > 2:
            # The car turns based on steering input
            rotation = self.steering * self.velocity.length() * self.turn_speed
            self.angle += rotation
            
            # --- SKID MARK GENERATOR ---
            # If turning hard while moving fast -> Drop skid marks
            if abs(self.steering) > 0.5 and self.velocity.length() > 15:
                offset_l = pygame.math.Vector2(-15, -20).rotate(self.angle)
                offset_r = pygame.math.Vector2(-15, 20).rotate(self.angle)
                self.skid_marks.append([self.position + offset_l, 20]) 
                self.skid_marks.append([self.position + offset_r, 20])

        # Apply Velocity
        self.position += self.velocity
        self.distance_traveled += self.velocity.length()
        self.rect.center = (int(self.position.x), int(self.position.y))

        # Reset Inputs
        self.acceleration = 0
        self.steering = 0
        
        # Check Wall Collision
        self.check_collision(map_mask)

    def check_collision(self, map_mask):
        try:
            # Check center point
            if map_mask.get_at((int(self.position.x), int(self.position.y))) == 0:
                self.alive = False
        except IndexError:
            self.alive = False

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
        # 1. Draw Skid Marks (Under everything)
        for i in range(len(self.skid_marks) - 1, -1, -1):
            pos, life = self.skid_marks[i]
            life -= 1
            self.skid_marks[i][1] = life
            
            if life <= 0:
                self.skid_marks.pop(i)
            else:
                adj_pos = camera.apply_point(pos)
                pygame.draw.circle(screen, (30, 30, 30), adj_pos, 4)

        if not self.alive: return

        # 2. Select Sprite
        img = self.sprite_leader if self.is_leader else self.sprite_norm
        
        # 3. Rotation
        rotated_img = pygame.transform.rotate(img, -self.angle - 90)
        rotated_shadow = pygame.transform.rotate(self.shadow_surf, -self.angle - 90)
        
        # 4. Positioning
        rect = rotated_img.get_rect(center=self.position)
        cam_pos = camera.apply(rect).topleft
        
        # 5. Blit Shadow (Offset +6px for depth)
        screen.blit(rotated_shadow, (cam_pos[0] + 6, cam_pos[1] + 8))
        # 6. Blit Car
        screen.blit(rotated_img, cam_pos)
        
        # 7. Draw Sensors (Debug view for leader)
        if self.is_leader:
            for radar in self.radars:
                end = camera.apply_point(radar[0])
                start = camera.apply_point(self.position)
                pygame.draw.line(screen, (0, 255, 0), start, end, 1)


class Camera:
    def __init__(self, width, height):
        self.camera = pygame.Rect(0, 0, width, height)
        self.width = width
        self.height = height

    def apply(self, entity_rect):
        return entity_rect.move(self.camera.topleft)

    def apply_point(self, pos):
        return (pos[0] + self.camera.x, pos[1] + self.camera.y)

    def update(self, target):
        x = -target.rect.centerx + int(WIDTH / 2)
        y = -target.rect.centery + int(HEIGHT / 2)
        
        # Clamp camera to world bounds
        x = min(0, max(-(self.width - WIDTH), x))
        y = min(0, max(-(self.height - HEIGHT), y))
        self.camera = pygame.Rect(x, y, self.width, self.height)


class TrackGenerator:
    def __init__(self, seed):
        np.random.seed(seed)
        
    def generate_track(self):
        phys_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        vis_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        
        # Physics: Black = Wall
        phys_surf.fill((0,0,0)) 
        # Visual: Dark Grass (Matches COL_BG)
        vis_surf.fill(COL_BG) 
        
        # --- SPLINE GENERATION ---
        points = []
        n_points = 20
        for i in range(n_points):
            angle = (i / n_points) * 2 * math.pi
            # Randomize radius for interesting turns
            radius = np.random.randint(1100, 1800)
            x = WORLD_SIZE // 2 + radius * math.cos(angle)
            y = WORLD_SIZE // 2 + radius * math.sin(angle)
            points.append((x, y))
        points.append(points[0]) 
        
        try:
            pts = np.array(points)
            tck, u = splprep(pts.T, u=None, s=0.0, per=1)
            u_new = np.linspace(u.min(), u.max(), 4000)
            x_new, y_new = splev(u_new, tck, der=0)
            smooth_points = list(zip(x_new, y_new))
        except:
            smooth_points = points

        # --- DRAWING LAYERS ---
        
        # 1. Physics Mask (The "Real" Road)
        pygame.draw.lines(phys_surf, (255, 255, 255), True, smooth_points, 450) 
        
        # 2. Visual Track (The "F1" Look)
        # A. Outer Curbs (Red)
        pygame.draw.lines(vis_surf, (200, 0, 0), True, smooth_points, 480) 
        # B. Inner Edge (White)
        pygame.draw.lines(vis_surf, (220, 220, 220), True, smooth_points, 450) 
        # C. Asphalt (Dark Grey)
        pygame.draw.lines(vis_surf, (50, 50, 55), True, smooth_points, 420) 
        # D. Center Line (Faint Grey)
        pygame.draw.lines(vis_surf, (80, 80, 80), True, smooth_points, 4)

        start_x, start_y = x_new[0], y_new[0]
        return (int(start_x), int(start_y)), phys_surf, vis_surf
