"""Camera system for viewport management."""

import pygame


class Camera:
    """A smooth-following camera for the simulation.
    
    Attributes:
        camera: The view rectangle
        width: World width
        height: World height
        exact_x: Float x position for smooth interpolation
        exact_y: Float y position for smooth interpolation
    """

    def __init__(self, world_width: int, world_height: int) -> None:
        """Initialize camera with world dimensions.
        
        Args:
            world_width: Total world width in pixels
            world_height: Total world height in pixels
        """
        self.camera = pygame.Rect(0, 0, world_width, world_height)
        self.width = world_width
        self.height = world_height
        self.exact_x = 0.0
        self.exact_y = 0.0
        self._viewport_width = 1080  # Default, updated via apply_point context
        self._viewport_height = 1920

    def set_viewport(self, width: int, height: int) -> None:
        """Set the viewport dimensions.
        
        Args:
            width: Viewport width
            height: Viewport height
        """
        self._viewport_width = width
        self._viewport_height = height

    def apply_point(self, pos: tuple[float, float]) -> tuple[int, int]:
        """Transform world coordinates to screen coordinates.
        
        Args:
            pos: (x, y) world position
            
        Returns:
            (x, y) screen position
        """
        return (
            int(pos[0] + self.exact_x),
            int(pos[1] + self.exact_y),
        )

    def update(self, target: "Car") -> None:  # type: ignore  # noqa: F821
        """Smoothly follow a target.
        
        Args:
            target: The car to follow
        """
        # Calculate target camera position (centered on target)
        target_x = -target.position.x + self._viewport_width / 2
        target_y = -target.position.y + self._viewport_height / 2
        
        # Clamp target to world bounds
        target_x = min(0, max(-(self.width - self._viewport_width), target_x))
        target_y = min(0, max(-(self.height - self._viewport_height), target_y))

        # Smooth interpolation
        lerp_factor = 0.3
        self.exact_x += (target_x - self.exact_x) * lerp_factor
        self.exact_y += (target_y - self.exact_y) * lerp_factor
        
        # CRITICAL: Clamp actual position to bounds after interpolation
        # This prevents the camera from showing empty space at world edges
        self.exact_x = min(0, max(-(self.width - self._viewport_width), self.exact_x))
        self.exact_y = min(0, max(-(self.height - self._viewport_height), self.exact_y))
        
        # Camera rect represents the viewport (what's visible on screen)
        self.camera = pygame.Rect(
            int(self.exact_x),
            int(self.exact_y),
            self._viewport_width,
            self._viewport_height,
        )
