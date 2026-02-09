"""Generate sprite assets procedurally."""

from pathlib import Path

import pygame

from src.logging_config import get_logger

logger = get_logger(__name__)


def create_f1_sprite(
    color: tuple[int, int, int],
    filename: str | Path,
    size: tuple[int, int] = (50, 85),
) -> None:
    """Generate an F1-style car sprite.
    
    Args:
        color: Body color as RGB tuple
        filename: Output filename
        size: Sprite dimensions (width, height)
    """
    w, h = 60, 100
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    
    body_col = color
    tire_col = (20, 20, 20)
    cockpit_col = (10, 10, 10)
    helmet_col = (255, 255, 0)
    wing_col = (50, 50, 50)
    
    # Shadow
    pygame.draw.ellipse(surf, (0, 0, 0, 60), (5, 5, w - 10, h - 10))
    
    # Rear wing
    pygame.draw.rect(surf, wing_col, (5, 85, 50, 10))
    
    # Rear tires
    pygame.draw.rect(surf, tire_col, (0, 60, 12, 25), border_radius=3)
    pygame.draw.rect(surf, tire_col, (48, 60, 12, 25), border_radius=3)
    
    # Body
    pygame.draw.polygon(
        surf,
        body_col,
        [(20, 10), (40, 10), (45, 60), (42, 90), (18, 90), (15, 60)],
    )
    
    # Front tires
    pygame.draw.rect(surf, tire_col, (0, 15, 10, 20), border_radius=3)
    pygame.draw.rect(surf, tire_col, (50, 15, 10, 20), border_radius=3)
    
    # Front wing
    pygame.draw.polygon(surf, wing_col, [(5, 5), (55, 5), (30, 0)])
    
    # Cockpit
    pygame.draw.ellipse(surf, cockpit_col, (25, 45, 10, 20))
    pygame.draw.circle(surf, helmet_col, (30, 50), 4)
    
    # Scale to target size
    if (w, h) != size:
        surf = pygame.transform.scale(surf, size)
    
    pygame.image.save(surf, str(filename))
    logger.info("sprite_generated", filename=str(filename), color=color)


def create_smoke_sprite(filename: str | Path, size: int = 32) -> None:
    """Generate a smoke particle sprite.
    
    Args:
        filename: Output filename
        size: Sprite size (square)
    """
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    
    # Create soft fade circles
    for i in range(size // 2, 0, -1):
        alpha = int(150 * (1 - (i / (size // 2))))
        pygame.draw.circle(surf, (200, 200, 200, alpha), (size // 2, size // 2), i)
    
    pygame.image.save(surf, str(filename))
    logger.info("smoke_sprite_generated", filename=str(filename))


def generate_all_assets(assets_dir: str | Path) -> None:
    """Generate all required assets.
    
    Args:
        assets_dir: Directory to save assets
    """
    assets_dir = Path(assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    # Leader car (red Ferrari style)
    create_f1_sprite((220, 0, 0), assets_dir / "car_leader.png")
    
    # Normal car (blue Red Bull style)
    create_f1_sprite((0, 0, 220), assets_dir / "car_normal.png")
    
    # Smoke particle
    create_smoke_sprite(assets_dir / "particle_smoke.png")
    
    logger.info("all_assets_generated", directory=str(assets_dir))
