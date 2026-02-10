"""Command-line interface for AI Racing Evolution."""

import os
import sys
from pathlib import Path

import click

from src.config import get_settings, load_theme, save_theme, themes
from src.config.settings import reset_settings
from src.logging_config import configure_logging, get_logger
from src.video.producer import VideoProducer
from src.video.uploader import YouTubeUploader

logger = get_logger(__name__)


def validate_environment() -> None:
    """Validate required environment variables are set."""
    settings = get_settings()
    
    if settings.enable_youtube_upload:
        required = ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"]
        missing = [v for v in required if not os.getenv(v)]
        if missing:
            raise click.UsageError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Set these or disable YouTube upload with --no-upload"
            )


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option("--env", default="development", help="Environment (development/staging/production)")
@click.option("--enhanced", is_flag=True, help="Use enhanced trainer with all features")
@click.pass_context
def cli(ctx: click.Context, debug: bool, env: str, enhanced: bool) -> None:
    """AI Racing Evolution - Train AI to race and generate videos."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["env"] = env
    ctx.obj["enhanced"] = enhanced
    
    log_level = "DEBUG" if debug else "INFO"
    configure_logging(log_level=log_level, debug=debug)
    
    os.environ["ENV"] = env
    reset_settings()
    
    logger.info("cli_started", env=env, debug=debug, enhanced=enhanced)


@cli.command()
@click.option("--seed", type=int, help="Random seed for track generation")
@click.option("--theme", type=click.Choice(list(themes.THEMES.keys())), help="Theme to use")
@click.option("--difficulty", type=int, help="Curriculum difficulty level (1-8)")
@click.pass_context
def config(ctx: click.Context, seed: int | None, theme: str | None, difficulty: int | None) -> None:
    """Generate daily theme configuration."""
    if theme:
        theme_data = themes.THEMES[theme]
        map_seed = seed if seed is not None else os.urandom(4).__hash__() % 999_999
        daily_theme = themes.ThemeConfig(
            key=theme,
            name=theme_data["name"],
            friction=theme_data["friction"],
            colors=theme_data["colors"],
            title_template=theme_data["title"],
            tags=theme_data["tags"],
            map_seed=map_seed,
        )
    else:
        daily_theme = themes.get_daily_theme()
    
    save_theme(daily_theme)
    click.echo(f"Generated theme: {daily_theme.name} (seed: {daily_theme.map_seed})")
    
    # Set curriculum level if specified
    if difficulty:
        from src.curriculum.manager import get_curriculum_manager
        curr = get_curriculum_manager()
        curr.current_level = difficulty
        click.echo(f"Curriculum level set to: {difficulty}")


@cli.command()
@click.pass_context
def assets(ctx: click.Context) -> None:
    """Generate asset sprites based on theme."""
    import pygame
    
    settings = get_settings()
    settings.paths.assets_dir.mkdir(parents=True, exist_ok=True)
    
    pygame.init()
    
    from src.assets.generator import generate_all_assets
    
    try:
        generate_all_assets(settings.paths.assets_dir)
        click.echo("Assets generated successfully")
    except Exception as e:
        logger.error("asset_generation_failed", error=str(e))
        raise click.ClickException(f"Failed to generate assets: {e}")
    finally:
        pygame.quit()


@cli.command()
@click.option("--generations", "-g", type=int, help="Number of generations to run")
@click.option("--resume/--no-resume", default=True, help="Resume from checkpoint if available")
@click.option("--enhanced/--legacy", default=True, help="Use enhanced trainer with all features")
@click.pass_context
def train(ctx: click.Context, generations: int | None, resume: bool, enhanced: bool) -> None:
    """Run NEAT evolution training."""
    settings = get_settings()
    
    if generations:
        settings.neat.daily_generations = generations
    
    # Use enhanced trainer if requested or set in context
    use_enhanced = enhanced or ctx.obj.get("enhanced", True)
    
    logger.info(
        "starting_training",
        generations=settings.neat.daily_generations,
        resume=resume,
        enhanced=use_enhanced,
    )
    
    if use_enhanced:
        from src.ai.enhanced_trainer import EnhancedEvolutionTrainer
        trainer = EnhancedEvolutionTrainer()
    else:
        from src.ai.trainer import EvolutionTrainer
        trainer = EvolutionTrainer()
    
    try:
        trainer.run_evolution()
        click.echo(f"Training complete! Reached generation {trainer.generation}")
        
        # Show curriculum progress if enabled
        if use_enhanced and hasattr(trainer, 'curriculum'):
            progress = trainer.curriculum.get_progress_percent()
            click.echo(f"Curriculum progress: {progress:.1f}%")
            
    except KeyboardInterrupt:
        logger.info("training_interrupted")
        click.echo("Training interrupted by user")
    except Exception as e:
        logger.error("training_failed", error=str(e))
        raise click.ClickException(f"Training failed: {e}")


@cli.command()
@click.option("--upload/--no-upload", default=True, help="Upload to YouTube after rendering")
@click.option("--title", help="Custom video title (A/B test)")
@click.pass_context
def render(ctx: click.Context, upload: bool, title: str | None) -> None:
    """Render final video from training clips."""
    settings = get_settings()
    settings.enable_youtube_upload = upload
    
    if upload:
        validate_environment()
    
    logger.info("starting_render", upload=upload)
    
    try:
        producer = VideoProducer()
        
        # Use custom title if provided
        if title:
            click.echo(f"Using custom title: {title}")
        
        video_path, generation = producer.produce()
        
        if not video_path:
            raise click.ClickException("Video production failed")
        
        click.echo(f"Video rendered: {video_path}")
        
        if upload:
            uploader = YouTubeUploader()
            video_id = uploader.upload(video_path, generation)
            
            if video_id:
                click.echo(f"Uploaded to YouTube: https://youtu.be/{video_id}")
            else:
                click.echo("Upload failed", err=True)
                
    except Exception as e:
        logger.error("render_failed", error=str(e))
        raise click.ClickException(f"Rendering failed: {e}")


@cli.command()
@click.pass_context
def daily(ctx: click.Context) -> None:
    """Run full daily pipeline (config -> assets -> train -> render -> upload)."""
    click.echo("=== AI Racing Evolution - Daily Run ===")
    
    validate_environment()
    
    click.echo("\n1. Generating theme...")
    daily_theme = themes.get_daily_theme()
    save_theme(daily_theme)
    click.echo(f"   Theme: {daily_theme.name}")
    
    click.echo("\n2. Generating assets...")
    ctx.invoke(assets)
    
    click.echo("\n3. Running evolution (enhanced)...")
    ctx.invoke(train, enhanced=True)
    
    click.echo("\n4. Rendering and uploading...")
    ctx.invoke(render, upload=True)
    
    click.echo("\n=== Daily run complete! ===")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current project status."""
    settings = get_settings()
    
    click.echo("=== Project Status ===")
    
    theme = load_theme()
    if theme:
        click.echo(f"Theme: {theme.name} ({theme.key})")
        click.echo(f"Seed: {theme.map_seed}")
        click.echo(f"Friction: {theme.friction}")
    else:
        click.echo("Theme: Not set")
    
    checkpoints = list(Path(".").glob("neat-checkpoint-*"))
    if checkpoints:
        latest = max(checkpoints, key=lambda p: int(p.stem.split("-")[-1]))
        gen = int(latest.stem.split("-")[-1])
        click.echo(f"Latest checkpoint: Gen {gen} ({latest.name})")
    else:
        click.echo("Checkpoints: None (fresh start)")
    
    clips = list(settings.paths.clips_dir.glob("gen_*.mp4"))
    click.echo(f"Training clips: {len(clips)}")
    
    assets = list(settings.paths.assets_dir.glob("*.png"))
    click.echo(f"Assets: {len(assets)}")
    
    # Feature flags status
    from src.utils.feature_flags import get_feature_flags
    flags = get_feature_flags()
    click.echo("\n=== Feature Flags ===")
    click.echo(f"Curriculum Learning: {'ON' if flags.enable_curriculum else 'OFF'}")
    click.echo(f"Weather System: {'ON' if flags.enable_weather else 'OFF'}")
    click.echo(f"Ghost Cars: {'ON' if flags.enable_ghost_cars else 'OFF'}")
    click.echo(f"Multi-objective: {'ON' if flags.enable_multi_objective else 'OFF'}")
    click.echo(f"Error Recovery: {'ON' if flags.enable_error_recovery else 'OFF'}")
    click.echo(f"Wandb: {'ON' if flags.enable_wandb else 'OFF'}")


