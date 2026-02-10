"""Car physics and behavior."""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from src.constants import Fitness, Physics, Sensors

if TYPE_CHECKING:
    from pygame.math import Vector2


class Car:
    """A car in the racing simulation.
    
    Attributes:
        position: Current position vector
        velocity: Current velocity vector
        angle: Current heading in degrees
        alive: Whether the car is still in the simulation
        distance_traveled: Total distance traveled
        gates_passed: Number of checkpoints passed
        next_gate_idx: Index of next checkpoint to reach
        frames_since_gate: Frames since last checkpoint (for timeout)
        is_leader: Whether this is the current leader
        radars: List of (endpoint, distance) tuples for sensor rays
        particles: Active particle effects (position, lifetime)
    """

    def __init__(
        self,
        start_pos: tuple[float, float],
        start_angle: float,
        friction: float = Physics.DEFAULT_FRICTION,
        max_speed: float = Physics.DEFAULT_MAX_SPEED,
        acceleration_rate: float = Physics.DEFAULT_ACCELERATION,
        turn_speed: float = Physics.DEFAULT_TURN_SPEED,
    ) -> None:
        """Initialize a car at the given position and angle.
        
        Args:
            start_pos: Initial (x, y) position
            start_angle: Initial heading in degrees
            friction: Velocity decay factor per frame
            max_speed: Maximum speed cap
            acceleration_rate: Acceleration per gas input
            turn_speed: Turning rate multiplier
        """
        self.position = pygame.math.Vector2(start_pos)
        self.velocity = pygame.math.Vector2(0, 0)
        self.angle = start_angle
        self.acceleration = 0.0
        self.steering = 0.0
        
        self.max_speed = max_speed
        self.friction = friction
        self.acceleration_rate = acceleration_rate
        self.turn_speed = turn_speed
        
        self.alive = True
        self.distance_traveled = 0.0
        self.is_leader = False
        self.gates_passed = 0
        self.next_gate_idx = 0
        self.frames_since_gate = 0
        
        self.radars: list[tuple[tuple[int, int], float]] = []
        self.particles: list[list] = []  # [position, lifetime]
        
        # Visuals (loaded externally)
        self.sprite_norm: pygame.Surface | None = None
        self.sprite_leader: pygame.Surface | None = None
        self.img_smoke: pygame.Surface | None = None
        self.rect = pygame.Rect(0, 0, 50, 85)
        self.rect.center = (int(self.position.x), int(self.position.y))
    
    def load_sprites(self, assets_dir: Path | str = "assets") -> None:
        """Load car sprites from assets directory.
        
        Args:
            assets_dir: Directory containing sprite files
        """
        assets_path = Path(assets_dir)
        
        def load_sprite(filename: str, scale_size: tuple[int, int] | None = None) -> pygame.Surface | None:
            """Load a sprite image."""
            path = assets_path / filename
            if not path.exists():
                return None
            try:
                img = pygame.image.load(str(path)).convert_alpha()
                if scale_size:
                    img = pygame.transform.scale(img, scale_size)
                return img
            except Exception:
                return None
        
        self.sprite_norm = load_sprite("car_normal.png", (50, 85))
        self.sprite_leader = load_sprite("car_leader.png", (50, 85))
        self.img_smoke = load_sprite("particle_smoke.png", (32, 32))
        
        # Update rect if sprite loaded
        if self.sprite_norm:
            self.rect = self.sprite_norm.get_rect(center=self.position)

    def get_data(self, checkpoints: list[tuple[float, float]]) -> list[float]:
        """Get AI inputs for target direction and distance.
        
        Args:
            checkpoints: List of checkpoint positions
            
        Returns:
            [heading_normalized, distance_normalized] where
            heading is -1 to 1 (left to right) and distance is 0 to 1
        """
        if not self.alive:
            return [0.0, 0.0]
        
        if not checkpoints:
            return [0.0, 1.0]
        
        target_idx = self.next_gate_idx % len(checkpoints)
        target_pos = pygame.math.Vector2(checkpoints[target_idx])
        
        dx = target_pos.x - self.position.x
        dy = target_pos.y - self.position.y
        target_rad = math.atan2(dy, dx)
        car_rad = math.radians(self.angle)
        
        # Normalize angle difference to [-pi, pi]
        diff = target_rad - car_rad
        while diff > math.pi:
            diff -= 2 * math.pi
        while diff < -math.pi:
            diff += 2 * math.pi
        
        heading_input = diff / math.pi
        dist = self.position.distance_to(target_pos)
        dist_input = min(dist / 1000.0, 1.0)
        
        return [heading_input, dist_input]

    def input_steer(self, left: bool = False, right: bool = False) -> None:
        """Set steering input.
        
        Args:
            left: Steer left
            right: Steer right
        """
        if left:
            self.steering = -1.0
        if right:
            self.steering = 1.0

    def input_gas(self) -> None:
        """Apply acceleration."""
        self.acceleration = self.acceleration_rate

    def check_gates(self, checkpoints: list[tuple[float, float]]) -> bool:
        """Check if car has reached the next checkpoint.
        
        Args:
            checkpoints: List of checkpoint positions
            
        Returns:
            True if checkpoint was passed
        """
        if not self.alive or not checkpoints:
            return False
        
        target_idx = self.next_gate_idx % len(checkpoints)
        target_pos = pygame.math.Vector2(checkpoints[target_idx])
        distance = self.position.distance_to(target_pos)
        
        if distance < 300:  # Checkpoint radius
            self.gates_passed += 1
            self.next_gate_idx += 1
            self.frames_since_gate = 0
            return True
        return False

    def update(self, map_mask: pygame.mask.Mask) -> None:
        """Update physics for one frame.
        
        Args:
            map_mask: Collision mask of the track
        """
        if not self.alive:
            return
        
        self.frames_since_gate += 1
        if self.frames_since_gate > Fitness.MAX_FRAMES_WITHOUT_GATE:
            self.alive = False
            return

        # Apply friction and acceleration
        self.velocity *= self.friction
        rad = math.radians(self.angle)
        self.velocity += pygame.math.Vector2(
            math.cos(rad), math.sin(rad)
        ) * self.acceleration

        # Clamp speed
        if self.velocity.length() > self.max_speed:
            self.velocity.scale_to_length(self.max_speed)
        
        # Apply steering proportional to speed
        if self.velocity.length() > 2:
            self.angle += self.steering * self.velocity.length() * self.turn_speed
            
            # Generate particles when turning hard at speed
            if abs(self.steering) > 0.5 and self.velocity.length() > 15:
                if random.random() < 0.3:
                    offset = pygame.math.Vector2(-20, 0).rotate(self.angle)
                    self.particles.append([self.position + offset, 20])

        # Update position
        self.position += self.velocity
        self.distance_traveled += self.velocity.length()
        
        self.rect.center = (int(self.position.x), int(self.position.y))
        self.acceleration = 0.0
        self.steering = 0.0
        
        # Check collision with track
        try:
            if map_mask.get_at((int(self.position.x), int(self.position.y))) == 0:
                self.alive = False
        except IndexError:
            self.alive = False

    def check_radar(self, map_mask: pygame.mask.Mask) -> None:
        """Cast sensor rays and store distances.
        
        Args:
            map_mask: Collision mask of the track
        """
        self.radars.clear()
        for degree in Sensors.RAY_ANGLES:
            self._cast_ray(degree, map_mask)

    def _cast_ray(self, degree: float, map_mask: pygame.mask.Mask) -> None:
        """Cast a single sensor ray.
        
        Args:
            degree: Angle offset from car heading
            map_mask: Collision mask of the track
        """
        length = 0.0
        rad = math.radians(self.angle + degree)
        vec = pygame.math.Vector2(math.cos(rad), math.sin(rad))
        center = self.position
        
        while length < Sensors.DEFAULT_LENGTH:
            length += Sensors.RAY_STEP
            check = center + vec * length
            try:
                if map_mask.get_at((int(check.x), int(check.y))) == 0:
                    break
            except IndexError:
                break
        
        self.radars.append(((int(check.x), int(check.y)), length))

    def handle_car_collision(self, other_cars: list[Car]) -> None:
        """Handle collisions with other cars.
        
        Cars bounce off each other without dying.
        
        Args:
            other_cars: List of other car instances
        """
        if not self.alive:
            return
            
        for other in other_cars:
            if other is self or not other.alive:
                continue
            if self.rect.colliderect(other.rect):
                # Push cars apart
                push_vec = self.position - other.position
                if push_vec.length() > 0:
                    push_vec = push_vec.normalize() * Physics.CAR_COLLISION_PUSH
                    self.position += push_vec
                    other.position -= push_vec
                    # Bounce velocities
                    self.velocity *= -Physics.CAR_COLLISION_BOUNCE
                    other.velocity *= -Physics.CAR_COLLISION_BOUNCE

    def draw(
        self,
        screen: pygame.Surface,
        camera: "Camera",
    ) -> None:
        """Draw the car and its particles.
        
        Args:
            screen: Surface to draw on
            camera: Camera for coordinate transformation
        """
        if not self.alive:
            return
        
        # Select sprite
        if self.is_leader and self.sprite_leader:
            img = self.sprite_leader
        elif self.sprite_norm:
            img = self.sprite_norm
        else:
            # Fallback rectangle
            pygame.draw.rect(screen, (255, 0, 0), self.rect)
            return
        
        # Rotate and draw car
        rotated_img = pygame.transform.rotate(img, -self.angle - 90)
        draw_pos = camera.apply_point(self.position)
        rect = rotated_img.get_rect(center=draw_pos)
        screen.blit(rotated_img, rect.topleft)
        
        # Draw particles
        if self.img_smoke:
            for i in range(len(self.particles) - 1, -1, -1):
                pos, life = self.particles[i]
                life -= 1
                self.particles[i][1] = life
                if life <= 0:
                    self.particles.pop(i)
                else:
                    adj = camera.apply_point(pos)
                    s = self.img_smoke.copy()
                    s.set_alpha(int((life / 20) * 150))
                    screen.blit(s, (adj[0] - 16, adj[1] - 16))
