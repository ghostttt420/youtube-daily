\#!/usr/bin/env python3
"""
Create daily YouTube Shorts - CLEAN VERSION with better audio, less text
"""
import os
import glob
import random
from datetime import datetime
from moviepy.editor import (VideoFileClip, concatenate_videoclips, concatenate_audioclips,
                            TextClip, CompositeVideoClip, AudioFileClip, CompositeAudioClip)
from moviepy.video.fx.all import fadein, fadeout
from moviepy.audio.fx.all import volumex
from challenge_loader import ChallengeLoader
from content_strategy import ContentStrategy

VIDEO_DIR = "training_clips"
OUTPUT_DIR = "daily_shorts"
MUSIC_FILES = ["music.mp3", "music2.mp3", "music3.mp3"]
ENGINE_SOUND = "engine.mp3"

def get_all_clips():
    """Get all mp4 clips from training_clips and subdirectories"""
    pattern = os.path.join(VIDEO_DIR, "**", "*.mp4")
    clips = glob.glob(pattern, recursive=True)
    
    def get_gen(filename):
        try:
            return int(os.path.basename(filename).split('_')[1].split('.')[0])
        except:
            return 0
    
    return sorted(clips, key=get_gen)

def analyze_clip_performance(video_path):
    """Analyze clip quality - higher score = better performance"""
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration
        clip.close()
        return duration
    except:
        return 0

def mix_audio_with_engine(video_clip, music_vol=0.15, engine_vol=0.3):
    """Mix background music with engine sound"""
    try:
        # Pick random music
        music_file = random.choice([m for m in MUSIC_FILES if os.path.exists(m)])
        
        audio_layers = []
        
        # Add music
        if music_file and os.path.exists(music_file):
            music = AudioFileClip(music_file).subclip(0, min(video_clip.duration, 60))
            music = music.volumex(music_vol)
            audio_layers.append(music)
        
        # Add engine sound (looped)
        if os.path.exists(ENGINE_SOUND):
            engine = AudioFileClip(ENGINE_SOUND)
            # Loop engine sound to match video duration
            loops_needed = int(video_clip.duration / engine.duration) + 1
            engine_looped = concatenate_audioclips([engine] * loops_needed)
            engine_looped = engine_looped.subclip(0, video_clip.duration)
            engine_looped = engine_looped.volumex(engine_vol)
            audio_layers.append(engine_looped)
        
        if audio_layers:
            mixed = CompositeAudioClip(audio_layers)
            return video_clip.set_audio(mixed)
        
        return video_clip
    except Exception as e:
        print(f"⚠️ Audio mixing failed: {e}")
        return video_clip

def add_minimal_text(clip, hook_text, day_info, phase):
    """Add minimal text - just hook and day info"""
    try:
        # Color based on phase (subtle)
        colors = {
            "INTRO": "#FF6666",
            "LEARNING": "#FFAA44", 
            "IMPROVING": "#44DDFF",
            "MASTERY": "#66FF88",
            "FINALE": "#FFDD44"
        }
        color = colors.get(phase, "#FFFFFF")
        
        # Main hook - top, bold
        txt = TextClip(
            hook_text,
            fontsize=65,
            color=color,
            font='DejaVu-Sans-Bold',
            stroke_color='black',
            stroke_width=2,
            method='caption',
            size=(clip.w - 60, None)
        ).set_duration(clip.duration).set_position(('center', 40))
        
        # Day info - bottom, small
        day = TextClip(
            day_info,
            fontsize=35,
            color='#AAAAAA',
            font='DejaVu-Sans',
            stroke_color='black',
            stroke_width=1
        ).set_duration(clip.duration).set_position(('center', clip.h - 80))
        
        return CompositeVideoClip([clip, txt, day])
    except Exception as e:
        print(f"⚠️ Text overlay failed: {e}")
        return clip

