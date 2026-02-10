"""Ghost car system for racing against previous best."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from src.config import get_settings

if TYPE_CHECKING:
    from src.simulation.car import Car
    from src.simulation.camera import Camera


@dataclass
class GhostFrame:
    """Single frame of ghost data."""
    frame: int
    x: float
    y: float
    angle: float
    speed: float


class GhostRecorder:
    """Records car trajectory for ghost replay."""

    def __init__(self) -> None:
        """Initialize recorder."""
        self.frames: list[GhostFrame] = []
        self.is_recording = False

    def start(self) -> None:
        """Start recording."""
        self.frames = []
        self.is_recording = True

    def record(self, car: Car, frame: int) -> None:
        """Record a frame."""
        if not self.is_recording:
            return
        
        self.frames.append(GhostFrame(
            frame=frame,
            x=car.position.x,
            y=car.position.y,
            angle=car.angle,
            speed=car.velocity.length(),
        ))

    def stop(self) -> list[GhostFrame]:
        """Stop recording and return frames."""
        self.is_recording = False
        return self.frames.copy()

    def save(self, generation: int, fitness: float) -> Path:
        """Save ghost data to file."""
        settings = get_settings()
        ghost_dir = settings.paths.data_dir / "ghosts"
        ghost_dir.mkdir(parents=True, exist_ok=True)
        
        path = ghost_dir / f"ghost_gen_{generation:05d}.json"
        
        data = {
            "generation": generation,
            "fitness": fitness,
            "frame_count": len(self.frames),
            "frames": [
                {
                    "frame": f.frame,
                    "x": f.x,
                    "y": f.y,
                    "angle": f.angle,
                    "speed": f.speed,
                }
                for f in self.frames
            ],
        }
        
        with open(path, "w") as f:
            json.dump(data, f)
        
        return path

    @staticmethod
    def load(generation: int) -> list[GhostFrame] | None:
        """Load ghost data from file."""
        settings = get_settings()
        path = settings.paths.data_dir / "ghosts" / f"ghost_gen_{generation:05d}.json"
        
        if not path.exists():
            return None
        
        with open(path) as f:
            data = json.load(f)
        
        return [
            GhostFrame(
                frame=f["frame"],
                x=f["x"],
                y=f["y"],
                angle=f["angle"],
                speed=f["speed"],
            )
            for f in data["frames"]
        ]

    @staticmethod
    def find_best_ghost(max_generation: int | None = None) -> tuple[int, list[GhostFrame]] | None:
        """Find the best ghost up to given generation."""
        settings = get_settings()
        ghost_dir = settings.paths.data_dir / "ghosts"
        
        if not ghost_dir.exists():
            return None
        
        best_fitness = -1
        best_gen = -1
        best_frames = None
        
        for path in ghost_dir.glob("ghost_gen_*.json"):
            gen = int(path.stem.split("_")[2])
            if max_generation and gen > max_generation:
                continue
            
            with open(path) as f:
                data = json.load(f)
            
            if data["fitness"] > best_fitness:
                best_fitness = data["fitness"]
                best_gen = gen
                best_frames = [
                    GhostFrame(
                        frame=f["frame"],
                        x=f["x"],
                        y=f["y"],
                        angle=f["angle"],
                        speed=f["speed"],
                    )
                    for f in data["frames"]
                ]
        
        return (best_gen, best_frames) if best_frames else None


class GhostCar:
    """Ghost car for racing against previous best."""

    def __init__(self, frames: list[GhostFrame]) -> None:
        """Initialize ghost with recorded frames."""
        self.frames = frames
        self.current_frame = 0
        self.finished = False
        
        # Visual
        self.color = (255, 255, 0, 128)  # Semi-transparent yellow
        self.size = (40, 70)
        
        # Pre-render ghost surface
        self._surface: pygame.Surface | None = None

    def update(self) -> None:
        """Advance to next frame."""
        self.current_frame += 1
        if self.current_frame >= len(self.frames):
            self.finished = True

    def get_position(self) -> tuple[float, float] | None:
        """Get current position."""
        if self.finished or self.current_frame >= len(self.frames):
            return None
        frame = self.frames[self.current_frame]
        return (frame.x, frame.y)

    def get_angle(self) -> float:
        """Get current angle."""
        if self.finished or self.current_frame >= len(self.frames):
            return 0.0
        return self.frames[self.current_frame].angle

    def draw(self, screen: pygame.Surface, camera: Camera) -> None:
        """Draw ghost car."""
        if self.finished:
            return
        
        pos = self.get_position()
        if not pos:
            return
        
        draw_pos = camera.apply_point(pos)
        
        # Draw semi-transparent ghost
        if self._surface is None:
            self._create_surface()
        
        if self._surface:
            rotated = pygame.transform.rotate(self._surface, -self.get_angle() - 90)
            rect = rotated.get_rect(center=draw_pos)
            screen.blit(rotated, rect.topleft)
        else:
            # Fallback
            pygame.draw.circle(screen, (255, 255, 0), draw_pos, 20)

    def _create_surface(self) -> None:
        """Create semi-transparent ghost surface."""
        try:
            surf = pygame.Surface(self.size, pygame.SRCALPHA)
            
            # Ghost body - semi-transparent
            body_color = (255, 255, 0, 100)
            pygame.draw.ellipse(surf, body_color, (5, 5, self.size[0]-10, self.size[1]-10))
            
            # Ghost outline
            pygame.draw.ellipse(surf, (255, 255, 0, 180), (5, 5, self.size[0]-10, self.size[1]-10), 2)
            
            self._surface = surf
        except Exception:
            self._surface = None

    def get_progress(self) -> float:
        """Get progress through recording (0-1)."""
        if not self.frames:
            return 1.0
        return self.current_frame / len(self.frames)

    def reset(self) -> None:
        """Reset to start."""
        self.current_frame = 0
        self.finished = False
