"""Tests for simulation components."""

import math

import pygame
import pytest

from src.constants import Physics
from src.simulation.car import Car
from src.simulation.camera import Camera


class TestCar:
    """Test car physics."""

    @pytest.fixture
    def car(self):
        """Create a test car."""
        return Car((100, 100), 0.0)

    @pytest.fixture
    def mock_mask(self):
        """Create a mock collision mask."""
        # Create a 200x200 surface with white (track) everywhere
        surf = pygame.Surface((200, 200))
        surf.fill((255, 255, 255))
        return pygame.mask.from_surface(surf)

    def test_initial_state(self, car):
        """Test car initializes correctly."""
        assert car.position.x == 100
        assert car.position.y == 100
        assert car.angle == 0.0
        assert car.alive is True
        assert car.velocity.length() == 0

    def test_acceleration(self, car, mock_mask):
        """Test car accelerates."""
        initial_speed = car.velocity.length()
        car.input_gas()
        car.update(mock_mask)
        assert car.velocity.length() > initial_speed

    def test_steering(self, car, mock_mask):
        """Test car turns."""
        # Give car some speed first
        for _ in range(10):
            car.input_gas()
            car.update(mock_mask)
        
        initial_angle = car.angle
        car.input_steer(left=True)
        car.update(mock_mask)
        
        assert car.angle != initial_angle

    def test_friction(self, car, mock_mask):
        """Test friction slows car."""
        # Accelerate
        for _ in range(5):
            car.input_gas()
            car.update(mock_mask)
        
        speed_with_gas = car.velocity.length()
        
        # Coast (no gas)
        for _ in range(5):
            car.update(mock_mask)
        
        assert car.velocity.length() < speed_with_gas

    def test_max_speed_cap(self, car, mock_mask):
        """Test max speed is enforced."""
        # Accelerate for many frames
        for _ in range(100):
            car.input_gas()
            car.update(mock_mask)
        
        assert car.velocity.length() <= car.max_speed + 0.1

    def test_collision_death(self, car):
        """Test car dies when leaving track."""
        # Create mask with black (off-track) at car position
        surf = pygame.Surface((200, 200))
        surf.fill((0, 0, 0))  # All black
        mask = pygame.mask.from_surface(surf)
        
        assert car.alive is True
        car.update(mask)
        assert car.alive is False

    def test_gate_checking(self, car):
        """Test checkpoint detection."""
        checkpoints = [(150, 100), (200, 100)]  # One is 50 units away
        
        # Car at (100, 100), first checkpoint at (150, 100)
        result = car.check_gates(checkpoints)
        assert result is False  # Too far
        
        # Move car close to checkpoint
        car.position = pygame.math.Vector2(150, 100)
        result = car.check_gates(checkpoints)
        assert result is True
        assert car.gates_passed == 1
        assert car.next_gate_idx == 1

    def test_sensor_rays(self, car, mock_mask):
        """Test sensor ray casting."""
        car.check_radar(mock_mask)
        
        assert len(car.radars) == 5  # 5 sensors at -60, -30, 0, 30, 60
        
        for endpoint, distance in car.radars:
            assert distance > 0
            assert distance <= 300  # SENSOR_LENGTH

    def test_get_data(self, car):
        """Test AI input generation."""
        checkpoints = [(200, 100)]  # Directly to the right
        
        data = car.get_data(checkpoints)
        assert len(data) == 2
        
        # Car at (100,100), target at (200,100) - heading is 0
        # Car angle is 0, so heading input should be ~0
        assert abs(data[0]) < 0.1  # Heading aligned
        assert data[1] > 0  # Some distance away

    def test_timeout(self, car, mock_mask):
        """Test car dies after too many frames without checkpoint."""
        from src.constants import Fitness
        
        for _ in range(Fitness.MAX_FRAMES_WITHOUT_GATE + 1):
            car.input_gas()
            car.update(mock_mask)
        
        assert car.alive is False


class TestCamera:
    """Test camera system."""

    @pytest.fixture
    def camera(self):
        """Create a test camera."""
        cam = Camera(4000, 4000)
        cam.set_viewport(1080, 1920)
        return cam

    @pytest.fixture
    def mock_car(self):
        """Create a mock car for camera to follow."""
        class MockCar:
            def __init__(self):
                self.position = pygame.math.Vector2(2000, 2000)
        return MockCar()

    def test_initial_state(self, camera):
        """Test camera initializes correctly."""
        assert camera.width == 4000
        assert camera.height == 4000

    def test_apply_point(self, camera):
        """Test coordinate transformation."""
        camera.exact_x = -1000
        camera.exact_y = -1000
        
        result = camera.apply_point((2000, 2000))
        assert result == (1000, 1000)

    def test_follow_target(self, camera, mock_car):
        """Test camera follows target."""
        camera.update(mock_car)
        
        # Camera should be centered on car (minus half viewport)
        expected_x = -mock_car.position.x + 1080 / 2
        expected_y = -mock_car.position.y + 1920 / 2
        
        # Camera smooths over time, so check it's moving toward target
        assert camera.exact_x != 0 or camera.exact_y != 0

    def test_clamping(self, camera, mock_car):
        """Test camera stays within world bounds."""
        # Put car at edge of world
        mock_car.position = pygame.math.Vector2(100, 100)
        
        # Update many times to let smoothing settle
        for _ in range(100):
            camera.update(mock_car)
        
        # Camera should be clamped (exact_x should be 0, not positive)
        assert camera.exact_x <= 0
