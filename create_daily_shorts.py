#!/usr/bin/env python3
"""
Create daily YouTube Shorts - Professional Version
- 15s Training + 15s Learning + 30s Pro structure
- Uses existing engine.mp3 and music files
- Robust error handling
"""
import os
import glob
import random
import logging
from datetime import datetime
from moviepy.editor import (
    VideoFileClip, concatenate_videoclips, TextClip, 
    CompositeVideoClip, AudioFileClip, CompositeAudioClip
)
from moviepy.video.fx.all import fadein, fadeout
from challenge_loader import ChallengeLoader
from content_strategy import ContentStrategy

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VIDEO_DIR = "training_clips"
OUTPUT_DIR = "daily_shorts"

# Audio file paths - use existing files
ENGINE_SOUND = "engine.mp3"
MUSIC_FILES = ["music.mp3", "music2.mp3", "music3.mp3"]


def get_all_clips():
    """Get all mp4 clips from training_clips directory, grouped by theme folder"""
    pattern = os.path.join(VIDEO_DIR, "**", "*.mp4")
    clips = glob.glob(pattern, recursive=True)
    
    def get_gen(filename):
        try:
            basename = os.path.basename(filename)
            # Extract number from gen_00531.mp4
            num_part = basename.split('_')[1].split('.')[0]
            return int(num_part)
        except (IndexError, ValueError):
            return 0
    
    # Group clips by their parent directory (theme folder)
    from collections import defaultdict
    clips_by_folder = defaultdict(list)
    for clip in clips:
        folder = os.path.dirname(clip)
        clips_by_folder[folder].append(clip)
    
    # Sort each folder's clips by generation
    for folder in clips_by_folder:
        clips_by_folder[folder].sort(key=get_gen)
    
    # Return a random folder's clips (all same theme)
    if clips_by_folder:
        selected_folder = random.choice(list(clips_by_folder.keys()))
        logger.info(f"Selected theme folder: {os.path.basename(selected_folder)}")
        return clips_by_folder[selected_folder]
    return []


def get_clip_duration(video_path):
    """Get duration of a video clip"""
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration
        clip.close()
        return duration
    except Exception as e:
        logger.warning(f"Could not get duration for {video_path}: {e}")
        return 0


def load_audio_files(duration):
    """
    Load and prepare audio from existing mp3 files.
    Returns a CompositeAudioClip with engine + music mixed.
    """
    audio_clips = []
    
    # 1. Add engine sound - loop if necessary
    if os.path.exists(ENGINE_SOUND):
        try:
            engine = AudioFileClip(ENGINE_SOUND)
            # Loop engine sound to match video duration
            if engine.duration < duration:
                loops = int(duration / engine.duration) + 1
                from moviepy.editor import concatenate_audioclips
                engine_loops = [engine] * loops
                engine = concatenate_audioclips(engine_loops)
            # Trim to exact duration
            engine = engine.subclip(0, duration)
            # Engine at 35% volume
            audio_clips.append(engine.volumex(0.35))
            logger.info(f"Added engine sound: {ENGINE_SOUND}")
        except Exception as e:
            logger.warning(f"Could not load engine sound: {e}")
    else:
        logger.warning(f"Engine sound not found: {ENGINE_SOUND}")
    
    # 2. Add background music - pick random, loop if needed
    available_music = [m for m in MUSIC_FILES if os.path.exists(m)]
    if available_music:
        try:
            music_file = random.choice(available_music)
            music = AudioFileClip(music_file)
            # Loop music to match video duration
            if music.duration < duration:
                loops = int(duration / music.duration) + 1
                from moviepy.editor import concatenate_audioclips
                music_loops = [music] * loops
                music = concatenate_audioclips(music_loops)
            # Trim to exact duration
            music = music.subclip(0, duration)
            # Music at 20% volume (background)
            audio_clips.append(music.volumex(0.20))
            logger.info(f"Added music: {music_file}")
        except Exception as e:
            logger.warning(f"Could not load music: {e}")
    else:
        logger.warning("No music files found")
    
    if audio_clips:
        return CompositeAudioClip(audio_clips)
    return None


