import pygame
import math
import numpy as np
from scipy.interpolate import splprep, splev

# --- HIGH TIER VISUALS ---
WIDTH, HEIGHT = 1080, 1920
WORLD_SIZE = 4000  # The map is 4x bigger than the screen
CAR_SIZE = 45      # Bigger, detailed cars
SENSOR_LENGTH = 250
FPS = 60

# Neon Cyberpunk Palette
COL_BG = (10, 10, 18)        # Deep Void Blue
COL_GRID = (30, 30, 50)      # Faint Grid lines
COL_TRACK = (20, 20, 30)     # Dark Asphalt
COL_WALL = (0, 255, 255)     # Cyan Neon Borders
COL_CAR_LEADER = (255, 0, 110) # Hot Pink (Leader)
COL_CAR_NORM = (50, 100, 255) # Blue (Normal)
COL_SENSOR = (0, 255, 65)    # Matrix Green

class Camera:
    def __init__(self, width, height):
        self.camera = pygame.Rect(0, 0, width, height)
        self.width = width
        self.height = height

    def apply(self, entity_rect):
        """Returns a rect shifted by camera coordinates"""
        return entity_rect.move(self.camera.topleft)

    def apply_point(self, pos):
        """Returns a point (x,y) shifted by camera coordinates"""
        return (pos[0] + self.camera.x, pos[1] + self.camera.y)

    def update(self, target):
        """Follow the target (Lead Car)"""
        # Calculate offset to center the target
        x = -target.rect.centerx + int(WIDTH / 2)
        y = -target.rect.centery + int(HEIGHT / 2)

        # Clamp camera to world bounds (so we don't see black void edges)
        x = min(0, max(-(self.width - WIDTH), x))
        y = min(0, max(-(self.height - HEIGHT), y))
        
        self.camera = pygame.Rect(x, y, self.width, self.height)

