"""Application constants."""

# Physics constants
class Physics:
    """Physics simulation constants."""
    
    DEFAULT_FRICTION = 0.97
    DEFAULT_MAX_SPEED = 29.0
    DEFAULT_ACCELERATION = 1.2
    DEFAULT_TURN_SPEED = 0.18
    CAR_COLLISION_BOUNCE = 0.8
    CAR_COLLISION_PUSH = 15.0


# Sensor/AI constants
class Sensors:
    """Sensor configuration constants."""
    
    RAY_ANGLES = [-90, -60, -45, -30, -15, 0, 15, 30, 45, 60, 90]
    DEFAULT_LENGTH = 300
    RAY_STEP = 20
    CENTER_BONUS_WEIGHT = 0.1


# Fitness scoring constants
class Fitness:
    """NEAT fitness calculation constants."""
    
    GATE_PASS_BONUS = 500
    LAP_COMPLETE_BONUS = 2000
    DEATH_PENALTY = 200
    EARLY_DEATH_PENALTY = 100
    STUCK_PENALTY = 20
    DISTANCE_WEIGHT = 0.05
    MIN_DISTANCE_FOR_EARLY_DEATH = 500
    MAX_FRAMES_WITHOUT_GATE = 90
    MAX_FRAMES_STUCK = 450


# Visual constants
class Visuals:
    """Visual rendering constants."""
    
    DEFAULT_WIDTH = 1080
    DEFAULT_HEIGHT = 1920
    DEFAULT_WORLD_SIZE = 4000
    DEFAULT_FPS = 30
    
    # Track generation
    TRACK_POINTS = 20
    TRACK_RADIUS_MIN = 1100
    TRACK_RADIUS_MAX = 1800
    TRACK_SMOOTHING = 5000
    CHECKPOINT_INTERVAL = 70
    
    # Road dimensions
    ROAD_WIDTH = 450
    WALL_WIDTH = 260
    EDGE_WIDTH = 235
    ASPHALT_WIDTH = 210
    
    # Kerb settings
    KERB_SEGMENT_LENGTH = 60
    KERB_WIDTH = 28
    
    # Center line
    DASH_LENGTH = 40
    DASH_GAP = 30
    DASH_WIDTH = 4


# Video production constants
class Video:
    """Video rendering constants."""
    
    OUTPUT_FPS = 30
    TARGET_DURATION = 58.0  # YouTube Shorts target
    MAX_DURATION = 60.0
    
    # Frame recording
    RECORD_EVERY_N_FRAMES = 10
    
    # Audio
    MUSIC_VOLUME = 0.5
    ENGINE_VOLUME_BASE = 0.4
    VOICE_VOLUME = 1.0


# YouTube upload constants
class YouTube:
    """YouTube upload configuration."""
    
    CATEGORY_ID = "28"  # Science & Technology
    DEFAULT_TAGS = ["ai", "machine learning", "python", "racing", "simulation", "coding"]
    MAX_TITLE_LENGTH = 100


# NEAT configuration
class NEAT:
    """NEAT algorithm constants."""
    
    DEFAULT_POPULATION = 60
    DEFAULT_GENERATIONS = 50
    CHECKPOINT_INTERVAL = 5
    INPUTS = 15  # 11 sensors + 2 GPS (current) + 1 speed + 1 GPS (next-next checkpoint)
    OUTPUTS = 2  # steering + gas (though gas is always on in current impl)
