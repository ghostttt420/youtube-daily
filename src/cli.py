"""Command-line interface for AI Racing Evolution."""

import os
import sys
from pathlib import Path

import click

from src.ai.trainer import EvolutionTrainer
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
@click.pass_context
def cli(ctx: click.Context, debug: bool, env: str) -> None:
    """AI Racing Evolution - Train AI to race and generate videos."""
    # Ensure context object exists
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["env"] = env
    
    # Configure logging
    log_level = "DEBUG" if debug else "INFO"
    configure_logging(log_level=log_level, debug=debug)
    
    # Set environment
    os.environ["ENV"] = env
    reset_settings()
    
    logger.info("cli_started", env=env, debug=debug)


@cli.command()
@click.option("--seed", type=int, help="Random seed for track generation")
@click.option("--theme", type=click.Choice(list(themes.THEMES.keys())), help="Theme to use")
@click.pass_context
def config(ctx: click.Context, seed: int | None, theme: str | None) -> None:
    """Generate daily theme configuration."""
    if theme:
        # Use specific theme
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
        # Random theme
        daily_theme = themes.get_daily_theme()
    
    save_theme(daily_theme)
    click.echo(f"Generated theme: {daily_theme.name} (seed: {daily_theme.map_seed})")


@cli.command()
@click.pass_context
def assets(ctx: click.Context) -> None:
    """Generate asset sprites based on theme."""
    import pygame
    
    settings = get_settings()
    settings.paths.assets_dir.mkdir(parents=True, exist_ok=True)
    
    pygame.init()
    
    # Import asset generation
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
@click.pass_context
def train(ctx: click.Context, generations: int | None, resume: bool) -> None:
    """Run NEAT evolution training."""
    settings = get_settings()
    
    if generations:
        settings.neat.daily_generations = generations
    
    logger.info(
        "starting_training",
        generations=settings.neat.daily_generations,
        resume=resume,
    )
    
    trainer = EvolutionTrainer()
    
    try:
        trainer.run_evolution()
        click.echo(f"Training complete! Reached generation {trainer.generation}")
    except KeyboardInterrupt:
        logger.info("training_interrupted")
        click.echo("Training interrupted by user")
    except Exception as e:
        logger.error("training_failed", error=str(e))
        raise click.ClickException(f"Training failed: {e}")


@cli.command()
@click.option("--upload/--no-upload", default=True, help="Upload to YouTube after rendering")
@click.pass_context
def render(ctx: click.Context, upload: bool) -> None:
    """Render final video from training clips."""
    settings = get_settings()
    settings.enable_youtube_upload = upload
    
    if upload:
        validate_environment()
    
    logger.info("starting_render", upload=upload)
    
    try:
        # Produce video
        producer = VideoProducer()
        video_path, generation = producer.produce()
        
        if not video_path:
            raise click.ClickException("Video production failed")
        
        click.echo(f"Video rendered: {video_path}")
        
        # Upload if requested
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
    
    # Validate environment first
    validate_environment()
    
    # Step 1: Generate theme
    click.echo("\n1. Generating theme...")
    daily_theme = themes.get_daily_theme()
    save_theme(daily_theme)
    click.echo(f"   Theme: {daily_theme.name}")
    
    # Step 2: Generate assets
    click.echo("\n2. Generating assets...")
    ctx.invoke(assets)
    
    # Step 3: Train
    click.echo("\n3. Running evolution...")
    ctx.invoke(train)
    
    # Step 4: Render and upload
    click.echo("\n4. Rendering and uploading...")
    ctx.invoke(render, upload=True)
    
    click.echo("\n=== Daily run complete! ===")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current project status."""
    settings = get_settings()
    
    click.echo("=== Project Status ===")
    
    # Theme
    theme = load_theme()
    if theme:
        click.echo(f"Theme: {theme.name} ({theme.key})")
        click.echo(f"Seed: {theme.map_seed}")
        click.echo(f"Friction: {theme.friction}")
    else:
        click.echo("Theme: Not set")
    
    # Checkpoints
    checkpoints = list(Path(".").glob("neat-checkpoint-*"))
    if checkpoints:
        latest = max(checkpoints, key=lambda p: int(p.stem.split("-")[-1]))
        gen = int(latest.stem.split("-")[-1])
        click.echo(f"Latest checkpoint: Gen {gen} ({latest.name})")
    else:
        click.echo("Checkpoints: None (fresh start)")
    
    # Clips
    clips = list(settings.paths.clips_dir.glob("gen_*.mp4"))
    click.echo(f"Training clips: {len(clips)}")
    
    # Assets
    assets = list(settings.paths.assets_dir.glob("*.png"))
    click.echo(f"Assets: {len(assets)}")


def main() -> None:
    """Entry point."""
    # Set required env vars for pygame headless
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    
    cli()


if __name__ == "__main__":
    main()
