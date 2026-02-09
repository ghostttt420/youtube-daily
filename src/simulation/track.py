"""Procedural track generation."""

import math

import numpy as np
import pygame
from scipy.interpolate import splev, splprep

from __future__ import annotations

from src.constants import Visuals
from src.config import get_daily_theme
from src.config.themes import ColorScheme


class TrackGenerator:
    """Generates procedural racing tracks using spline interpolation."""

    def __init__(self, seed: int | None = None) -> None:
        """Initialize with random seed.
        
        Args:
            seed: Random seed for reproducible tracks
        """
        if seed is not None:
            np.random.seed(seed)
        self.seed = seed

    def generate_track(
        self,
        world_size: int = Visuals.DEFAULT_WORLD_SIZE,
    ) -> tuple[
        tuple[int, int],  # start position
        pygame.Surface,   # physics surface (collision mask)
        pygame.Surface,   # visual surface (rendered track)
        list[tuple[float, float]],  # checkpoints
        float,            # start angle
    ]:
        """Generate a complete racing track.
        
        Args:
            world_size: Size of the world square
            
        Returns:
            Tuple of (start_pos, physics_surface, visual_surface, checkpoints, start_angle)
        """
        theme = get_daily_theme()
        colors = theme.visuals if theme else self._default_colors()
        
        # Create surfaces
        phys_surf = pygame.Surface((world_size, world_size))
        vis_surf = pygame.Surface((world_size, world_size))
        
        # Fill backgrounds
        phys_surf.fill((0, 0, 0))  # Black = off-track for physics
        vis_surf.fill(colors["bg"] if isinstance(colors, dict) else colors.bg)
        
        # Generate control points in a circle
        points = self._generate_control_points(world_size)
        points.append(points[0])  # Close the loop
        
        # Create smooth spline
        smooth_points = self._create_spline(points)
        checkpoints = smooth_points[::Visuals.CHECKPOINT_INTERVAL]
        
        # Draw physics track (simplified, thicker)
        pygame.draw.lines(
            phys_surf,
            (255, 255, 255),  # White = on-track
            True,
            smooth_points,
            Visuals.ROAD_WIDTH,
        )
        
        # Draw visual track
        self._draw_visual_track(vis_surf, smooth_points, colors)
        
        # Calculate start angle
        start_angle = math.degrees(
            math.atan2(
                smooth_points[5][1] - smooth_points[0][1],
                smooth_points[5][0] - smooth_points[0][0],
            )
        )
        
        return (
            (int(smooth_points[0][0]), int(smooth_points[0][1])),
            phys_surf,
            vis_surf,
            checkpoints,
            start_angle,
        )

    def _generate_control_points(
        self,
        world_size: int,
        num_points: int = Visuals.TRACK_POINTS,
    ) -> list[tuple[float, float]]:
        """Generate random control points in a rough circle.
        
        Args:
            world_size: Size of world
            num_points: Number of control points
            
        Returns:
            List of (x, y) control points
        """
        points = []
        center = world_size // 2
        for i in range(num_points):
            angle = (i / num_points) * 2 * math.pi
            radius = np.random.randint(
                Visuals.TRACK_RADIUS_MIN,
                Visuals.TRACK_RADIUS_MAX,
            )
            x = center + radius * math.cos(angle)
            y = center + radius * math.sin(angle)
            points.append((x, y))
        return points

    def _create_spline(
        self,
        points: list[tuple[float, float]],
        num_samples: int = Visuals.TRACK_SMOOTHING,
    ) -> list[tuple[float, float]]:
        """Create smooth spline from control points.
        
        Args:
            points: Control points
            num_samples: Number of points to sample on spline
            
        Returns:
            List of smoothed points
        """
        pts = np.array(points)
        tck, u = splprep(pts.T, u=None, s=0.0, per=1)
        u_new = np.linspace(u.min(), u.max(), num_samples)
        x_new, y_new = splev(u_new, tck, der=0)
        return list(zip(x_new, y_new))

    def _draw_visual_track(
        self,
        surface: pygame.Surface,
        points: list[tuple[float, float]],
        colors: dict | ColorScheme,
    ) -> None:
        """Draw the visual track with walls, kerbs, and center line.
        
        Args:
            surface: Surface to draw on
            points: Track centerline points
            colors: Color scheme
        """
        # Extract colors
        if isinstance(colors, dict):
            wall_color = colors["wall"]
            edge_color = (220, 220, 220)
            road_color = colors["road"]
            center_color = colors["center"]
        else:
            wall_color = colors.wall
            edge_color = (220, 220, 220)
            road_color = colors.road
            center_color = colors.center
        
        # Sample points for brush drawing
        brush_points = points[::10]
        
        # Base layers (continuous for no gaps)
        for p in brush_points:
            pygame.draw.circle(surface, wall_color, (int(p[0]), int(p[1])), Visuals.WALL_WIDTH)
        for p in brush_points:
            pygame.draw.circle(surface, edge_color, (int(p[0]), int(p[1])), Visuals.EDGE_WIDTH)
        for p in brush_points:
            pygame.draw.circle(surface, road_color, (int(p[0]), int(p[1])), Visuals.ASPHALT_WIDTH)
        
        # Kerbs (red/white alternating)
        self._draw_kerbs(surface, points, wall_color)
        
        # Center line (dashed)
        self._draw_center_line(surface, points, center_color)

    def _draw_kerbs(
        self,
        surface: pygame.Surface,
        points: list[tuple[float, float]],
        wall_color: tuple[int, int, int],
    ) -> None:
        """Draw alternating red/white kerb segments.
        
        Args:
            surface: Surface to draw on
            points: Track points
            wall_color: Base wall color (red used for kerbs)
        """
        seg_len = Visuals.KERB_SEGMENT_LENGTH
        
        for i in range(0, len(points) - seg_len, seg_len * 2):
            # Red segment
            red_start = i
            red_end = min(i + seg_len, len(points) - 1)
            red_seg = points[red_start:red_end]
            if len(red_seg) > 1:
                pygame.draw.lines(
                    surface,
                    wall_color,
                    False,
                    red_seg,
                    Visuals.KERB_WIDTH,
                )
            
            # White segment
            white_start = i + seg_len
            white_end = min(white_start + seg_len, len(points) - 1)
            white_seg = points[white_start:white_end]
            if len(white_seg) > 1:
                pygame.draw.lines(
                    surface,
                    (255, 255, 255),
                    False,
                    white_seg,
                    Visuals.KERB_WIDTH,
                )

    def _draw_center_line(
        self,
        surface: pygame.Surface,
        points: list[tuple[float, float]],
        color: tuple[int, int, int],
    ) -> None:
        """Draw dashed center line.
        
        Args:
            surface: Surface to draw on
            points: Track points
            color: Line color
        """
        dash = Visuals.DASH_LENGTH
        gap = Visuals.DASH_GAP
        
        for i in range(0, len(points) - dash, dash + gap):
            start_idx = i
            end_idx = min(i + dash, len(points) - 1)
            dash_seg = points[start_idx:end_idx]
            if len(dash_seg) > 1:
                pygame.draw.lines(
                    surface,
                    color,
                    False,
                    dash_seg,
                    Visuals.DASH_WIDTH,
                )

    def _default_colors(self) -> dict:
        """Get default colors if theme unavailable."""
        return {
            "bg": (30, 35, 30),
            "road": (50, 50, 55),
            "wall": (200, 0, 0),
            "center": (80, 80, 80),
        }
