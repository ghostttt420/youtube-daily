"""Video production from training clips."""

from __future__ import annotations

import random
from pathlib import Path

import structlog

try:
    from moviepy.editor import (
        AudioFileClip,
        CompositeAudioClip,
        CompositeVideoClip,
        TextClip,
        VideoFileClip,
        concatenate_videoclips,
        vfx,
    )
    from moviepy.audio.fx.all import audio_loop
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

from src.config import get_settings, load_theme
from src.constants import Video
from src.logging_config import get_logger

logger = get_logger(__name__)


# Viral title templates
VIRAL_TITLES = [
    "AI Learns to Drive: Gen 1 vs Gen {gen} 🤯",
    "I taught an AI to drive and it did THIS... (Gen {gen})",
    "Watch my AI go from NOOB to PRO in {gen} Gens 🚀",
    "Can AI beat a Pro Driver? Gen {gen} Update",
    "This AI Driver is getting SCARY good 🤖🚗",
    "Evolution of AI Driving: Gen 0 to {gen}",
    "AI Driving Fails vs Wins (Gen {gen})",
    "You won't believe how good this AI got! (Gen {gen})",
    "Satisfying AI Lines... Gen {gen} is CLEAN 🤤",
    "Gen {gen}: The AI's final form 🏎️",
]

# Hook overlays for first clip
HOOKS = [
    "WAIT FOR IT... 💀",
    "GEN 1 VS GEN 100",
    "PURE CHAOS 🤡",
    "SATISFYING 🤤",
    "AI TRAINING... 🧬",
]