class Car:
    def __init__(self, start_pos):
        self.x, self.y = start_pos
        self.angle = 0
        self.speed = 0
        self.radars = []
        self.alive = True
        self.distance_traveled = 0
        self.is_leader = False
        
        # Visuals: Trail Buffer
        self.trail = [] 

        # Base Sprite
        self.image = pygame.Surface((CAR_SIZE, CAR_SIZE), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def draw_sprite(self):
        """Redraws the car sprite (needed if color changes)"""
        self.image.fill((0,0,0,0))
        color = COL_CAR_LEADER if self.is_leader else COL_CAR_NORM
        
        # 1. Glow Effect (Faint Circle)
        pygame.draw.circle(self.image, (*color, 50), (CAR_SIZE//2, CAR_SIZE//2), CAR_SIZE//2)
        # 2. Hard Body (Triangle)
        pts = [(CAR_SIZE, CAR_SIZE//2), (0, 0), (0, CAR_SIZE)]
        pygame.draw.polygon(self.image, color, pts)

    def update(self, map_mask):
        if not self.alive: return

        # Physics
        self.x += math.cos(math.radians(360 - self.angle)) * self.speed
        self.y += math.sin(math.radians(360 - self.angle)) * self.speed
        
        self.distance_traveled += self.speed
        self.rect.center = (int(self.x), int(self.y))
        
        # Trail Logic (Cyberpunk tail)
        if self.distance_traveled % 10 == 0:
            self.trail.append((self.x, self.y))
            if len(self.trail) > 15: self.trail.pop(0)

        # Collision & Radar
        self.check_collision(map_mask)
        self.check_radar(map_mask)

    def check_collision(self, map_mask):
        try:
            # If center of car hits a wall (Black color on mask)
            if map_mask.get_at((int(self.x), int(self.y))) == 0:
                self.alive = False
        except IndexError:
            self.alive = False

    def check_radar(self, map_mask):
        self.radars.clear()
        for degree in [-90, -45, 0, 45, 90]:
            self.cast_ray(degree, map_mask)

    def cast_ray(self, degree, map_mask):
        length = 0
        x, y = int(self.x), int(self.y)
        
        # Raycast loop
        while length < SENSOR_LENGTH:
            length += 10 # Step size optimization
            x = int(self.rect.center[0] + math.cos(math.radians(360 - (self.angle + degree))) * length)
            y = int(self.rect.center[1] + math.sin(math.radians(360 - (self.angle + degree))) * length)
            
            try:
                if map_mask.get_at((x, y)) == 0: # Hit Wall
                    break
            except IndexError:
                break
        
        dist = int(math.sqrt(math.pow(x - self.rect.center[0], 2) + math.pow(y - self.rect.center[1], 2)))
        self.radars.append([(x, y), dist])

    def rotate(self, left=False, right=False):
        if left: self.angle += 5
        if right: self.angle -= 5

    def draw(self, screen, camera):
        # Draw Trail first (so it's under the car)
        if len(self.trail) > 1 and self.alive:
            adjusted_trail = [camera.apply_point(p) for p in self.trail]
            color = COL_CAR_LEADER if self.is_leader else COL_CAR_NORM
            pygame.draw.lines(screen, color, False, adjusted_trail, 2)

        # Draw Car
        self.draw_sprite()
        rotated_image = pygame.transform.rotate(self.image, self.angle)
        # Fix center offset after rotation
        new_rect = rotated_image.get_rect(center=self.image.get_rect(center=(self.x, self.y)).center)
        screen.blit(rotated_image, camera.apply(new_rect).topleft)
        
        # Draw Sensors (Only for Leader to reduce clutter)
        if self.is_leader and self.alive:
            for radar in self.radars:
                pos, dist = radar
                pygame.draw.line(screen, (0, 255, 65, 80), camera.apply_point(self.rect.center), camera.apply_point(pos), 1)
                pygame.draw.circle(screen, (0, 255, 65), camera.apply_point(pos), 3)

class TrackGenerator:
    def __init__(self, seed):
        np.random.seed(seed)
        
    def generate_track(self):
        # 1. Create a massive surface (World)
        track_surface = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        track_surface.fill((0, 0, 0)) # Walls are 0 (Black)
        
        # 2. Draw random spline loop
        n_points = 14
        points = []
        for i in range(n_points):
            angle = (i / n_points) * 2 * math.pi
            radius = np.random.randint(800, 1800) # Huge radius
            x = WORLD_SIZE // 2 + radius * math.cos(angle)
            y = WORLD_SIZE // 2 + radius * math.sin(angle)
            points.append((x, y))
        points.append(points[0]) # Close loop
        
        # Smooth it
        pts = np.array(points)
        tck, u = splprep(pts.T, u=None, s=0.0, per=1)
        u_new = np.linspace(u.min(), u.max(), 2000)
        x_new, y_new = splev(u_new, tck, der=0)
        smooth_points = list(zip(x_new, y_new))

        # 3. Draw The "Drivable" Road (White = Safe)
        # We draw a wide white line. The AI sees white as safe, black as death.
        pygame.draw.lines(track_surface, (255, 255, 255), True, smooth_points, 350) 
        
        # 4. Generate the "Visual" Map (Pretty colors for the user)
        visual_surface = pygame.Surface((WORLD_SIZE, WORLD_SIZE))
        visual_surface.fill(COL_BG)
        
        # Draw Grid
        for x in range(0, WORLD_SIZE, 200):
            pygame.draw.line(visual_surface, COL_GRID, (x, 0), (x, WORLD_SIZE))
        for y in range(0, WORLD_SIZE, 200):
            pygame.draw.line(visual_surface, COL_GRID, (0, y), (WORLD_SIZE, y))

        # Draw Road
        pygame.draw.lines(visual_surface, COL_TRACK, True, smooth_points, 340)
        # Draw Neon Edges
        pygame.draw.lines(visual_surface, COL_WALL, True, smooth_points, 355) # Outer
        pygame.draw.lines(visual_surface, COL_TRACK, True, smooth_points, 335) # Inner Cut

        return (int(x_new[0]), int(y_new[0])), track_surface, visual_surface