def create_segment(clip_path, target_duration, caption, color_hex, day_num, allow_loop=True):
    """
    Create a video segment with text overlay and audio.
    
    Args:
        clip_path: Path to source video
        target_duration: Desired duration in seconds
        caption: Text to display
        color_hex: Color for the caption text
        day_num: Day number for display
        allow_loop: If False, won't loop video (for continuous pro footage)
    
    Returns:
        Processed VideoFileClip or None on error
    """
    if not clip_path or not os.path.exists(clip_path):
        logger.error(f"Clip not found: {clip_path}")
        return None
    
    try:
        logger.info(f"Processing segment: {os.path.basename(clip_path)} -> {target_duration}s")
        
        # Load the clip
        clip = VideoFileClip(clip_path)
        
        # Handle duration - trim or loop to match target
        if clip.duration > target_duration:
            # Trim to target duration
            clip = clip.subclip(0, target_duration)
            logger.info(f"  Trimmed from {clip.duration:.1f}s to {target_duration}s")
        elif clip.duration < target_duration:
            if allow_loop:
                # Loop to fill duration
                loops_needed = int(target_duration / clip.duration) + 1
                logger.info(f"  Looping {loops_needed}x to reach {target_duration}s")
                from moviepy.editor import concatenate_videoclips
                clip = concatenate_videoclips([clip] * loops_needed)
                clip = clip.subclip(0, target_duration)
            else:
                # For pro segment: use full clip as-is, do NOT slow down
                logger.info(f"  Using full clip {clip.duration:.1f}s (no loop, no speed change)")
                # Just trim if longer, use as-is if shorter (no slowing down)
                clip = clip.subclip(0, min(clip.duration, target_duration))
        
        # Add caption text (appears briefly at start then disappears)
        try:
            # Main caption at top - only show for first 2 seconds
            text_duration = min(2.0, clip.duration)
            txt_clip = TextClip(
                caption,
                fontsize=50,
                color=color_hex,
                font='DejaVu-Sans-Bold',
                stroke_color='black',
                stroke_width=2,
                method='caption',
                size=(clip.w - 40, None)
            ).set_duration(text_duration).set_position(('center', 20))
            
            # Composite text over video
            clip = CompositeVideoClip([clip, txt_clip])
            logger.info(f"  Added text overlay (2s)")
        except Exception as e:
            logger.warning(f"  Could not add text: {e}")
        
        # Add audio
        audio = load_audio_files(clip.duration)
        if audio:
            clip = clip.set_audio(audio)
            logger.info(f"  Added audio mix")
        
        return clip
        
    except Exception as e:
        logger.error(f"Failed to process segment: {e}")
        return None


