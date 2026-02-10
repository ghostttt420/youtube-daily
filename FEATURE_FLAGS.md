# Feature Flags Guide

Feature flags allow you to enable/disable functionality without code changes.

## Available Flags

### Core Features
| Flag | Default | Description |
|------|---------|-------------|
| `enable_curriculum` | `true` | Progressive difficulty system |
| `enable_weather` | `true` | Dynamic weather effects |
| `enable_ghost_cars` | `true` | Ghost car replay system |
| `enable_tournament_mode` | `true` | Weekly championship races |
| `enable_multi_objective` | `true` | Smoothness & efficiency bonuses |

### Visual Features
| Flag | Default | Description |
|------|---------|-------------|
| `enable_telemetry_overlay` | `true` | On-screen speed, sensors, etc. |
| `enable_neural_visualization` | `true` | Network activation display |
| `enable_crash_heatmap` | `true` | Track crash locations |

### Data & Analytics
| Flag | Default | Description |
|------|---------|-------------|
| `enable_wandb` | `false` | Weights & Biases cloud logging |
| `enable_detailed_metrics` | `true` | SQLite metrics database |
| `enable_ab_testing` | `true` | YouTube title optimization |

### Racing Modes
| Flag | Default | Description |
|------|---------|-------------|
| `enable_qualifying` | `true` | Time trial qualifying |
| `enable_race_mode` | `false` | Full race mode (slower) |

### Recovery
| Flag | Default | Description |
|------|---------|-------------|
| `enable_error_recovery` | `true` | Auto-recover from crashes |
| `enable_emergency_checkpoints` | `true` | Save emergency backups |

### Cloud
| Flag | Default | Description |
|------|---------|-------------|
| `enable_cloud_storage` | `false` | S3/GCS checkpoint storage |
| `enable_community_voting` | `false` | Community theme voting |

## Usage

### Command Line
```bash
# Toggle a feature
python -m src.cli feature enable_weather false
python -m src.cli feature enable_wandb true

# Check current status
python -m src.cli status
```

### Environment Variables
```bash
# Override via environment
export FEATURE_WEATHER=false
export FEATURE_WANDB=true
export FEATURE_CURRICULUM=true

python -m src.cli train
```

### Configuration File
Create `feature_flags.json`:
```json
{
  "enable_curriculum": true,
  "enable_weather": false,
  "enable_ghost_cars": true,
  "enable_wandb": false
}
```

## Recommended Configurations

### Performance Mode (Faster)
```bash
python -m src.cli feature enable_weather false
python -m src.cli feature enable_telemetry_overlay false
python -m src.cli feature enable_neural_visualization false
```

### Maximum Engagement (YouTube)
```bash
python -m src.cli feature enable_ab_testing true
python -m src.cli feature enable_ghost_cars true
python -m src.cli feature enable_tournament_mode true
python -m src.cli feature enable_weather true
```

### Development/Debug
```bash
python -m src.cli feature enable_wandb true
python -m src.cli feature enable_detailed_metrics true
python -m src.cli feature enable_error_recovery true
```

### Minimal (Just Evolution)
```bash
python -m src.cli feature enable_curriculum false
python -m src.cli feature enable_weather false
python -m src.cli feature enable_ghost_cars false
python -m src.cli feature enable_telemetry_overlay false
python -m src.cli feature enable_multi_objective false
```

## Feature Dependencies

Some features depend on others:
- `enable_tournament_mode` → uses `enable_ghost_cars`
- `enable_ab_testing` → uses `enable_detailed_metrics`
- `enable_error_recovery` → uses `enable_emergency_checkpoints`

Disabling a dependency will automatically disable dependent features.

## Resetting to Defaults

Delete `feature_flags.json` to reset all flags to defaults:
```bash
rm feature_flags.json
python -m src.cli status
```
