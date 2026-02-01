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
COL_WALL = THEME["visuals"]["wall"]

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
        self.max_speed = 29      
        self.friction = THEME["physics"]["friction"] 
        self.acceleration_rate = 1.2
        self.turn_speed = 0.18   
        self.alive = True
        self.distance_traveled = 0 
        self.is_leader = False
        self.gates_passed = 0
        self.next_gate_idx = 0
        self.frames_since_gate = 0
        
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

    def update(self, map_mask, other_cars=None, wall_mask=None):
        if not self.alive: return
        self.frames_since_gate += 1
        if self.frames_since_gate > 180:  # 6 seconds (was 3s)
            self.alive = False
            return
        
        # Check car collisions (gentle bumper cars)
        if other_cars:
            self.check_car_collision(other_cars)

        self.velocity *= self.friction
        rad = math.radians(self.angle)
        self.velocity += pygame.math.Vector2(math.cos(rad), math.sin(rad)) * self.acceleration

        if self.velocity.length() > self.max_speed:
            self.velocity.scale_to_length(self.max_speed)
            
        if self.velocity.length() > 2:
            # Pro steering: reduced sensitivity
            speed_factor = min(self.velocity.length(), 20)
            self.angle += self.steering * speed_factor * self.turn_speed * 0.6
            
            if abs(self.steering) > 0.5 and self.velocity.length() > 15:
                if random.random() < 0.3:
                    offset = pygame.math.Vector2(-20, 0).rotate(self.angle)
                    self.particles.append([self.position + offset, 20])

        self.position += self.velocity
        self.distance_traveled += self.velocity.length()
        
        self.rect.center = (int(self.position.x), int(self.position.y))
        self.acceleration = 0
        self.steering = 0
        
        # Cars no longer die when going off track (can drive anywhere)

    def check_car_collision(self, other_cars):
        """Gentle bumper car collision"""
        if not self.alive:
            return
        
        collision_distance = 35
        
        for other in other_cars:
            if other is self or not other.alive:
                continue
            
            dist = self.position.distance_to(other.position)
            if dist < collision_distance * 2 and dist > 0:
                diff = self.position - other.position
                collision_normal = diff.normalize() if diff.length() > 0 else pygame.math.Vector2(1, 0)
                
                # Gentle bounce
                bounce_strength = 0.2
                self.velocity += collision_normal * bounce_strength * 5
                other.velocity -= collision_normal * bounce_strength * 5
                
                # Push apart
                overlap = (collision_distance * 2 - dist) / 2
                self.position += collision_normal * overlap
                other.position -= collision_normal * overlap
                
                # Small spin
                self.angle += random.choice([-5, 5])
                other.angle += random.choice([-5, 5])

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
        img = self.sprite_leader if self.is_leader else self.sprite_norm
        rotated_img = pygame.transform.rotate(img, -self.angle - 90)
        
        draw_pos = camera.apply_point(self.position)
        rect = rotated_img.get_rect(center=draw_pos)
        screen.blit(rotated_img, rect.topleft)
        
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

def draw_text_with_outline(screen, text, pos, size=40, color=(255,255,255), outline_color=(0,0,0), outline_width=2):
    font = pygame.font.SysFont("consolas", size, bold=True)
    for dx in range(-outline_width, outline_width+1):
        for dy in range(-outline_width, outline_width+1):
            if dx != 0 or dy != 0:
                outline = font.render(text, True, outline_color)
                screen.blit(outline, (pos[0]+dx, pos[1]+dy))
    main = font.render(text, True, color)
    screen.blit(main, pos)

class TrackGenerator:
    def __init__(self, seed):
        np.random.seed(seed)
    
    def generate_track(self):
        phys_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE), pygame.SRCALPHA)
        vis_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        
        phys_surf.fill((0, 0, 0, 0)) 
        vis_surf.fill(THEME["visuals"]["bg"]) 
        
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
        
        # Physics mask - thick track (900px total width)
        pygame.draw.lines(phys_surf, (255, 255, 255, 255), True, smooth_points, 450) 
        
        # Visual rendering
        brush_points = smooth_points[::10]
        wall_color = THEME["visuals"]["wall"]
        edge_color = (220, 220, 220)
        road_color = THEME["visuals"]["road"]
        
        for p in brush_points:
            pygame.draw.circle(vis_surf, wall_color, (int(p[0]), int(p[1])), 250)
        for p in brush_points:
            pygame.draw.circle(vis_surf, edge_color, (int(p[0]), int(p[1])), 230)
        for p in brush_points:
            pygame.draw.circle(vis_surf, road_color, (int(p[0]), int(p[1])), 210)
            
        pygame.draw.lines(vis_surf, THEME["visuals"]["center"], True, smooth_points, 4)
        
        return (int(x_new[0]), int(y_new[0])), phys_surf, vis_surf, checkpoints, math.degrees(math.atan2(y_new[5]-y_new[0], x_new[5]-x_new[0]))
