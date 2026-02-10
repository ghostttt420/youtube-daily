"""Weather system with dynamic conditions."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.simulation.car import Car

logger = structlog.get_logger()


class WeatherType(Enum):
    """Types of weather conditions."""
    CLEAR = auto()
    CLOUDY = auto()
    LIGHT_RAIN = auto()
    HEAVY_RAIN = auto()
    FOG = auto()
    OIL_SPILL = auto()  # Random slippery patch


@dataclass
class WeatherCondition:
    """Current weather state."""
    weather_type: WeatherType
    friction_multiplier: float
    visibility: float  # 1.0 = full, 0.0 = none
    sensor_range_multiplier: float
    duration_frames: int
    intensity: float  # 0.0 to 1.0
    
    # Visual effects
    rain_intensity: float = 0.0
    fog_density: float = 0.0
    lightning_chance: float = 0.0


class WeatherSystem:
    """Manages dynamic weather during races."""

    # Base weather configurations
    WEATHER_CONFIGS: dict[WeatherType, dict] = {
        WeatherType.CLEAR: {
            "friction_mult": 1.0,
            "visibility": 1.0,
            "sensor_mult": 1.0,
            "duration_range": (1000, 2000),
        },
        WeatherType.CLOUDY: {
            "friction_mult": 0.98,
            "visibility": 0.95,
            "sensor_mult": 1.0,
            "duration_range": (800, 1500),
        },
        WeatherType.LIGHT_RAIN: {
            "friction_mult": 0.92,
            "visibility": 0.85,
            "sensor_mult": 0.9,
            "duration_range": (600, 1200),
        },
        WeatherType.HEAVY_RAIN: {
            "friction_mult": 0.85,
            "visibility": 0.6,
            "sensor_mult": 0.75,
            "duration_range": (400, 800),
        },
        WeatherType.FOG: {
            "friction_mult": 0.95,
            "visibility": 0.5,
            "sensor_mult": 0.7,
            "duration_range": (500, 1000),
        },
        WeatherType.OIL_SPILL: {
            "friction_mult": 0.7,  # Very slippery
            "visibility": 1.0,
            "sensor_mult": 1.0,
            "duration_range": (200, 400),  # Short-lived
        },
    }

    def __init__(self, enable_weather: bool = True) -> None:
        """Initialize weather system."""
        self.enabled = enable_weather
        self.current: WeatherCondition | None = None
        self.frame_count = 0
        self.weather_change_timer = 0
        self.oil_spills: list[tuple[float, float, float]] = []  # x, y, radius

    def update(self) -> None:
        """Update weather state."""
        if not self.enabled:
            return
        
        self.frame_count += 1
        
        # Check if weather should change
        if self.current:
            self.weather_change_timer -= 1
            if self.weather_change_timer <= 0:
                self._change_weather()
        else:
            self._change_weather()
        
        # Update oil spills (they dissipate)
        self.oil_spills = [
            (x, y, r - 0.1) for x, y, r in self.oil_spills if r > 0
        ]

    def _change_weather(self) -> None:
        """Change to new random weather."""
        # Weight towards clear weather
        weights = [0.5, 0.2, 0.15, 0.05, 0.05, 0.05]
        weather_type = random.choices(list(WeatherType), weights=weights)[0]
        
        config = self.WEATHER_CONFIGS[weather_type]
        duration = random.randint(*config["duration_range"])
        
        self.current = WeatherCondition(
            weather_type=weather_type,
            friction_multiplier=config["friction_mult"],
            visibility=config["visibility"],
            sensor_range_multiplier=config["sensor_mult"],
            duration_frames=duration,
            intensity=random.uniform(0.3, 1.0),
            rain_intensity=0.5 if weather_type in (WeatherType.LIGHT_RAIN, WeatherType.HEAVY_RAIN) else 0.0,
            fog_density=0.6 if weather_type == WeatherType.FOG else 0.0,
            lightning_chance=0.01 if weather_type == WeatherType.HEAVY_RAIN else 0.0,
        )
        
        self.weather_change_timer = duration
        
        # Create random oil spills for OIL_SPILL weather
        if weather_type == WeatherType.OIL_SPILL:
            self._spawn_oil_spills()
        
        logger.info(
            "weather_changed",
            weather=weather_type.name,
            friction=self.current.friction_multiplier,
            visibility=self.current.visibility,
            duration=duration,
        )

    def _spawn_oil_spills(self) -> None:
        """Create random oil spills on track."""
        import math
        
        # Create 3-5 oil spills
        num_spills = random.randint(3, 5)
        world_size = 4000
        center = world_size // 2
        
        for _ in range(num_spills):
            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(800, 1500)
            x = center + radius * math.cos(angle)
            y = center + radius * math.sin(angle)
            spill_radius = random.uniform(100, 300)
            self.oil_spills.append((x, y, spill_radius))

    def get_friction_at(self, x: float, y: float) -> float:
        """Get friction multiplier at position (for oil spills)."""
        if not self.enabled or not self.current:
            return 1.0
        
        base_friction = self.current.friction_multiplier
        
        # Check if in oil spill
        for sx, sy, sr in self.oil_spills:
            dist = ((x - sx) ** 2 + (y - sy) ** 2) ** 0.5
            if dist < sr:
                return 0.5  # Very slippery in oil
        
        return base_friction

    def get_sensor_range(self, base_range: float) -> float:
        """Get effective sensor range."""
        if not self.enabled or not self.current:
            return base_range
        return base_range * self.current.sensor_range_multiplier

    def affects_car(self, car: Car) -> dict[str, float]:
        """Get weather effects for a car at its current position."""
        if not self.enabled or not self.current:
            return {"friction": 1.0, "visibility": 1.0}
        
        return {
            "friction": self.get_friction_at(car.position.x, car.position.y),
            "visibility": self.current.visibility,
        }

    def get_weather_name(self) -> str:
        """Get current weather name for display."""
        if not self.current:
            return "Clear"
        return self.current.weather_type.name.replace("_", " ").title()

    def force_weather(self, weather_type: WeatherType, duration: int = 600) -> None:
        """Force a specific weather (for curriculum)."""
        config = self.WEATHER_CONFIGS[weather_type]
        
        self.current = WeatherCondition(
            weather_type=weather_type,
            friction_multiplier=config["friction_mult"],
            visibility=config["visibility"],
            sensor_range_multiplier=config["sensor_mult"],
            duration_frames=duration,
            intensity=0.8,
            rain_intensity=0.5 if weather_type in (WeatherType.LIGHT_RAIN, WeatherType.HEAVY_RAIN) else 0.0,
            fog_density=0.6 if weather_type == WeatherType.FOG else 0.0,
        )
        
        self.weather_change_timer = duration
        
        if weather_type == WeatherType.OIL_SPILL:
            self._spawn_oil_spills()

    def clear_oil_spills(self) -> None:
        """Remove all oil spills."""
        self.oil_spills = []
