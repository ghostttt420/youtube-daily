import pygame
import math
import numpy as np
from scipy.interpolate import splprep, splev
import os

# --- CONFIGURATION ---
WIDTH, HEIGHT = 1080, 1920  # YouTube Shorts Resolution
CAR_SIZE = 25
SENSOR_LENGTH = 200
BG_COLOR = (10, 10, 10)     # Deep Dark Grey (Not pure black, looks better)
TRACK_COLOR = (40, 40, 40)
WALL_COLOR = (0, 255, 65)   # Neon Green Walls
CAR_COLOR = (255, 0, 100)   # Neon Pink Car
FPS = 60

class Car:
    def __init__(self, start_pos, angle=0):
        self.x, self.y = start_pos
        self.angle = angle
        self.speed = 0
        self.radars = []
        self.alive = True
        self.distance_traveled = 0
        
        # Load/Create Car Image
        self.original_image = pygame.Surface((CAR_SIZE, CAR_SIZE), pygame.SRCALPHA)
        # Draw a cool Neon Triangle
        pygame.draw.polygon(self.original_image, CAR_COLOR, 
                          [(CAR_SIZE, CAR_SIZE//2), (0, 0), (0, CAR_SIZE)])
        self.image = self.original_image
        self.rect = self.image.get_rect(center=(self.x, self.y))

    def update(self, map_mask):
        if not self.alive: return

        # Simple Physics
        self.x += math.cos(math.radians(360 - self.angle)) * self.speed
        self.y += math.sin(math.radians(360 - self.angle)) * self.speed
        
        # Collision Detection (Pixel Perfect)
        # We check if the center of the car touches the "Black" void of the mask
        try:
            if map_mask.get_at((int(self.x), int(self.y))) == (0, 0, 0, 255):
                self.alive = False
        except IndexError:
            self.alive = False # Went off screen

        self.distance_traveled += self.speed
        self.rect.center = (int(self.x), int(self.y))
        self.check_radar(map_mask)

    def rotate(self, left=False, right=False):
        if left: self.angle += 3
        if right: self.angle -= 3

    def check_radar(self, map_mask):
        self.radars.clear()
        # Cast 5 rays: -90, -45, 0, 45, 90 degrees
        for degree in [-90, -45, 0, 45, 90]:
            self.cast_ray(degree, map_mask)

    def cast_ray(self, degree, map_mask):
        length = 0
        x = int(self.rect.center[0] + math.cos(math.radians(360 - (self.angle + degree))) * length)
        y = int(self.rect.center[1] + math.sin(math.radians(360 - (self.angle + degree))) * length)

        # Extend ray until it hits a wall or max length
        while length < SENSOR_LENGTH:
            try:
                if map_mask.get_at((x, y)) == (0, 0, 0, 255): # Hit Wall (Black)
                    break
            except IndexError:
                break
                
            length += 1
            x = int(self.rect.center[0] + math.cos(math.radians(360 - (self.angle + degree))) * length)
            y = int(self.rect.center[1] + math.sin(math.radians(360 - (self.angle + degree))) * length)

        # Store (Position, Distance)
        dist = int(math.sqrt(math.pow(x - self.rect.center[0], 2) + math.pow(y - self.rect.center[1], 2)))
        self.radars.append([(x, y), dist])

    def draw(self, screen):
        # Rotate image
        rotated_image = pygame.transform.rotate(self.original_image, self.angle)
        new_rect = rotated_image.get_rect(center=self.image.get_rect(center=(self.x, self.y)).center)
        screen.blit(rotated_image, new_rect.topleft)
        
        # Draw Sensors (The "AI Vision") - Visual Candy
        for radar in self.radars:
            position, dist = radar
            pygame.draw.line(screen, (0, 255, 0, 100), self.rect.center, position, 1)
            pygame.draw.circle(screen, (0, 255, 0), position, 3)

class TrackGenerator:
    def __init__(self, seed):
        np.random.seed(seed)
        
    def generate_track(self, screen):
        """Generates a random organic loop using Splines"""
        screen.fill((0, 0, 0)) # Fill Black (Walls)
        
        # Generate random points in a circle
        n_points = 8
        margin = 200
        points = []
        for i in range(n_points):
            angle = (i / n_points) * 2 * math.pi
            # Randomize radius to make it squiggly
            radius = np.random.randint(300, 450) 
            x = WIDTH // 2 + radius * math.cos(angle)
            y = HEIGHT // 2 + radius * math.sin(angle)
            points.append((x, y))
        
        # Close the loop
        points.append(points[0])
        points = np.array(points)

        # Smooth curve (Spline Interpolation)
        tck, u = splprep(points.T, u=None, s=0.0, per=1)
        u_new = np.linspace(u.min(), u.max(), 1000)
        x_new, y_new = splev(u_new, tck, der=0)

        # Draw the "Drivable" area (White) on Black background
        track_surface = pygame.Surface((WIDTH, HEIGHT))
        track_surface.fill((0, 0, 0))
        
        smooth_points = list(zip(x_new, y_new))
        # Draw thick line for track
        pygame.draw.lines(track_surface, (255, 255, 255), True, smooth_points, 180)
        
        # Blit track onto screen
        screen.blit(track_surface, (0, 0))
        
        # Return the start position (First point of spline)
        return (int(x_new[0]), int(y_new[0])), track_surface

# --- TESTER ---
if __name__ == "__main__":
    # Setup for Headless (Server) or GUI
    os.environ["SDL_VIDEODRIVER"] = "dummy" # Remove this line to see it on your PC
    
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    
    # 1. Generate Map (Seed 42)
    generator = TrackGenerator(seed=42)
    start_pos, track_surface = generator.generate_track(screen)
    
    # Create Mask for Collision (White = Safe, Black = Wall)
    map_mask = pygame.mask.from_surface(track_surface)
    # Invert mask so Black is solid (collision)
    map_mask.invert()

    # 2. Spawn Car
    car = Car(start_pos)
    car.speed = 5
    
    # 3. Game Loop (Simulation)
    clock = pygame.time.Clock()
    for i in range(100): # Run 100 frames
        screen.fill(BG_COLOR)
        
        # Draw Track
        # We perform a "Color Key" trick: White pixels become Track Color
        temp_track = track_surface.copy()
        temp_track.set_colorkey((0, 0, 0)) # Make black transparent
        
        # Draw Neon Borders
        pygame.draw.lines(screen, WALL_COLOR, True, list(zip(*[
            [int(p[0]) for p in generator.points], # This is pseudo-code for outline
            # Actually, proper outline requires edge detection, 
            # for now, we just draw the grey road.
        ])), 5)
        
        # Simple Blit for now
        pygame.draw.rect(screen, TRACK_COLOR, (0,0,WIDTH,HEIGHT)) # Base
        screen.blit(track_surface, (0,0)) # This is the white road

        # Update Car
        # AI INPUT WOULD GO HERE (e.g., car.rotate(left=True))
        car.update(track_surface) # Pass surface for color detection
        car.draw(screen)
        
        pygame.display.flip()
        clock.tick(FPS)
        
        if i % 10 == 0:
            print(f"Frame {i}: Car at {car.x:.1f}, {car.y:.1f} | Alive: {car.alive}")

    pygame.quit()
