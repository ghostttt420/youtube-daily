# AI Racing Evolution

[![Daily Evolution](https://github.com/YOUR_USERNAME/youtube-daily/actions/workflows/daily.yml/badge.svg)](https://github.com/YOUR_USERNAME/youtube-daily/actions/workflows/daily.yml)

A NEAT (NeuroEvolution of Augmenting Topologies) based AI racing simulation that evolves cars to drive on procedurally generated tracks. The system automatically generates and uploads videos to YouTube showing the AI's progression.

## Features

- 🧬 **NEAT Evolution**: Cars evolve using neural networks that improve over generations
- 🏎️ **Physics Simulation**: Realistic car physics with drifting, collision, and friction
- 🎨 **Procedural Tracks**: Randomly generated racing tracks with different themes
- 🎬 **Automatic Video Production**: Stitches training clips into viral-worthy videos
- 📺 **YouTube Integration**: Automatic upload with optimized titles and descriptions
- 🌍 **Daily Themes**: 9 different visual themes (Circuit, Ice, Desert, Cyber, etc.)

## Project Structure

```
youtube-daily/
├── src/
│   ├── ai/              # NEAT training logic
│   ├── simulation/      # Physics and rendering
│   ├── video/           # Video production and upload
│   ├── assets/          # Asset generation
│   ├── config/          # Configuration management
│   ├── cli.py           # Command-line interface
│   ├── constants.py     # Application constants
│   └── logging_config.py # Structured logging
├── tests/               # Test suite
├── data/checkpoints/    # NEAT checkpoints
├── training_clips/      # Generated training videos
└── assets/              # Generated sprites
```

## Quick Start

### Prerequisites

- Python 3.10+
- FFmpeg
- SDL2 (for pygame)

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/youtube-daily.git
cd youtube-daily

# Install dependencies
pip install -r requirements.txt

# For development
pip install -r requirements-dev.txt
```

### Environment Variables

Create a `.env` file:

```bash
# YouTube API credentials (for uploads)
YT_CLIENT_ID=your_client_id
YT_CLIENT_SECRET=your_client_secret
YT_REFRESH_TOKEN=your_refresh_token

# Optional: Override defaults
SIM_FPS=30
NEAT_DAILY_GENERATIONS=50
```

### Running Locally

```bash
# Run the complete daily pipeline
python -m src.cli daily

# Or step by step:
python -m src.cli config          # Generate theme
python -m src.cli assets          # Generate sprites
python -m src.cli train           # Run evolution
python -m src.cli render          # Create video

# Check status
python -m src.cli status
```

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_simulation.py
```

## Configuration

### Themes

Available themes are defined in `src/config/themes.py`:

- **CIRCUIT**: Standard F1 racing
- **ICE**: Slippery ice drifting
- **DESERT**: Mars rally conditions
- **CYBER**: Neon cyberpunk night racing
- **TOXIC**: Post-apocalyptic wasteland
- **LAVA**: Dangerous volcano track
- **RETRO**: 80s synthwave style
- **JUNGLE**: Off-road mud racing
- **MIDNIGHT**: Tokyo drift streets

### NEAT Parameters

Edit `config.txt` or use environment variables:

```bash
NEAT_POPULATION_SIZE=40
NEAT_DAILY_GENERATIONS=50
```

## GitHub Actions Automation

The project includes a GitHub Actions workflow that:

1. Runs 3 times daily (9am, 4pm, 11pm UTC)
2. Generates a new random theme
3. Evolves the AI for 50 generations
4. Renders and uploads the video
5. Saves checkpoints to git

### Setup

1. Fork this repository
2. Add YouTube API credentials as repository secrets:
   - `YT_CLIENT_ID`
   - `YT_CLIENT_SECRET`
   - `YT_REFRESH_TOKEN`
3. Enable GitHub Actions

## Architecture

### Simulation Layer (`src/simulation/`)

- **Car**: Physics-based vehicle with sensors
- **Camera**: Smooth following camera
- **TrackGenerator**: Procedural track generation using splines

### AI Layer (`src/ai/`)

- **EvolutionTrainer**: Manages NEAT evolution process
- Uses 7 inputs (5 radar sensors + 2 GPS)
- 2 outputs (steering + acceleration)

### Video Layer (`src/video/`)

- **VideoProducer**: Stitches clips with text overlays
- **YouTubeUploader**: Handles API upload with metadata

## Development

### Code Quality

```bash
# Format code
black src tests

# Lint
ruff check src tests

# Type check
mypy src
```

### Adding New Features

1. Create a feature branch
2. Add tests in `tests/`
3. Run the test suite
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- [NEAT-Python](https://github.com/CodeReclaimers/neat-python) for the evolution algorithm
- [Pygame](https://www.pygame.org/) for graphics
- [MoviePy](https://zulko.github.io/moviepy/) for video editing