def create_clean_short(strategy, clip_path, hook_text, output_name):
    """Create a clean, minimal short"""
    if not clip_path or not os.path.exists(clip_path):
        return None
    
    try:
        print(f"🎬 Creating: {output_name}")
        
        # Load clip
        clip = VideoFileClip(clip_path)
        
        # Trim to max 45 seconds (Shorts optimal)
        if clip.duration > 45:
            clip = clip.subclip(0, 45)
        
        # Add minimal text
        day_info = f"Day {strategy['day']} • {strategy['challenge']}"
        clip = add_minimal_text(clip, hook_text, day_info, strategy['phase'])
        
        # Mix audio with engine
        clip = mix_audio_with_engine(clip)
        
        # Subtle fade
        clip = fadein(clip, 0.5)
        clip = fadeout(clip, 0.5)
        
        # Export
        output_path = os.path.join(OUTPUT_DIR, output_name)
        clip.write_videofile(
            output_path,
            fps=30,
            codec='libx264',
            audio_codec='aac',
            preset='fast',
            threads=4,
            logger=None
        )
        
        clip.close()
        print(f"✅ Created: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"❌ Failed to create {output_name}: {e}")
        return None

def main():
    print("=" * 60)
    print("🎬 DAILY SHORTS CREATOR (Clean Edition)")
    print("=" * 60)
    
    # Get content strategy
    content = ContentStrategy()
    strategy = content.get_today_strategy()
    
    print(f"\n📅 Day {strategy['day']} | {strategy['phase']} | {strategy['videos_per_day']} videos")
    
    # Get challenge
    loader = ChallengeLoader()
    challenge = loader.get_active_challenge()
    challenge_name = challenge['name'] if challenge else "AI Training"
    content.update_challenge(challenge_name, strategy['day'])
    
    # Get clips
    all_clips = get_all_clips()
    if len(all_clips) < 1:
        print("❌ No clips found")
        return
    
    print(f"📹 {len(all_clips)} clips available")
    
    # Score clips
    scored = [(c, analyze_clip_performance(c)) for c in all_clips]
    scored.sort(key=lambda x: x[1])
    
    n = len(scored)
    worst = scored[0][0] if scored else None
    middle = scored[n//2][0] if n > 1 else worst
    best = scored[-1][0] if scored else worst
    
    # Create videos based on count
    shorts = []
    today = datetime.now().strftime('%Y%m%d')
    
    hooks = strategy['theme']
    
    if strategy['videos_per_day'] >= 3:
        # Morning - struggle
        h = content.format_hook("The struggle is real 💀", challenge_name)
        s = create_clean_short(strategy, worst, h, f"01_morning_{today}.mp4")
        if s: shorts.append(("09:00", s, h))
        
        # Afternoon - progress
        h = content.format_hook("Getting better... 📈", challenge_name)
        s = create_clean_short(strategy, middle, h, f"02_afternoon_{today}.mp4")
        if s: shorts.append(("15:00", s, h))
        
        # Evening - mastery
        h = content.format_hook("Nailed it! 🎯", challenge_name)
        s = create_clean_short(strategy, best, h, f"03_evening_{today}.mp4")
        if s: shorts.append(("21:00", s, h))
    
    elif strategy['videos_per_day'] == 2:
        # Compare worst vs best
        h1 = content.format_hook("Then vs Now 👀", challenge_name)
        s1 = create_clean_short(strategy, worst, h1, f"01_then_{today}.mp4")
        if s1: shorts.append(("12:00", s1, h1))
        
        h2 = content.format_hook("This is insane! 🤯", challenge_name)
        s2 = create_clean_short(strategy, best, h2, f"02_now_{today}.mp4")
        if s2: shorts.append(("20:00", s2, h2))
    
    else:
        # Just best
        h = content.format_hook("Perfect run ✨", challenge_name)
        s = create_clean_short(strategy, best, h, f"daily_{today}.mp4")
        if s: shorts.append(("19:00", s, h))
    
    # Summary
    print(f"\n✅ Created {len(shorts)} shorts")
    for time, path, title in shorts:
        print(f"  {time} | {title}")
    
    # Save schedule
    with open(os.path.join(OUTPUT_DIR, "upload_schedule.txt"), "w") as f:
        for time, path, title in shorts:
            f.write(f"{time}|{path}|{title}\n")
    
    content.advance_day()

if __name__ == "__main__":
    main()
