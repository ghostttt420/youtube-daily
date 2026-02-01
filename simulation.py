import pygame
import math
import os
import json
import random 
import numpy as np
from scipy.interpolate import splprep, splev
from scipy.spatial.distance import cdist

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
                
                # Gentle bounce (reduced chaos for competitive racing)
                bounce_strength = 0.2  # Reduced from 0.5
                self.velocity += collision_normal * bounce_strength * 5  # Reduced from 10
                other.velocity -= collision_normal * bounce_strength * 5
                
                # Push cars apart so they don't stick
                overlap = (collision_distance * 2 - dist) / 2
                self.position += collision_normal * overlap
                other.position -= collision_normal * overlap
                
                # Minimal spin (pro drivers don't spin out easily)
                self.angle += random.choice([-5, 5])  # Reduced from 15
                other.angle += random.choice([-5, 5])
                
                # Visual effect - sparks
                for _ in range(3):
                    mid_point = (self.position + other.position) / 2
                    self.particles.append([mid_point, random.randint(10, 20)])

    def update(self, map_mask, other_cars=None, wall_mask=None):
        if not self.alive: return
        self.frames_since_gate += 1
        if self.frames_since_gate > 180:  # 6 seconds at 30fps (was 4s/120 frames)
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
            # Pro steering: less sensitive at high speed to prevent oversteer
            speed_factor = min(self.velocity.length(), 20)  # Cap steering effect at 20 speed
            self.angle += self.steering * speed_factor * self.turn_speed * 0.6  # Reduced by 40%

            if abs(self.steering) > 0.5 and self.velocity.length() > 15:
                if random.random() < 0.3:
                    offset = pygame.math.Vector2(-20, 0).rotate(self.angle)
                    self.particles.append([self.position + offset, 20])

        self.position += self.velocity
        self.distance_traveled += self.velocity.length()

        self.rect.center = (int(self.position.x), int(self.position.y))
        self.acceleration = 0
        self.steering = 0

        # Check track boundary collision
        try:
            if map_mask.get_at((int(self.position.x), int(self.position.y))) == 0:
                self.alive = False
        except: self.alive = False
        
        # Check wall collision (if wall_mask provided)
        if wall_mask is not None:
            try:
                if wall_mask.get_at((int(self.position.x), int(self.position.y))) == 1:
                    # Hit the wall - bounce or crash
                    self.alive = False  # Crash into wall
            except: pass

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
        """Generate a professional race track with proper asphalt, curbs, and racing line"""
        phys_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE), pygame.SRCALPHA)
        vis_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))

        phys_surf.fill((0, 0, 0, 0))  # Fully transparent for proper mask 
        vis_surf.fill(COL_BG) 

        # Generate smooth track control points
        points = []
        num_control_points = 12
        for i in range(num_control_points):
            angle = (i / num_control_points) * 2 * math.pi
            # Create flowing track with smooth curves
            base_radius = 1500
            # Use smoother variation
            variation = int(200 * math.sin(i * 1.5) + 150 * math.cos(i * 2.3))
            radius = base_radius + variation
            points.append((
                WORLD_SIZE // 2 + radius * math.cos(angle),
                WORLD_SIZE // 2 + radius * math.sin(angle)
            ))
        points.append(points[0])  # Close the loop

        # Create very smooth spline with many points
        pts = np.array(points)
        tck, u = splprep(pts.T, u=None, s=2.0, per=1)  # s=2.0 for smoother curves
        u_new = np.linspace(u.min(), u.max(), 3000)  # Many points for smoothness
        x_new, y_new = splev(u_new, tck, der=0)
        centerline = [(float(x), float(y)) for x, y in zip(x_new, y_new)]
        
        # Calculate checkpoints (~10 evenly spaced)
        checkpoints = centerline[::(len(centerline)//10)]

        # === PROFESSIONAL TRACK RENDERING ===
        track_half_width = 180  # Half of 360px track width (1.5x wider)
        curb_half_width = 20    # Half of 40px curb width
        
        # Calculate track boundaries
        left_edge = []      # Outer edge (left side looking forward)
        right_edge = []     # Inner edge (right side looking forward)
        left_curb = []      # Outer curb edge
        right_curb = []     # Inner curb edge
        
        for i in range(len(centerline)):
            # Current point and next point for direction
            curr = pygame.math.Vector2(centerline[i])
            next_idx = (i + 1) % len(centerline)
            next_p = pygame.math.Vector2(centerline[next_idx])
            
            # Calculate forward direction
            forward = next_p - curr
            if forward.length() > 0:
                forward = forward.normalize()
                # Perpendicular (normal) pointing left
                normal = pygame.math.Vector2(-forward.y, forward.x)
            else:
                normal = pygame.math.Vector2(0, 1)
            
            # Calculate edge points
            left_pt = curr + normal * track_half_width
            right_pt = curr - normal * track_half_width
            left_curb_pt = curr + normal * (track_half_width - curb_half_width)
            right_curb_pt = curr - normal * (track_half_width - curb_half_width)
            
            left_edge.append((int(left_pt.x), int(left_pt.y)))
            right_edge.append((int(right_pt.x), int(right_pt.y)))
            left_curb.append((int(left_curb_pt.x), int(left_curb_pt.y)))
            right_curb.append((int(right_curb_pt.x), int(right_curb_pt.y)))

        # 1. Create physics collision mask (drivable track area between edges)
        # Draw track as series of quadrilaterals (road segments)
        for i in range(len(centerline) - 1):
            # Create quad for this segment: left->right at i, then right->left at i+1
            quad = [
                left_edge[i],
                right_edge[i],
                right_edge[i + 1],
                left_edge[i + 1]
            ]
            pygame.draw.polygon(phys_surf, (255, 255, 255), quad)
        # Close the loop
        quad = [
            left_edge[-1],
            right_edge[-1],
            right_edge[0],
            left_edge[0]
        ]
        pygame.draw.polygon(phys_surf, (255, 255, 255), quad)

        # 2. Draw outer wall/barrier (beyond left_edge) and create wall collision mask
        wall_points = []
        for i in range(len(centerline)):
            curr = pygame.math.Vector2(centerline[i])
            next_idx = (i + 1) % len(centerline)
            next_p = pygame.math.Vector2(centerline[next_idx])
            forward = next_p - curr
            if forward.length() > 0:
                forward = forward.normalize()
                normal = pygame.math.Vector2(-forward.y, forward.x)
            else:
                normal = pygame.math.Vector2(0, 1)
            wall_pt = curr + normal * (track_half_width + 25)
            wall_points.append((int(wall_pt.x), int(wall_pt.y)))
        
        # Draw wall as thick line segments (not closed polygon)
        for i in range(len(wall_points)):
            p1 = wall_points[i]
            p2 = wall_points[(i + 1) % len(wall_points)]
            pygame.draw.line(vis_surf, COL_WALL, p1, p2, width=20)
        
        # Create wall collision mask (for car collision detection)
        # Use SRCALPHA so (0,0,0,0) pixels don't count in the mask
        wall_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE), pygame.SRCALPHA)
        wall_surf.fill((0, 0, 0, 0))  # Fully transparent
        for i in range(len(wall_points)):
            p1 = wall_points[i]
            p2 = wall_points[(i + 1) % len(wall_points)]
            pygame.draw.line(wall_surf, (255, 255, 255, 255), p1, p2, width=20)
        wall_mask = pygame.mask.from_surface(wall_surf)

        # 3. Draw alternating RED/WHITE curbs (between left_edge and left_curb)
        curb_segments = 24  # Number of curb segments
        segment_size = len(centerline) // curb_segments
        
        for seg in range(curb_segments):
            start_idx = seg * segment_size
            end_idx = min((seg + 1) * segment_size, len(centerline))
            
            # Alternate red and white
            color = (220, 30, 30) if seg % 2 == 0 else (240, 240, 240)  # Red/White curbs
            
            # Create curb polygon for this segment
            curb_poly = []
            # Add left_edge points
            for i in range(start_idx, end_idx):
                curb_poly.append(left_edge[i])
            # Add left_curb points in reverse
            for i in range(end_idx - 1, start_idx - 1, -1):
                curb_poly.append(left_curb[i])
            
            if len(curb_poly) > 2:
                pygame.draw.polygon(vis_surf, color, curb_poly)

        # 4. Draw ASPHALT road surface (between left_curb and right_curb)
        road_polygon = left_curb + right_curb[::-1]  # Combine and close
        pygame.draw.polygon(vis_surf, COL_ROAD, road_polygon)
        
        # 5. Draw dashed RACING LINE in center
        dash_length = 40  # Pixels per dash
        gap_length = 30   # Pixels between dashes
        
        accumulated_dist = 0
        drawing_dash = True
        dash_points = []
        
        for i in range(len(centerline) - 1):
            p1 = pygame.math.Vector2(centerline[i])
            p2 = pygame.math.Vector2(centerline[i + 1])
            seg_dist = p1.distance_to(p2)
            
            accumulated_dist += seg_dist
            
            if drawing_dash:
                dash_points.append((int(p1.x), int(p1.y)))
                if accumulated_dist >= dash_length:
                    # Draw this dash
                    if len(dash_points) > 1:
                        pygame.draw.lines(vis_surf, COL_CENTER, False, dash_points, 6)
                    dash_points = []
                    accumulated_dist = 0
                    drawing_dash = False
            else:
                # In gap
                if accumulated_dist >= gap_length:
                    accumulated_dist = 0
                    drawing_dash = True
                    dash_points = [(int(p1.x), int(p1.y))]

        return (int(x_new[0]), int(y_new[0])), phys_surf, vis_surf, checkpoints, math.degrees(math.atan2(y_new[5]-y_new[0], x_new[5]-x_new[0])), wall_mask


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
    
    # Challenge name (top center) - only show if in active challenge
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
    
    # Speed (top right, smaller) - color coded
    if car is None:
        return  # No car to display speed/gates for
    
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
        (WIDTH - 250, 40), 
        size=45, 
        color=speed_color
    )
    
    # Gates passed (top right, below speed)
    draw_text_with_outline(
        screen, 
        f"Gates: {car.gates_passed}", 
        (WIDTH - 250, 95), 
        size=40, 
        color=(0, 255, 255)
    )