@cli.command()
@click.argument("flag_name")
@click.argument("value", type=bool)
def feature(flag_name: str, value: bool) -> None:
    """Toggle a feature flag."""
    from src.utils.feature_flags import get_feature_flags
    
    flags = get_feature_flags()
    flags.set(flag_name, value)
    
    # Save to file
    from src.utils.feature_flags import FeatureFlagManager
    manager = FeatureFlagManager()
    manager.save()
    
    click.echo(f"Feature '{flag_name}' set to {value}")


@cli.command()
@click.option("--limit", default=20, help="Number of generations to show")
def metrics(limit: int) -> None:
    """Show recent evolution metrics."""
    from src.metrics.database import MetricsDatabase
    
    db = MetricsDatabase()
    history = db.get_fitness_history(limit=limit)
    
    if not history:
        click.echo("No metrics data available yet.")
        return
    
    click.echo(f"\n{'Gen':<6} {'Max Fit':<12} {'Avg Fit':<12} {'Species':<8} {'Theme':<15}")
    click.echo("-" * 60)
    
    for row in history:
        click.echo(
            f"{row['generation']:<6} "
            f"{row['max_fitness']:<12.1f} "
            f"{row['avg_fitness']:<12.1f} "
            f"{row['species_count']:<8} "
            f"{row.get('theme', 'unknown'):<15}"
        )


