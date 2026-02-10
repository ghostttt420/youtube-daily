"""Telemetry overlay for video rendering."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from src.simulation.car import Car
    from src.simulation.camera import Camera


class TelemetryOverlay:
    """Renders real-time telemetry on screen."""

    def __init__(self) -> None:
        """Initialize telemetry overlay."""
        self.font_large = None
        self.font_medium = None
        self.font_small = None
        self._initialized = False

    def _init_fonts(self) -> None:
        """Initialize fonts (call after pygame.init)."""
        if self._initialized:
            return
        
        try:
            self.font_large = pygame.font.SysFont("consolas", 36, bold=True)
            self.font_medium = pygame.font.SysFont("consolas", 24, bold=True)
            self.font_small = pygame.font.SysFont("consolas", 16)
            self._initialized = True
        except Exception:
            # Fallback if fonts not available
            self.font_large = pygame.font.Font(None, 36)
            self.font_medium = pygame.font.Font(None, 24)
            self.font_small = pygame.font.Font(None, 16)

    def draw(
        self,
        screen: pygame.Surface,
        car: Car,
        generation: int,
        weather_name: str = "",
        curriculum_level: str = "",
    ) -> None:
        """Draw telemetry overlay on screen."""
        self._init_fonts()
        
        # Background panel
        panel_rect = pygame.Rect(10, 10, 280, 180)
        s = pygame.Surface((panel_rect.width, panel_rect.height), pygame.SRCALPHA)
        s.fill((0, 0, 0, 160))
        screen.blit(s, panel_rect.topleft)
        
        # Border
        pygame.draw.rect(screen, (100, 100, 100), panel_rect, 2)
        
        y = 20
        
        # Generation
        gen_text = self.font_large.render(f"GEN {generation}", True, (255, 100, 100))
        screen.blit(gen_text, (20, y))
        y += 40
        
        # Speed
        speed = car.velocity.length() if car.velocity else 0
        speed_kmh = int(speed * 3.6)  # Convert to km/h approx
        speed_text = self.font_medium.render(f"SPEED: {speed_kmh} km/h", True, (255, 255, 255))
        screen.blit(speed_text, (20, y))
        y += 30
        
        # Gates
        gates_text = self.font_medium.render(f"GATES: {car.gates_passed}", True, (100, 255, 100))
        screen.blit(gates_text, (20, y))
        y += 30
        
        # Distance
        dist_text = self.font_small.render(f"DIST: {int(car.distance_traveled)}m", True, (200, 200, 200))
        screen.blit(dist_text, (20, y))
        y += 25
        
        # Weather/Environment
        if weather_name:
            weather_text = self.font_small.render(f"WEATHER: {weather_name}", True, (100, 200, 255))
            screen.blit(weather_text, (20, y))
            y += 20
        
        if curriculum_level:
            curr_text = self.font_small.render(f"LEVEL: {curriculum_level}", True, (255, 200, 100))
            screen.blit(curr_text, (20, y))

    def draw_sensor_rays(
        self,
        screen: pygame.Surface,
        car: Car,
        camera: Camera,
    ) -> None:
        """Draw visual sensor rays."""
        if not car.radars:
            return
        
        car_pos = camera.apply_point(car.position)
        
        for i, (endpoint, distance) in enumerate(car.radars):
            end_pos = camera.apply_point(endpoint)
            
            # Color based on distance
            ratio = distance / 300.0
            if ratio < 0.3:
                color = (255, 50, 50)  # Red - close
            elif ratio < 0.6:
                color = (255, 255, 50)  # Yellow - medium
            else:
                color = (50, 255, 50)  # Green - far
            
            # Draw ray
            pygame.draw.line(screen, color, car_pos, end_pos, 2)
            
            # Draw endpoint
            pygame.draw.circle(screen, color, end_pos, 4)
            
            # Draw distance value
            if self.font_small:
                dist_text = self.font_small.render(f"{int(distance)}", True, color)
                screen.blit(dist_text, (end_pos[0] + 5, end_pos[1] - 10))

    def draw_minimap(
        self,
        screen: pygame.Surface,
        car: Car,
        checkpoints: list[tuple[float, float]],
        car_position_on_track: float = 0.0,
    ) -> None:
        """Draw mini track map."""
        # Mini map in bottom right
        map_size = 150
        map_x = screen.get_width() - map_size - 20
        map_y = screen.get_height() - map_size - 20
        
        # Background
        map_rect = pygame.Rect(map_x, map_y, map_size, map_size)
        s = pygame.Surface((map_size, map_size), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        screen.blit(s, map_rect.topleft)
        pygame.draw.rect(screen, (100, 100, 100), map_rect, 2)
        
        if len(checkpoints) < 2:
            return
        
        # Scale checkpoints to minimap
        world_size = 4000
        scale = map_size / world_size
        
        # Draw track
        points = [
            (map_x + int(cp[0] * scale), map_y + int(cp[1] * scale))
            for cp in checkpoints
        ]
        
        if len(points) > 1:
            pygame.draw.lines(screen, (80, 80, 80), True, points, 2)
        
        # Draw car position
        car_x = map_x + int(car.position.x * scale)
        car_y = map_y + int(car.position.y * scale)
        pygame.draw.circle(screen, (255, 255, 0), (car_x, car_y), 4)
        
        # Draw next checkpoint
        if car.next_gate_idx < len(checkpoints):
            next_cp = checkpoints[car.next_gate_idx]
            cp_x = map_x + int(next_cp[0] * scale)
            cp_y = map_y + int(next_cp[1] * scale)
            pygame.draw.circle(screen, (0, 255, 0), (cp_x, cp_y), 3)

    def draw_neural_activity(
        self,
        screen: pygame.Surface,
        inputs: list[float],
        outputs: list[float],
    ) -> None:
        """Draw simplified neural network activity."""
        # Neural viz in bottom left
        viz_width = 200
        viz_height = 120
        viz_x = 20
        viz_y = screen.get_height() - viz_height - 20
        
        # Background
        viz_rect = pygame.Rect(viz_x, viz_y, viz_width, viz_height)
        s = pygame.Surface((viz_width, viz_height), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        screen.blit(s, viz_rect.topleft)
        pygame.draw.rect(screen, (100, 100, 100), viz_rect, 2)
        
        # Title
        if self.font_small:
            title = self.font_small.render("NEURAL ACTIVITY", True, (200, 200, 200))
            screen.blit(title, (viz_x + 10, viz_y + 5))
        
        # Draw input bars (sensors)
        bar_height = 8
        bar_spacing = 2
        start_y = viz_y + 30
        
        for i, val in enumerate(inputs[:5]):  # First 5 are sensors
            bar_width = int(abs(val) * 60)
            color = (50, 255, 50) if val > 0 else (255, 50, 50)
            
            bar_rect = pygame.Rect(viz_x + 10, start_y + i * (bar_height + bar_spacing), bar_width, bar_height)
            pygame.draw.rect(screen, color, bar_rect)
        
        # Draw output bars (steering)
        output_start_x = viz_x + viz_width - 70
        
        for i, val in enumerate(outputs[:2]):
            bar_width = int(abs(val) * 60)
            color = (50, 150, 255) if val > 0 else (255, 150, 50)
            
            bar_rect = pygame.Rect(
                output_start_x,
                start_y + i * (bar_height + bar_spacing),
                bar_width,
                bar_height
            )
            pygame.draw.rect(screen, color, bar_rect)
            
            # Label
            if self.font_small:
                label = "STEER" if i == 0 else "GAS"
                text = self.font_small.render(label, True, (200, 200, 200))
                screen.blit(text, (output_start_x - 45, start_y + i * (bar_height + bar_spacing)))

    def draw_progress_bar(
        self,
        screen: pygame.Surface,
        progress: float,  # 0.0 to 1.0
        y_position: int | None = None,
    ) -> None:
        """Draw progress bar for ghost racing."""
        bar_width = 300
        bar_height = 10
        x = (screen.get_width() - bar_width) // 2
        y = y_position or (screen.get_height() - 50)
        
        # Background
        pygame.draw.rect(screen, (50, 50, 50), (x, y, bar_width, bar_height))
        
        # Progress
        fill_width = int(bar_width * progress)
        pygame.draw.rect(screen, (0, 255, 100), (x, y, fill_width, bar_height))
        
        # Border
        pygame.draw.rect(screen, (200, 200, 200), (x, y, bar_width, bar_height), 2)
        
        # Percentage text
        if self.font_small:
            pct_text = self.font_small.render(f"{int(progress * 100)}%", True, (255, 255, 255))
            screen.blit(pct_text, (x + bar_width + 10, y - 2))
