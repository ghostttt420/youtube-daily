import pygame
import math
import numpy as np
from scipy.interpolate import splprep, splev

# --- CONFIGURATION & PALETTE ---
WIDTH, HEIGHT = 1080, 1920  # Vertical (Shorts)
WORLD_SIZE = 4000           # Massive World
CAR_SIZE = 55               # Larger, detailed car
SENSOR_LENGTH = 300
FPS = 60

# Cyberpunk Palette
COL_BG = (10, 10, 18)        # Deep Void Blue
COL_GRID = (30, 30, 50)      # Faint Grid
COL_TRACK = (20, 20, 30)     # Dark Asphalt
COL_WALL = (0, 255, 255)     # Cyan Neon Borders
COL_CAR_LEADER = (255, 0, 110) # Hot Pink (Leader)
COL_CAR_NORM = (50, 100, 255)  # Blue (Normal)
COL_SENSOR = (0, 255, 65)    # Matrix Green

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
        # Center the camera on the target (Leader Car)
        x = -target.rect.centerx + int(WIDTH / 2)
        y = -target.rect.centery + int(HEIGHT / 2)

        # Clamp to map edges
        x = min(0, max(-(self.width - WIDTH), x))
        y = min(0, max(-(self.height - HEIGHT), y))
        
        self.camera = pygame.Rect(x, y, self.width, self.height)