@cli.command()
def curriculum() -> None:
    """Show curriculum progress."""
    from src.curriculum.manager import get_curriculum_manager
    
    curr = get_curriculum_manager()
    config = curr.get_current_config()
    
    click.echo("=== Curriculum Progress ===")
    click.echo(f"Current Level: {config.level.value} - {config.name}")
    click.echo(f"Description: {config.description}")
    click.echo(f"Progress: {curr.get_progress_percent():.1f}%")
    click.echo(f"Generations at level: {curr.generations_at_level}")
    click.echo(f"\nTarget fitness: {config.fitness_threshold}")
    click.echo(f"Generations to advance: {config.generations_to_advance}")


@cli.command()
def tournament() -> None:
    """Run weekly tournament with best cars."""
    from src.racing.tournament import WeeklyTournament
    
    click.echo("Starting weekly tournament...")
    
    tourney = WeeklyTournament()
    results = tourney.run_tournament()
    
    click.echo("\n=== Tournament Results ===")
    for i, result in enumerate(results[:5], 1):
        click.echo(f"{i}. Gen {result['generation']} - {result['points']} points")


@cli.command()
def crash_report() -> None:
    """Show crash recovery statistics."""
    from src.utils.error_recovery import ErrorRecovery
    
    recovery = ErrorRecovery()
    stats = recovery.get_recovery_stats()
    
    click.echo("=== Crash Recovery Stats ===")
    click.echo(f"Total crashes: {stats['total_crashes']}")
    click.echo(f"Emergency checkpoints: {stats['emergency_checkpoints']}")
    click.echo(f"Recovery attempts: {stats['recovery_attempts']}/{stats['max_attempts']}")


def main() -> None:
    """Entry point."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    
    cli()


if __name__ == "__main__":
    main()
