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
COL_WALL = THEME["visuals"]["wall"]  # <--- FIXED: Restored this variable

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

class TrackGenerator:
    def __init__(self, seed):
        np.random.seed(seed)
        self.center_x = WORLD_SIZE // 2
        self.center_y = WORLD_SIZE // 2
    
    def _create_straight(self, start, angle_deg, length):
        """Create a straight section."""
        angle = math.radians(angle_deg)
        end = (start[0] + length * math.cos(angle),
               start[1] + length * math.sin(angle))
        return end
    
    def _create_arc(self, center, start_angle, sweep_angle, radius, num_points=50):
        """Create an arc (corner)."""
        points = []
        for i in range(num_points + 1):
            t = i / num_points
            angle = math.radians(start_angle + sweep_angle * t)
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            points.append((x, y))
        return points
    
    def _calculate_arc_center(self, start_pos, entry_angle, radius, turn_direction):
        """Calculate arc center given start position, entry angle, radius and direction."""
        # Perpendicular to entry angle
        perp_angle = math.radians(entry_angle + (90 if turn_direction == 'left' else -90))
        center = (start_pos[0] + radius * math.cos(perp_angle),
                  start_pos[1] + radius * math.sin(perp_angle))
        return center
    
    def generate_track(self):
        phys_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        vis_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        
        phys_surf.fill((0,0,0)) 
        vis_surf.fill(THEME["visuals"]["bg"])
        
        # Track definition: list of (type, params)
        # Types: 'straight' -> (length), 'corner' -> (radius, angle, direction)
        # Build a proper race circuit layout
        
        track_sections = [
            ('straight', 600),           # Main straight
            ('corner', 250, 90, 'right'), # T1: 90° right
            ('straight', 400),           # Short straight
            ('corner', 200, 60, 'left'),  # T2: 60° left
            ('straight', 350),           
            ('corner', 300, 45, 'right'), # T3: sweeping right
            ('corner', 300, 45, 'right'), # T4: continues
            ('straight', 500),           # Back straight
            ('corner', 200, 90, 'left'),  # T5: tight left
            ('straight', 300),
            ('corner', 400, 60, 'right'), # T6: long sweeping right
            ('straight', 250),
            ('corner', 180, 90, 'left'),  # T7: tight chicane entry
            ('corner', 180, 90, 'right'), # T8: chicane exit
            ('straight', 400),
            ('corner', 350, 120, 'right'), # T9: hairpin-like
            ('straight', 300),
            ('corner', 250, 60, 'left'),   # T10: back to start
        ]
        
        # Generate track points
        all_points = []
        checkpoints = []
        
        # Start position (main straight, pointing up/left diagonal)
        current_pos = (self.center_x + 800, self.center_y + 600)
        current_angle = 210  # Pointing up-left
        
        for section in track_sections:
            section_type = section[0]
            
            if section_type == 'straight':
                length = section[1]
                # Add start point
                if not all_points:
                    all_points.append(current_pos)
                    checkpoints.append(current_pos)
                
                # Calculate end of straight
                end_pos = self._create_straight(current_pos, current_angle, length)
                
                # Add intermediate points along straight
                num_points = max(2, int(length / 30))
                for i in range(1, num_points + 1):
                    t = i / num_points
                    x = current_pos[0] + t * (end_pos[0] - current_pos[0])
                    y = current_pos[1] + t * (end_pos[1] - current_pos[1])
                    all_points.append((x, y))
                
                current_pos = end_pos
                checkpoints.append(current_pos)
                
            elif section_type == 'corner':
                radius = section[1]
                turn_angle = section[2]
                direction = section[3]
                
                # Calculate arc center
                center = self._calculate_arc_center(current_pos, current_angle, radius, direction)
                
                # Calculate entry angle to arc center
                dx = current_pos[0] - center[0]
                dy = current_pos[1] - center[1]
                start_arc_angle = math.degrees(math.atan2(dy, dx))
                
                # Sweep direction
                sweep = turn_angle if direction == 'left' else -turn_angle
                
                # Generate arc points
                arc_points = self._create_arc(center, start_arc_angle, sweep, radius, num_points=40)
                all_points.extend(arc_points[1:])  # Skip first (it's current_pos)
                
                # Update current position and angle
                current_pos = arc_points[-1]
                current_angle = (current_angle + sweep) % 360
                checkpoints.append(current_pos)
        
        # Close the loop smoothly
        # Remove duplicate last point if close to first
        if len(all_points) > 1:
            first = all_points[0]
            last = all_points[-1]
            dist = math.hypot(first[0] - last[0], first[1] - last[1])
            if dist < 100:
                all_points.pop()
        
        # Draw physics surface (collision mask) - thick white line
        pygame.draw.lines(phys_surf, (255, 255, 255), True, all_points, 450)
        
        # Draw visual track with proper layering
        wall_color = THEME["visuals"]["wall"]
        edge_color = (220, 220, 220)
        road_color = THEME["visuals"]["road"]
        
        # Draw walls (outer boundary)
        pygame.draw.lines(vis_surf, wall_color, True, all_points, 250)
        
        # Draw edge lines
        pygame.draw.lines(vis_surf, edge_color, True, all_points, 230)
        
        # Draw road surface
        pygame.draw.lines(vis_surf, road_color, True, all_points, 210)
        
        # Draw center racing line
        pygame.draw.lines(vis_surf, THEME["visuals"]["center"], True, all_points, 4)
        
        # Calculate start angle for car placement
        start_angle = math.degrees(math.atan2(
            all_points[5][1] - all_points[0][1],
            all_points[5][0] - all_points[0][0]
        ))
        
        return (int(all_points[0][0]), int(all_points[0][1])), phys_surf, vis_surf, checkpoints, start_angle
