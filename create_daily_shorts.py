#!/usr/bin/env python3
"""
Create daily YouTube Shorts - FIXED VERSION
Works with 1+ clips, adds proper audio
"""
import os
import glob
import random
import math
from datetime import datetime
from moviepy.editor import (VideoFileClip, concatenate_videoclips, concatenate_audioclips,
                            TextClip, CompositeVideoClip, AudioFileClip, CompositeAudioClip,
                            AudioClip)
from moviepy.video.fx.all import fadein, fadeout
from moviepy.audio.AudioClip import AudioArrayClip
import numpy as np
from challenge_loader import ChallengeLoader
from content_strategy import ContentStrategy

VIDEO_DIR = "training_clips"
OUTPUT_DIR = "daily_shorts"
MUSIC_FILES = ["music.mp3", "music2.mp3", "music3.mp3"]

def generate_engine_sound(duration, fps=44100):
    """Generate synthetic engine rumble sound"""
    try:
        t = np.linspace(0, duration, int(duration * fps), False)
        
        # Base engine rumble (low frequency)
        base_freq = 75
        rumble = np.sin(2 * np.pi * base_freq * t) * 0.4
        
        # Higher rev sound
        rev = np.sin(2 * np.pi * base_freq * 2 * t) * 0.2
        
        # Random noise for texture
        noise = np.random.uniform(-0.1, 0.1, len(t))
        
        # Combine
        audio = rumble + rev + noise
        
        # Fade in/out
        fade_samples = int(0.1 * fps)
        if len(audio) > fade_samples * 2:
            audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
            audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)
        
        # Clip to prevent distortion
        audio = np.clip(audio, -0.8, 0.8)
        
        # Make stereo
        stereo = np.vstack((audio, audio)).T
        
        return AudioArrayClip(stereo, fps=fps)
    except Exception as e:
        print(f"⚠️ Engine sound generation failed: {e}")
        return None

def get_all_clips():
    """Get all mp4 clips"""
    pattern = os.path.join(VIDEO_DIR, "**", "*.mp4")
    clips = glob.glob(pattern, recursive=True)
    
    def get_gen(filename):
        try:
            return int(os.path.basename(filename).split('_')[1].split('.')[0])
        except:
            return 0
    
    return sorted(clips, key=get_gen)

def analyze_clip(video_path):
    """Get clip duration as quality metric"""
    try:
        clip = VideoFileClip(video_path)
        dur = clip.duration
        clip.close()
        return dur
    except:
        return 0

def add_text(clip, main_text, sub_text, color):
    """Add clean text overlay"""
    try:
        # Main text
        txt = TextClip(
            main_text,
            fontsize=55,
            color=color,
            font='Arial-Bold',
            stroke_color='black',
            stroke_width=2,
            method='caption',
            size=(clip.w - 60, None)
        ).set_duration(clip.duration).set_position(('center', 25))
        
        # Sub text
        sub = TextClip(
            sub_text,
            fontsize=30,
            color='#CCCCCC',
            font='Arial',
            stroke_color='black',
            stroke_width=1
        ).set_duration(clip.duration).set_position(('center', clip.h - 60))
        
        return CompositeVideoClip([clip, txt, sub])
    except Exception as e:
        print(f"⚠️ Text error: {e}")
        return clip