class VideoProducer:
    """Produces final video from training clips."""

    def __init__(self) -> None:
        """Initialize the video producer."""
        if not MOVIEPY_AVAILABLE:
            raise RuntimeError("MoviePy is required for video production")
        
        self.settings = get_settings()
        self.clips_dir = self.settings.paths.clips_dir
        self.output_file = Path("evolution_short.mp4")
        
        # Audio options
        self.music_options = ["music.mp3", "music2.mp3", "music3.mp3"]
        self.engine_file = "engine.mp3"

    def get_viral_title(self, generation: int) -> str:
        """Generate a viral title for the video.
        
        Args:
            generation: Final generation number
            
        Returns:
            Formatted title string
        """
        template = random.choice(VIRAL_TITLES)
        return template.format(gen=generation)

    def find_clips(self) -> list[Path]:
        """Find all training clips sorted by generation.
        
        Returns:
            List of clip paths
        """
        if not self.clips_dir.exists():
            logger.error("clips_directory_not_found", path=str(self.clips_dir))
            return []
        
        clips = sorted(self.clips_dir.glob("gen_*.mp4"))
        logger.info("clips_found", count=len(clips))
        return clips

    def extract_generation(self, path: Path) -> int:
        """Extract generation number from filename.
        
        Args:
            path: Clip file path
            
        Returns:
            Generation number or 0
        """
        try:
            return int(path.stem.split("_")[-1])
        except (ValueError, IndexError):
            return 0

    def produce(self) -> tuple[Path | None, int]:
        """Produce the final video from clips.
        
        Returns:
            Tuple of (output_path, final_generation)
        """
        logger.info("video_production_starting")
        
        clips = self.find_clips()
        if not clips:
            logger.error("no_clips_found")
            return None, 0
        
        final_gen = self.extract_generation(clips[-1])
        logger.info("producing_video", clip_count=len(clips), final_gen=final_gen)
        
        # Calculate target duration per clip to hit ~58s total
        # Allow buffer for intro/outro text overlays
        target_total = Video.TARGET_DURATION  # 58s
        num_clips = len(clips)
        
        # Process each clip with dynamic duration based on total target
        processed_clips = []
        chosen_hook = random.choice(HOOKS)
        engine_volumes = []
        
        for i, clip_path in enumerate(clips):
            processed = self._process_clip(
                clip_path, i, len(clips), chosen_hook, target_total, num_clips
            )
            if processed:
                processed_clips.append(processed["clip"])
                engine_volumes.append((processed["duration"], processed["engine_vol"]))
        
        if not processed_clips:
            logger.error("no_clips_processed")
            return None, 0
        
        # Concatenate
        final_video = concatenate_videoclips(processed_clips, method="compose")
        
        # Time adjustment - only speed up if we're over max, otherwise pad to target
        speed_ratio = 1.0
        if final_video.duration > Video.MAX_DURATION:
            speed_ratio = final_video.duration / Video.TARGET_DURATION
            logger.info("speeding_up_video", ratio=speed_ratio)
            final_video = final_video.fx(vfx.speedx, speed_ratio)
        elif final_video.duration < Video.TARGET_DURATION:
            # Loop the video to reach target duration
            logger.info("looping_video", current_duration=final_video.duration, target=Video.TARGET_DURATION)
            loops_needed = int(Video.TARGET_DURATION / final_video.duration) + 1
            final_video = concatenate_videoclips([final_video] * loops_needed, method="compose")
            final_video = final_video.subclip(0, Video.TARGET_DURATION)
        
        # Add audio
        final_video = self._add_audio(final_video, speed_ratio)
        
        # Write output
        logger.info("writing_video", path=str(self.output_file))
        final_video.write_videofile(
            str(self.output_file),
            fps=Video.OUTPUT_FPS,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            logger=None,
        )
        
        # Cleanup
        for clip in processed_clips:
            clip.close()
        final_video.close()
        
        logger.info("video_production_complete", path=str(self.output_file))
        return self.output_file, final_gen

    def _process_clip(
        self,
        clip_path: Path,
        index: int,
        total: int,
        hook: str,
        target_total: float = 58.0,
        num_clips: int = 1,
    ) -> dict | None:
        """Process a single clip.
        
        Args:
            clip_path: Path to clip
            index: Clip index
            total: Total clips
            hook: Hook text for first clip
            
        Returns:
            Dict with clip info or None on failure
        """
        try:
            clip = VideoFileClip(str(clip_path))
            
            # Resize if needed
            if clip.w > 1080:
                clip = clip.resize(width=1080)
            
            gen_num = self.extract_generation(clip_path)
            is_first = index == 0
            is_last = index == total - 1
            
            # Calculate target duration for this clip
            # Distribute time: first and last get more, middle get less
            if is_first:
                target_duration = min(12.0, target_total * 0.2)  # 20% or max 12s
            elif is_last:
                target_duration = min(20.0, target_total * 0.3)  # 30% or max 20s
            else:
                # Distribute remaining time among middle clips
                remaining = target_total - min(12.0, target_total * 0.2) - min(20.0, target_total * 0.3)
                middle_count = max(1, num_clips - 2)
                target_duration = remaining / middle_count
            
            if is_first:
                clip_info = self._apply_first_clip_effects(clip, hook, gen_num, target_duration)
            elif is_last:
                clip_info = self._apply_last_clip_effects(clip, gen_num, target_duration)
            else:
                clip_info = self._apply_middle_clip_effects(clip, gen_num, target_duration)
            
            return clip_info
            
        except Exception as e:
            logger.error("clip_processing_failed", path=str(clip_path), error=str(e))
            return None

    def _apply_first_clip_effects(
        self,
        clip: VideoFileClip,
        hook: str,
        gen_num: int,
        target_duration: float = 10.0,
    ) -> dict:
        """Apply effects to first clip.
        
        Args:
            clip: Input clip
            hook: Hook text
            gen_num: Generation number
            target_duration: Target duration in seconds
            
        Returns:
            Clip info dict
        """
        # Use target duration, but don't exceed clip length
        use_duration = min(clip.duration, target_duration)
        if clip.duration > use_duration:
            clip = clip.subclip(0, use_duration)
        
        try:
            # Big hook text
            txt_hook = TextClip(
                hook,
                fontsize=110,
                color="white",
                font="DejaVu-Sans-Bold",
                stroke_color="black",
                stroke_width=5,
            )
            txt_hook = txt_hook.set_position("center").set_duration(clip.duration)
            
            # Label below
            txt_label = TextClip(
                f"Gen {gen_num}: TOTAL NOOB 🤡",
                fontsize=60,
                color="red",
                font="DejaVu-Sans-Bold",
                stroke_color="black",
                stroke_width=2,
            )
            txt_label = txt_label.set_position(("center", 0.8), relative=True).set_duration(clip.duration)
            
            clip = CompositeVideoClip([clip, txt_hook, txt_label])
        except Exception as e:
            logger.warning("text_overlay_failed", error=str(e))
        
        return {
            "clip": clip,
            "duration": clip.duration,
            "engine_vol": 0.3,
        }

    def _apply_last_clip_effects(
        self, 
        clip: VideoFileClip, 
        gen_num: int,
        target_duration: float = 15.0,
    ) -> dict:
        """Apply effects to last clip.
        
        Args:
            clip: Input clip
            gen_num: Generation number
            target_duration: Target duration in seconds
            
        Returns:
            Clip info dict
        """
        # Use target duration, but don't exceed clip length
        use_duration = min(clip.duration, target_duration)
        if clip.duration > use_duration:
            clip = clip.subclip(0, use_duration)
        try:
            txt = TextClip(
                f"Gen {gen_num}: EVOLUTION 🏁",
                fontsize=90,
                color="#00FF41",
                font="DejaVu-Sans-Bold",
                stroke_color="black",
                stroke_width=4,
            )
            txt = txt.set_position(("center", 0.2), relative=True).set_duration(clip.duration)
            clip = CompositeVideoClip([clip, txt])
        except Exception as e:
            logger.warning("text_overlay_failed", error=str(e))
        
        return {
            "clip": clip,
            "duration": clip.duration,
            "engine_vol": 0.8,
        }

    def _apply_middle_clip_effects(
        self, 
        clip: VideoFileClip, 
        gen_num: int,
        target_duration: float = 8.0,
    ) -> dict:
        """Apply effects to middle clip.
        
        Args:
            clip: Input clip
            gen_num: Generation number
            target_duration: Target duration in seconds
            
        Returns:
            Clip info dict
        """
        # Use target duration, but don't exceed clip length
        use_duration = min(clip.duration, target_duration)
        if clip.duration > use_duration:
            clip = clip.subclip(0, use_duration)
        
        try:
            txt = TextClip(
                f"Gen {gen_num}: Learning...",
                fontsize=60,
                color="yellow",
                font="DejaVu-Sans-Bold",
                stroke_color="black",
                stroke_width=2,
            )
            txt = txt.set_position(("center", 0.8), relative=True).set_duration(clip.duration)
            clip = CompositeVideoClip([clip, txt])
        except Exception as e:
            logger.warning("text_overlay_failed", error=str(e))
        
        return {
            "clip": clip,
            "duration": clip.duration,
            "engine_vol": 0.5,
        }

    def _add_audio(self, video: VideoFileClip, speed_ratio: float) -> VideoFileClip:
        """Add music and engine sounds to video.
        
        Args:
            video: Input video
            speed_ratio: Speed multiplier applied to video
            
        Returns:
            Video with audio
        """
        audio_tracks = []
        
        # Add music
        available_music = [m for m in self.music_options if Path(m).exists()]
        if available_music:
            chosen = random.choice(available_music)
            logger.info("adding_music", file=chosen)
            try:
                music = AudioFileClip(chosen)
                if music.duration < video.duration:
                    music = audio_loop(music, duration=video.duration)
                else:
                    music = music.subclip(0, video.duration)
                music = music.volumex(Video.MUSIC_VOLUME)
                audio_tracks.append(music)
            except Exception as e:
                logger.warning("music_processing_failed", error=str(e))
        
        # Add engine sound
        if Path(self.engine_file).exists():
            logger.info("adding_engine_sound")
            try:
                engine = AudioFileClip(self.engine_file)
                engine = audio_loop(engine, duration=video.duration)
                if speed_ratio != 1.0:
                    engine = engine.fx(vfx.speedx, speed_ratio)
                    engine = engine.subclip(0, video.duration)
                engine = engine.volumex(Video.ENGINE_VOLUME_BASE)
                audio_tracks.append(engine)
            except Exception as e:
                logger.warning("engine_processing_failed", error=str(e))
        
        if audio_tracks:
            final_audio = CompositeAudioClip(audio_tracks)
            video = video.set_audio(final_audio)
        
        return video
