"""Theme configuration for daily racing environments."""

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import structlog

logger = structlog.get_logger()

ThemeKey = Literal[
    "CIRCUIT", "ICE", "DESERT", "CYBER", "TOXIC", "LAVA", "RETRO", "JUNGLE", "MIDNIGHT"
]


@dataclass(frozen=True)
class ColorScheme:
    """RGB color scheme for a theme."""

    bg: tuple[int, int, int]
    road: tuple[int, int, int]
    wall: tuple[int, int, int]
    center: tuple[int, int, int]


@dataclass(frozen=True)
class ThemeConfig:
    """Complete theme configuration."""

    key: ThemeKey
    name: str
    friction: float
    colors: ColorScheme
    title_template: str
    tags: list[str]
    map_seed: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "theme_key": self.key,
            "map_seed": self.map_seed,
            "physics": {"friction": self.friction},
            "visuals": {
                "bg": list(self.colors.bg),
                "road": list(self.colors.road),
                "wall": list(self.colors.wall),
                "center": list(self.colors.center),
            },
            "meta": {
                "title": self.title_template,
                "tags": self.tags,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ThemeConfig":
        """Create ThemeConfig from dictionary."""
        colors = ColorScheme(**data["visuals"])
        return cls(
            key=data["theme_key"],
            name=data.get("name", data["theme_key"]),
            friction=data["physics"]["friction"],
            colors=colors,
            title_template=data["meta"]["title"],
            tags=data["meta"]["tags"],
            map_seed=data["map_seed"],
        )


# Theme definitions
THEMES: dict[ThemeKey, dict] = {
    "CIRCUIT": {
        "name": "Circuit",
        "friction": 0.97,
        "colors": ColorScheme(
            bg=(30, 35, 30),
            road=(50, 50, 55),
            wall=(200, 0, 0),
            center=(255, 255, 255),
        ),
        "title": "AI Learns to Race F1 Style 🏎️ (Gen {gen})",
        "tags": ["f1", "racing", "motorsport"],
    },
    "ICE": {
        "name": "Ice World",
        "friction": 0.93,
        "colors": ColorScheme(
            bg=(220, 245, 255),
            road=(160, 210, 255),
            wall=(0, 100, 220),
            center=(200, 240, 255),
        ),
        "title": "AI Tries Drifting on ICE ❄️ (Gen {gen})",
        "tags": ["drift", "ice", "winter", "rally"],
    },
    "DESERT": {
        "name": "Mars Rally",
        "friction": 0.955,
        "colors": ColorScheme(
            bg=(160, 60, 30),
            road=(210, 140, 90),
            wall=(90, 40, 10),
            center=(255, 200, 150),
        ),
        "title": "AI Rallies on MARS 🚀 (Gen {gen})",
        "tags": ["rally", "offroad", "mars", "space"],
    },
    "CYBER": {
        "name": "Cyber City",
        "friction": 0.98,
        "colors": ColorScheme(
            bg=(5, 0, 15),
            road=(20, 20, 35),
            wall=(0, 255, 255),
            center=(255, 0, 255),
        ),
        "title": "AI Street Racing at NIGHT 🌃 (Gen {gen})",
        "tags": ["cyberpunk", "neon", "drift", "night"],
    },
    "TOXIC": {
        "name": "Toxic Wasteland",
        "friction": 0.95,
        "colors": ColorScheme(
            bg=(20, 30, 10),
            road=(40, 60, 20),
            wall=(100, 255, 0),
            center=(200, 0, 255),
        ),
        "title": "AI Survives the WASTELAND ☢️ (Gen {gen})",
        "tags": ["post-apocalyptic", "zombie", "survival"],
    },
    "LAVA": {
        "name": "Volcano",
        "friction": 0.94,
        "colors": ColorScheme(
            bg=(40, 5, 5),
            road=(80, 20, 20),
            wall=(255, 80, 0),
            center=(255, 255, 0),
        ),
        "title": "AI Races on LAVA 🔥 (Gen {gen})",
        "tags": ["lava", "hot", "danger", "volcano"],
    },
    "RETRO": {
        "name": "Synthwave",
        "friction": 0.975,
        "colors": ColorScheme(
            bg=(35, 0, 50),
            road=(60, 0, 90),
            wall=(255, 0, 150),
            center=(0, 255, 255),
        ),
        "title": "AI 80s Retro Run 🕹️ (Gen {gen})",
        "tags": ["synthwave", "80s", "retro", "arcade"],
    },
    "JUNGLE": {
        "name": "Deep Jungle",
        "friction": 0.96,
        "colors": ColorScheme(
            bg=(0, 40, 0),
            road=(90, 70, 40),
            wall=(30, 100, 30),
            center=(200, 200, 150),
        ),
        "title": "AI Offroad JUNGLE Run 🌴 (Gen {gen})",
        "tags": ["jungle", "offroad", "4x4", "mud"],
    },
    "MIDNIGHT": {
        "name": "Tokyo Drift",
        "friction": 0.965,
        "colors": ColorScheme(
            bg=(10, 10, 10),
            road=(40, 40, 40),
            wall=(255, 215, 0),
            center=(255, 255, 255),
        ),
        "title": "AI Tokyo Drift Run 🇯🇵 (Gen {gen})",
        "tags": ["jdm", "tokyo", "drift", "japan"],
    },
}


def get_daily_theme() -> ThemeConfig:
    """Generate a random daily theme configuration."""
    theme_key: ThemeKey = random.choice(list(THEMES.keys()))
    theme_data = THEMES[theme_key]
    map_seed = random.randint(0, 999_999)

    theme = ThemeConfig(
        key=theme_key,
        name=theme_data["name"],
        friction=theme_data["friction"],
        colors=theme_data["colors"],
        title_template=theme_data["title"],
        tags=theme_data["tags"],
        map_seed=map_seed,
    )

    logger.info(
        "daily_theme_selected",
        theme=theme_key,
        name=theme.name,
        seed=map_seed,
        friction=theme.friction,
    )
    return theme


def save_theme(theme: ThemeConfig, path: Path | None = None) -> None:
    """Save theme configuration to JSON file."""
    if path is None:
        path = Path("theme.json")

    with open(path, "w") as f:
        json.dump(theme.to_dict(), f, indent=2)

    logger.info("theme_saved", path=str(path))


def load_theme(path: Path | None = None) -> ThemeConfig | None:
    """Load theme configuration from JSON file."""
    if path is None:
        path = Path("theme.json")

    if not path.exists():
        logger.warning("theme_file_not_found", path=str(path))
        return None

    try:
        with open(path) as f:
            data = json.load(f)
        theme = ThemeConfig.from_dict(data)
        logger.info("theme_loaded", path=str(path), theme=theme.key)
        return theme
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("theme_load_failed", path=str(path), error=str(e))
        return None