def process_clip(clip_path, duration, caption, color, add_engine=True):
    """Process a single clip with audio and text"""
    if not clip_path or not os.path.exists(clip_path):
        return None
    
    try:
        # Load and trim/pad
        clip = VideoFileClip(clip_path)
        
        if clip.duration > duration:
            clip = clip.subclip(0, duration)
        elif clip.duration < duration:
            # Loop to fill duration
            loops = int(duration / max(clip.duration, 1)) + 1
            clip = concatenate_videoclips([clip] * loops).subclip(0, duration)
        
        # Add text
        clip = add_text(clip, caption, "", color)
        
        # Add audio
        audio_clips = []
        
        if add_engine:
            engine = generate_engine_sound(clip.duration)
            if engine:
                audio_clips.append(engine.volumex(0.3))
        
        # Background music
        music_file = None
        for m in MUSIC_FILES:
            if os.path.exists(m):
                music_file = m
                break
        
        if music_file:
            try:
                music = AudioFileClip(music_file).subclip(0, clip.duration)
                audio_clips.append(music.volumex(0.15))
            except:
                pass
        
        if audio_clips:
            mixed = CompositeAudioClip(audio_clips)
            clip = clip.set_audio(mixed)
        
        return clip
        
    except Exception as e:
        print(f"⚠️ Clip processing error: {e}")
        return None

def create_triple_short(clips, strategy, output_name):
    """Create 15s + 15s + 30s video"""
    
    if not clips:
        print("❌ No clips available")
        return None
    
    print(f"🎬 Creating triple-short with {len(clips)} clip(s)")
    
    day = strategy['day']
    challenge = strategy['challenge']
    
    # If only 1 clip, use it for all segments
    # If 2+ clips, use worst/best
    # If 3+ clips, use worst/middle/best
    
    if len(clips) == 1:
        worst = middle = best = clips[0]
    elif len(clips) == 2:
        scored = [(c, analyze_clip(c)) for c in clips]
        scored.sort(key=lambda x: x[1])
        worst = scored[0][0]
        middle = best = scored[1][0]
    else:
        scored = [(c, analyze_clip(c)) for c in clips]
        scored.sort(key=lambda x: x[1])
        worst = scored[0][0]
        middle = scored[len(scored)//2][0]
        best = scored[-1][0]
    
    segments = []
    
    # Training segment (15s) - RED
    s1 = process_clip(worst, 15, f"🎓 TRAINING Day {day}", '#FF4444')
    if s1: segments.append(s1)
    
    # Learning segment (15s) - YELLOW  
    s2 = process_clip(middle, 15, f"📈 LEARNING Day {day}", '#FFAA00')
    if s2: segments.append(s2)
    
    # Pro segment (30s) - GREEN
    s3 = process_clip(best, 30, f"🏆 PRO Day {day}", '#44FF88')
    if s3: segments.append(s3)
    
    if not segments:
        return None
    
    # Combine
    final = concatenate_videoclips(segments)
    final = fadein(final, 0.3)
    final = fadeout(final, 0.5)
    
    # Export
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, output_name)
    
    print(f"💾 Exporting {output_path} ({final.duration:.1f}s)")
    
    final.write_videofile(
        output_path,
        fps=30,
        codec='libx264',
        audio_codec='aac',
        bitrate='3000k',
        preset='medium',
        threads=4,
        logger=None
    )
    
    # Cleanup
    for s in segments:
        s.close()
    final.close()
    
    print(f"✅ Created: {output_path}")
    return output_path

def main():
    print("=" * 60)
    print("🎬 DAILY SHORTS CREATOR")
    print("=" * 60)
    
    # Get strategy
    content = ContentStrategy()
    strategy = content.get_today_strategy()
    
    loader = ChallengeLoader()
    challenge = loader.get_active_challenge()
    challenge_name = challenge['name'] if challenge else "Training"
    content.update_challenge(challenge_name, strategy['day'])
    
    strategy['challenge'] = challenge_name
    
    print(f"\n📅 Day {strategy['day']} | {challenge_name}")
    
    # Get clips
    clips = get_all_clips()
    print(f"📹 Found {len(clips)} clip(s)")
    
    if not clips:
        print("❌ No clips to process")
        return
    
    # Create triple short
    today = datetime.now().strftime('%Y%m%d')
    output = create_triple_short(clips, strategy, f"daily_{today}.mp4")
    
    if output:
        print(f"\n✅ Success! Video created.")
    else:
        print("\n❌ Failed to create video")
    
    content.advance_day()

if __name__ == "__main__":
    main()
