import pygame
import math
import os
import json
import numpy as np
from scipy.interpolate import splprep, splev

# --- LOAD THEME ---
try:
    with open("theme.json", "r") as f:
        THEME = json.load(f)
except:
    # Default fallback
    THEME = {
        "map_seed": 42,
        "physics": {"friction": 0.97}, 
        "visuals": {
            "bg": [30,35,30], 
            "wall":[200,0,0], 
            "road":[50,50,55], 
            "center":[80,80,80]
        }
    }

# --- CONFIGURATION ---
WIDTH, HEIGHT = 1080, 1920
WORLD_SIZE = 4000
SENSOR_LENGTH = 300
FPS = 30 

# Visual Constants (Used by Brain for HUD)
COL_BG = THEME["visuals"]["bg"]
COL_WALL = THEME["visuals"]["wall"]

# --- ASSET LOADING HELPER ---
def load_sprite(filename, scale_size=None):
    path = os.path.join("assets", filename)
    if not os.path.exists(path):
        surf = pygame.Surface((scale_size if scale_size else (40, 60)))
        surf.fill((255, 0, 255)) 
        return surf
    img = pygame.image.load(path)
    if scale_size:
        img = pygame.transform.scale(img, scale_size)
    return img

class Car:
    def __init__(self, start_pos):
        self.position = pygame.math.Vector2(start_pos)
        self.velocity = pygame.math.Vector2(0, 0)
        self.angle = -90 
        self.acceleration = 0.0
        self.steering = 0.0
        
        # DYNAMIC PHYSICS FROM THEME
        self.max_speed = 28      
        self.friction = THEME["physics"]["friction"] 
        self.acceleration_rate = 1.2
        self.turn_speed = 0.18   
        
        self.radars = []
        self.alive = True
        self.distance_traveled = 0
        self.is_leader = False
        
        self.sprite_norm = load_sprite("car_normal.png", (50, 85))
        self.sprite_leader = load_sprite("car_leader.png", (50, 85))
        
        self.shadow_surf = pygame.Surface((50, 85), pygame.SRCALPHA)
        pygame.draw.ellipse(self.shadow_surf, (0, 0, 0, 80), (0, 0, 50, 85))

        self.skid_marks = [] 
        self.rect = self.sprite_norm.get_rect(center=self.position)

    def input_steer(self, left=False, right=False):
        if left: self.steering = -1
        if right: self.steering = 1
        
    def input_gas(self):
        self.acceleration = self.acceleration_rate

    def update(self, map_mask):
        if not self.alive: return

        self.velocity *= self.friction
        rad = math.radians(self.angle)
        accel_vec = pygame.math.Vector2(math.cos(rad), math.sin(rad)) * self.acceleration
        self.velocity += accel_vec

        if self.velocity.length() > self.max_speed:
            self.velocity.scale_to_length(self.max_speed)
            
        if self.velocity.length() > 2:
            rotation = self.steering * self.velocity.length() * self.turn_speed
            self.angle += rotation
            
            if abs(self.steering) > 0.5 and self.velocity.length() > 15:
                offset_l = pygame.math.Vector2(-15, -20).rotate(self.angle)
                offset_r = pygame.math.Vector2(-15, 20).rotate(self.angle)
                self.skid_marks.append([self.position + offset_l, 20]) 
                self.skid_marks.append([self.position + offset_r, 20])

        self.position += self.velocity
        self.distance_traveled += self.velocity.length()
        self.rect.center = (int(self.position.x), int(self.position.y))
        self.acceleration = 0
        self.steering = 0
        
        self.check_collision(map_mask)

    def check_collision(self, map_mask):
        try:
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
        for i in range(len(self.skid_marks) - 1, -1, -1):
            pos, life = self.skid_marks[i]
            life -= 1
            self.skid_marks[i][1] = life
            if life <= 0: self.skid_marks.pop(i)
            else:
                adj_pos = camera.apply_point(pos)
                pygame.draw.circle(screen, (30, 30, 30), adj_pos, 4)

        if not self.alive: return

        img = self.sprite_leader if self.is_leader else self.sprite_norm
        rotated_img = pygame.transform.rotate(img, -self.angle - 90)
        rotated_shadow = pygame.transform.rotate(self.shadow_surf, -self.angle - 90)
        
        rect = rotated_img.get_rect(center=self.position)
        cam_pos = camera.apply(rect).topleft
        
        screen.blit(rotated_shadow, (cam_pos[0] + 6, cam_pos[1] + 8))
        screen.blit(rotated_img, cam_pos)
        
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
        x = min(0, max(-(self.width - WIDTH), x))
        y = min(0, max(-(self.height - HEIGHT), y))
        self.camera = pygame.Rect(x, y, self.width, self.height)

class TrackGenerator:
    def __init__(self, seed):
        np.random.seed(seed)
        
    def generate_track(self):
        phys_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        vis_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        
        phys_surf.fill((0,0,0)) 
        vis_surf.fill(THEME["visuals"]["bg"]) # Dynamic BG
        
        points = []
        n_points = 20
        for i in range(n_points):
            angle = (i / n_points) * 2 * math.pi
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

        pygame.draw.lines(phys_surf, (255, 255, 255), True, smooth_points, 450) 
        
        # Dynamic Colors
        pygame.draw.lines(vis_surf, THEME["visuals"]["wall"], True, smooth_points, 480) 
        pygame.draw.lines(vis_surf, (220, 220, 220), True, smooth_points, 450) 
        pygame.draw.lines(vis_surf, THEME["visuals"]["road"], True, smooth_points, 420) 
        pygame.draw.lines(vis_surf, THEME["visuals"]["center"], True, smooth_points, 4)

        start_x, start_y = x_new[0], y_new[0]
        return (int(start_x), int(start_y)), phys_surf, vis_surf
