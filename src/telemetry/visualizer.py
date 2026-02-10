"""Neural network visualization."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    import neat


class NeuralVisualizer:
    """Visualizes neural network topology and activation."""

    def __init__(self, network: neat.nn.FeedForwardNetwork | None = None) -> None:
        """Initialize neural visualizer."""
        self.network = network
        self.node_positions: dict[int, tuple[int, int]] = {}
        self.surface: pygame.Surface | None = None
        self.font: pygame.font.Font | None = None

    def set_network(self, network: neat.nn.FeedForwardNetwork) -> None:
        """Set the network to visualize."""
        self.network = network
        self._calculate_layout()

    def _calculate_layout(self) -> None:
        """Calculate node positions for visualization."""
        if not self.network:
            return
        
        # Simple layered layout
        # Input layer (7 nodes)
        # Hidden layer (variable)
        # Output layer (2 nodes)
        
        width, height = 300, 400
        margin = 40
        
        # Input layer positions (left)
        input_y_start = height // 2 - (7 * 30) // 2
        for i in range(7):
            self.node_positions[f"in_{i}"] = (margin, input_y_start + i * 30)
        
        # Output layer positions (right)
        output_y = height // 2
        self.node_positions["out_0"] = (width - margin, output_y - 20)
        self.node_positions["out_1"] = (width - margin, output_y + 20)

    def create_surface(self, width: int = 300, height: int = 400) -> pygame.Surface:
        """Create visualization surface."""
        if self.surface is None or self.surface.get_size() != (width, height):
            self.surface = pygame.Surface((width, height), pygame.SRCALPHA)
            self.font = pygame.font.Font(None, 20)
        
        return self.surface

    def draw(
        self,
        inputs: list[float],
        outputs: list[float],
        width: int = 300,
        height: int = 400,
    ) -> pygame.Surface:
        """Draw neural network visualization."""
        surface = self.create_surface(width, height)
        surface.fill((0, 0, 0, 200))
        
        if not self.font:
            self.font = pygame.font.Font(None, 20)
        
        # Background
        pygame.draw.rect(surface, (20, 20, 30), (0, 0, width, height))
        pygame.draw.rect(surface, (60, 60, 80), (0, 0, width, height), 3)
        
        # Title
        title = self.font.render("NEURAL NETWORK", True, (200, 200, 255))
        surface.blit(title, (width // 2 - title.get_width() // 2, 10))
        
        margin = 50
        layer_spacing = (width - 2 * margin) // 2
        
        # Input layer
        input_y_positions = []
        input_start_y = height // 2 - (len(inputs) * 25) // 2 + 20
        
        for i, val in enumerate(inputs):
            x = margin
            y = input_start_y + i * 25
            input_y_positions.append(y)
            
            # Node color based on activation
            intensity = int(abs(val) * 255)
            if val > 0:
                color = (0, intensity, 0)
            else:
                color = (intensity, 0, 0)
            
            # Draw node
            pygame.draw.circle(surface, color, (x, y), 8)
            pygame.draw.circle(surface, (200, 200, 200), (x, y), 8, 2)
            
            # Label
            if i < 5:
                label = f"S{i}"
            else:
                label = f"G{i-5}"
            text = self.font.render(label, True, (200, 200, 200))
            surface.blit(text, (x - 25, y - 6))
            
            # Value
            val_text = self.font.render(f"{val:.2f}", True, (150, 150, 150))
            surface.blit(val_text, (x + 12, y - 6))
        
        # Output layer
        output_y_positions = []
        output_start_y = height // 2 - (len(outputs) * 30) // 2 + 20
        
        for i, val in enumerate(outputs):
            x = width - margin
            y = output_start_y + i * 30
            output_y_positions.append(y)
            
            # Node color
            intensity = int(abs(val) * 255)
            if val > 0.5:
                color = (0, intensity, intensity)
            elif val < -0.5:
                color = (intensity, intensity, 0)
            else:
                color = (100, 100, 100)
            
            # Draw node
            pygame.draw.circle(surface, color, (x, y), 10)
            pygame.draw.circle(surface, (200, 200, 200), (x, y), 10, 2)
            
            # Label
            label = "STEER" if i == 0 else "GAS"
            text = self.font.render(label, True, (200, 200, 200))
            surface.blit(text, (x + 15, y - 6))
            
            # Value
            val_text = self.font.render(f"{val:.2f}", True, (150, 150, 150))
            surface.blit(val_text, (x - 35, y - 6))
        
        # Draw connections (simplified)
        # In a full implementation, we'd draw actual weights
        for in_y in input_y_positions:
            for out_y in output_y_positions:
                # Random-ish opacity based on positions
                alpha = 50 + ((in_y + out_y) % 50)
                color = (100, 100, 100, alpha)
                
                # Create line surface with alpha
                line_surf = pygame.Surface((width, height), pygame.SRCALPHA)
                pygame.draw.line(
                    line_surf,
                    color,
                    (margin + 8, in_y),
                    (width - margin - 8, out_y),
                    1
                )
                surface.blit(line_surf, (0, 0))
        
        return surface

    def draw_activation_heatmap(
        self,
        surface: pygame.Surface,
        position: tuple[int, int],
        size: tuple[int, int],
        inputs: list[float],
    ) -> None:
        """Draw activation heatmap."""
        x, y = position
        w, h = size
        
        # Background
        pygame.draw.rect(surface, (30, 30, 30), (x, y, w, h))
        
        if len(inputs) < 5:
            return
        
        # Draw sensor bars
        bar_width = w // len(inputs[:5])
        max_bar_height = h - 20
        
        for i, val in enumerate(inputs[:5]):
            bar_height = int(abs(val) * max_bar_height)
            bar_x = x + i * bar_width + 2
            bar_y = y + h - bar_height - 5
            
            # Color based on value
            if val > 0.7:
                color = (255, 100, 100)  # Red - danger
            elif val > 0.4:
                color = (255, 255, 100)  # Yellow - caution
            else:
                color = (100, 255, 100)  # Green - safe
            
            pygame.draw.rect(surface, color, (bar_x, bar_y, bar_width - 4, bar_height))