def create_triple_short(clips, strategy, output_name):
    """
    Create the 15s + 15s + 30s triple short.
    
    Structure:
    - 15s: Training (struggle/fails) - RED
    - 15s: Learning (improving) - YELLOW  
    - 30s: Pro (mastery) - GREEN
    """
    if not clips:
        logger.error("No clips provided")
        return None
    
    logger.info(f"Creating triple-short from {len(clips)} clip(s)")
    
    day = strategy.get('day', 1)
    
    # Sort clips by generation number to pick from different phases
    def get_gen_num(clip_path):
        try:
            basename = os.path.basename(clip_path)
            # Extract number from gen_00531.mp4
            num_part = basename.split('_')[1].split('.')[0]
            return int(num_part)
        except:
            return 0
    
    clips_sorted = sorted(clips, key=get_gen_num)
    
    if len(clips_sorted) == 1:
        worst = middle = best = clips_sorted[0]
        logger.info("Using single clip for all segments")
    elif len(clips_sorted) == 2:
        worst = clips_sorted[0]
        middle = best = clips_sorted[1]
        logger.info("Using 2 clips: worst and best")
    else:
        # Pick from different generation ranges for evolution effect
        # Training: first 1/3 (early gens - struggling)
        # Learning: middle 1/3 (improving)
        # Pro: last 1/3 (late gens - professional)
        
        third = len(clips_sorted) // 3
        
        # Training = early generation (worst performance)
        worst = clips_sorted[random.randint(0, max(0, third - 1))]
        
        # Learning = middle generation (improving)
        middle = clips_sorted[random.randint(third, min(len(clips_sorted) - 1, third * 2 - 1))]
        
        # Pro = late generation (best performance)
        best = clips_sorted[random.randint(third * 2, len(clips_sorted) - 1)]
        
        logger.info(f"Selected clips by generation: Training={get_gen_num(worst)}, Learning={get_gen_num(middle)}, Pro={get_gen_num(best)}")
    
    segments = []
    
    # Segment 1: Training (15s) - Red
    logger.info("Creating TRAINING segment (15s)...")
    seg1 = create_segment(worst, 15, "TRAINING 💀", "#FF4444", day)
    if seg1:
        segments.append(seg1)
    
    # Segment 2: Learning (15s) - Yellow
    logger.info("Creating LEARNING segment (15s)...")
    seg2 = create_segment(middle, 15, "LEARNING 📈", "#FFAA00", day)
    if seg2:
        segments.append(seg2)
    
    # Segment 3: Pro (30s) - Green - continuous, no looping
    logger.info("Creating PRO segment (30s)...")
    seg3 = create_segment(best, 30, "PRO LEVEL 🏆", "#44FF88", day, allow_loop=False)
    if seg3:
        segments.append(seg3)
    
    if not segments:
        logger.error("No segments were created successfully")
        return None
    
    # Concatenate all segments
    logger.info(f"Concatenating {len(segments)} segments...")
    final = concatenate_videoclips(segments, method="compose")
    
    # Add fade in/out
    final = fadein(final, 0.5)
    final = fadeout(final, 0.8)
    
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, output_name)
    
    logger.info(f"Exporting to {output_path} ({final.duration:.1f}s total)")
    
    # Export with high quality settings
    final.write_videofile(
        output_path,
        fps=30,
        codec='libx264',
        audio_codec='aac',
        audio_bitrate='192k',
        bitrate='4000k',
        preset='medium',
        threads=4,
        logger=None
    )
    
    # Cleanup
    for seg in segments:
        seg.close()
    final.close()
    
    logger.info(f"✅ Successfully created: {output_path}")
    return output_path


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("🎬 DAILY SHORTS CREATOR - PROFESSIONAL")
    logger.info("=" * 60)
    
    # Get content strategy
    content = ContentStrategy()
    strategy = content.get_today_strategy()
    
    # Get challenge info
    loader = ChallengeLoader()
    challenge = loader.get_active_challenge()
    challenge_name = challenge['name'] if challenge else "Training"
    content.update_challenge(challenge_name, strategy.get('day', 1))
    
    strategy['challenge'] = challenge_name
    
    logger.info(f"Day {strategy['day']} | Challenge: {challenge_name}")
    
    # Check for audio files
    logger.info("Checking audio files...")
    if os.path.exists(ENGINE_SOUND):
        logger.info(f"  ✓ Engine: {ENGINE_SOUND}")
    else:
        logger.warning(f"  ✗ Engine not found: {ENGINE_SOUND}")
    
    available_music = [m for m in MUSIC_FILES if os.path.exists(m)]
    logger.info(f"  ✓ Music files: {available_music}")
    
    # Get training clips
    clips = get_all_clips()
    logger.info(f"Found {len(clips)} training clip(s)")
    
    if not clips:
        logger.error("No clips found. Cannot create video.")
        return
    
    # Create the triple short
    today = datetime.now().strftime('%Y%m%d')
    output = create_triple_short(clips, strategy, f"daily_{today}.mp4")
    
    if output:
        logger.info(f"\n✅ SUCCESS: Video created at {output}")
        # Save upload info
        schedule_path = os.path.join(OUTPUT_DIR, "upload_info.txt")
        with open(schedule_path, "w") as f:
            f.write(f"Video: {output}\n")
            f.write(f"Day: {strategy['day']}\n")
            f.write(f"Challenge: {challenge_name}\n")
        logger.info(f"Upload info saved to {schedule_path}")
    else:
        logger.error("\n❌ FAILED: Could not create video")
    
    # Advance to next day
    content.advance_day()


if __name__ == "__main__":
    main()