class Car:
    def __init__(self, start_pos):
        # Physics State
        self.position = pygame.math.Vector2(start_pos)
        self.velocity = pygame.math.Vector2(0, 0)
        self.angle = 0  # 0 is East
        self.acceleration = 0.0
        self.steering = 0.0
        
        # Tuning
        self.max_speed = 22      
        self.friction = 0.96     # Lower = more slide
        self.acceleration_rate = 0.8
        self.turn_speed = 0.15   # Steering sensitivity multiplier
        
        # Game State
        self.radars = []
        self.alive = True
        self.distance_traveled = 0
        self.is_leader = False
        self.trail = [] 

        # Graphics (Cached)
        self.img_normal = self._create_sprite(COL_CAR_NORM)
        self.img_leader = self._create_sprite(COL_CAR_LEADER)
        self.image = self.img_normal
        self.rect = self.image.get_rect(center=self.position)

    def _create_sprite(self, color):
        surf = pygame.Surface((CAR_SIZE, CAR_SIZE), pygame.SRCALPHA)
        # Glow
        pygame.draw.circle(surf, (*color, 40), (CAR_SIZE//2, CAR_SIZE//2), CAR_SIZE//2)
        # Body (Sport Shape)
        w, h = CAR_SIZE, CAR_SIZE
        pts = [(w*0.8, h*0.5), (0, 0), (0, h)] # Pointing East (0 deg)
        pygame.draw.polygon(surf, color, pts)
        return surf

    def input_steer(self, left=False, right=False):
        if left: self.steering = -1
        if right: self.steering = 1
        
    def input_gas(self):
        self.acceleration = self.acceleration_rate

    def update(self, map_mask):
        if not self.alive: return

        # 1. Physics Calculation
        self.velocity *= self.friction
        
        # Calculate acceleration vector based on car's angle
        # Note: In Pygame, Angle 0 is East. 
        accel_vec = pygame.math.Vector2(1, 0).rotate(-self.angle) * self.acceleration
        self.velocity += accel_vec

        # Cap Max Speed
        if self.velocity.length() > self.max_speed:
            self.velocity.scale_to_length(self.max_speed)
            
        # Apply Steering (Only if moving)
        if self.velocity.length() > 0.5:
            # The faster you go, the slightly less you turn (stability)
            rotation = self.steering * self.velocity.length() * self.turn_speed
            self.angle -= rotation # Subtract because Y grows downwards

        # Move
        self.position += self.velocity
        self.distance_traveled += self.velocity.length()
        
        # Sync Rect
        self.rect.center = (int(self.position.x), int(self.position.y))
        self.x, self.y = self.position.x, self.position.y

        # Reset Inputs
        self.acceleration = 0
        self.steering = 0

        # Update Visuals
        target_img = self.img_leader if self.is_leader else self.img_normal
        if self.image != target_img: self.image = target_img
        
        # Trail Logic
        if int(self.distance_traveled) % 15 == 0:
            self.trail.append((self.x, self.y))
            if len(self.trail) > 25: self.trail.pop(0)

        # 2. Collision & Sensors
        self.check_collision(map_mask)
        # Radar is checked externally or here, usually externally for optimization

    def check_collision(self, map_mask):
        try:
            if map_mask.get_at((int(self.x), int(self.y))) == 0:
                self.alive = False
        except IndexError:
            self.alive = False

    def check_radar(self, map_mask):
        self.radars.clear()
        # Cast rays in a fan
        for degree in [-60, -30, 0, 30, 60]:
            self.cast_ray(degree, map_mask)

    def cast_ray(self, degree, map_mask):
        length = 0
        # Calculate ray vector
        # Angle logic: Car Angle + Ray Offset
        ray_angle = math.radians(self.angle + degree)
        vec = pygame.math.Vector2(1, 0).rotate(-self.angle - degree)
        
        center = pygame.math.Vector2(self.rect.center)
        
        # March the ray
        while length < SENSOR_LENGTH:
            length += 20 # Step size
            check_pos = center + vec * length
            
            x, y = int(check_pos.x), int(check_pos.y)
            try:
                if map_mask.get_at((x, y)) == 0: # Hit Wall
                    break
            except IndexError:
                break
        
        # Dist calculation
        self.radars.append([(x, y), length])

    def draw(self, screen, camera):
        # Draw Trail
        if len(self.trail) > 1 and self.alive:
            adjusted = [camera.apply_point(p) for p in self.trail]
            color = COL_CAR_LEADER if self.is_leader else COL_CAR_NORM
            pygame.draw.lines(screen, color, False, adjusted, 2)

        # Draw Car (Rotate sprite)
        # Note: Pygame rotate goes Counter-Clockwise, so simply 'self.angle' usually works if 0=Right
        rotated_image = pygame.transform.rotate(self.image, self.angle) 
        new_rect = rotated_image.get_rect(center=self.image.get_rect(center=(self.x, self.y)).center)
        screen.blit(rotated_image, camera.apply(new_rect).topleft)
        
        # Draw Sensors (Leader Only)
        if self.is_leader and self.alive:
            for radar in self.radars:
                pos, dist = radar
                start = camera.apply_point(self.rect.center)
                end = camera.apply_point(pos)
                pygame.draw.line(screen, (0, 255, 65, 80), start, end, 1)
                pygame.draw.circle(screen, COL_SENSOR, end, 3)

class TrackGenerator:
    def __init__(self, seed):
        np.random.seed(seed)
        
    def generate_track(self):
        # Surfaces
        phys_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        vis_surf = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        
        phys_surf.fill((0,0,0)) # Wall
        vis_surf.fill(COL_BG)
        
        # Points
        n_points = 18
        points = []
        for i in range(n_points):
            angle = (i / n_points) * 2 * math.pi
            radius = np.random.randint(1200, 1800)
            x = WORLD_SIZE // 2 + radius * math.cos(angle)
            y = WORLD_SIZE // 2 + radius * math.sin(angle)
            points.append((x, y))
        points.append(points[0]) 
        
        # Smoothing
        pts = np.array(points)
        try:
            tck, u = splprep(pts.T, u=None, s=0.0, per=1)
            u_new = np.linspace(u.min(), u.max(), 3000)
            x_new, y_new = splev(u_new, tck, der=0)
            smooth_points = list(zip(x_new, y_new))
        except:
            smooth_points = points

        # Draw Physics Road (White = Safe)
        pygame.draw.lines(phys_surf, (255, 255, 255), True, smooth_points, 400) 
        
        # Draw Visual Road
        # Grid
        for x in range(0, WORLD_SIZE, 400):
            pygame.draw.line(vis_surf, COL_GRID, (x, 0), (x, WORLD_SIZE))
        for y in range(0, WORLD_SIZE, 400):
            pygame.draw.line(vis_surf, COL_GRID, (0, y), (WORLD_SIZE, y))

        # Layers
        pygame.draw.lines(vis_surf, COL_WALL, True, smooth_points, 410) # Edge
        pygame.draw.lines(vis_surf, COL_TRACK, True, smooth_points, 390) # Road
        
        start_x, start_y = x_new[0], y_new[0]
        return (int(start_x), int(start_y)), phys_surf, vis_surf

# --- DEBUG MODE (MANUAL DRIVE) ---
if __name__ == "__main__":
    pygame.init()
    win = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    
    gen = TrackGenerator(42)
    start, phys, vis = gen.generate_track()
    mask = pygame.mask.from_surface(phys)
    
    car = Car(start)
    car.is_leader = True
    cam = Camera(WORLD_SIZE, WORLD_SIZE)
    
    while True:
        clock.tick(FPS)
        for e in pygame.event.get():
            if e.type == pygame.QUIT: exit()
            
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]: car.input_steer(left=True)
        if keys[pygame.K_RIGHT]: car.input_steer(right=True)
        car.input_gas() # Always gas
        
        car.update(mask)
        car.check_radar(mask)
        cam.update(car)
        
        win.fill(COL_BG)
        win.blit(vis, (cam.camera.x, cam.camera.y))
        car.draw(win, cam)
        pygame.display.flip()
