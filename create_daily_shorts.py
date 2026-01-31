#!/usr/bin/env python3
"""
Create daily YouTube Shorts with 15s/15s/30s structure
15s Training (struggle) + 15s Learning (progress) + 30s Pro (mastery)
"""
import os
import glob
import random
import numpy as np
from datetime import datetime
from moviepy.editor import (VideoFileClip, concatenate_videoclips, concatenate_audioclips,
                            TextClip, CompositeVideoClip, AudioFileClip, CompositeAudioClip)
from moviepy.video.fx.all import fadein, fadeout
from moviepy.audio.AudioClip import AudioArrayClip
from challenge_loader import ChallengeLoader
from content_strategy import ContentStrategy

VIDEO_DIR = "training_clips"
OUTPUT_DIR = "daily_shorts"
MUSIC_FILES = ["music.mp3", "music2.mp3", "music3.mp3"]

def generate_engine_sound(duration, fps=44100):
    """Generate synthetic engine sound (since training clips have no audio)"""
    try:
        t = np.linspace(0, duration, int(duration * fps))
        # Engine rumble: low frequency with modulation
        base_freq = 80  # Hz
        rumble = np.sin(2 * np.pi * base_freq * t) * 0.3
        # Add higher harmonics
        harmonic = np.sin(2 * np.pi * base_freq * 2 * t) * 0.15
        # Add noise for texture
        noise = np.random.normal(0, 0.05, len(t))
        # Combine
        audio = rumble + harmonic + noise
        # Fade in/out
        fade_len = int(0.1 * fps)
        audio[:fade_len] *= np.linspace(0, 1, fade_len)
        audio[-fade_len:] *= np.linspace(1, 0, fade_len)
        # Stereo
        audio = np.array([audio, audio]).T
        return AudioArrayClip(audio, fps=fps)
    except:
        return None

def get_all_clips():
    """Get all mp4 clips from training_clips"""
    pattern = os.path.join(VIDEO_DIR, "**", "*.mp4")
    clips = glob.glob(pattern, recursive=True)
    
    def get_gen(filename):
        try:
            return int(os.path.basename(filename).split('_')[1].split('.')[0])
        except:
            return 0
    
    return sorted(clips, key=get_gen)

def analyze_clip_performance(video_path):
    """Score clip by performance (duration = survival time)"""
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration
        clip.close()
        return duration
    except:
        return 0

def add_caption(clip, text, position='top', fontsize=60, color='#FFFFFF'):
    """Add clean caption text"""
    try:
        txt = TextClip(
            text,
            fontsize=fontsize,
            color=color,
            font='Arial-Bold',
            stroke_color='black',
            stroke_width=2,
            method='caption',
            size=(clip.w - 80, None)
        ).set_duration(clip.duration)
        
        if position == 'top':
            txt = txt.set_position(('center', 30))
        elif position == 'bottom':
            txt = txt.set_position(('center', clip.h - 100))
        else:
            txt = txt.set_position('center')
        
        return CompositeVideoClip([clip, txt])
    except:
        return clip

def create_segment(clip_path, duration, caption, color, add_engine=True):
    """Create a video segment with audio"""
    if not clip_path or not os.path.exists(clip_path):
        return None
    
    try:
        clip = VideoFileClip(clip_path)
        
        # Trim/pad to exact duration
        if clip.duration > duration:
            clip = clip.subclip(0, duration)
        elif clip.duration < duration:
            # Loop if too short
            loops = int(duration / clip.duration) + 1
            clip = concatenate_videoclips([clip] * loops).subclip(0, duration)
        
        # Add caption
        clip = add_caption(clip, caption, color=color)
        
        # Add audio
        audio_layers = []
        
        # Engine sound
        if add_engine:
            engine = generate_engine_sound(duration)
            if engine:
                audio_layers.append(engine.volumex(0.25))
        
        # Background music
        music_file = random.choice([m for m in MUSIC_FILES if os.path.exists(m)])
        if music_file and os.path.exists(music_file):
            try:
                music = AudioFileClip(music_file).subclip(0, duration)
                audio_layers.append(music.volumex(0.15))
            except:
                pass
        
        if audio_layers:
            mixed = CompositeAudioClip(audio_layers)
            clip = clip.set_audio(mixed)
        
        return clip
        
    except Exception as e:
        print(f"⚠️ Segment error: {e}")
        return None

def create_triple_short(strategy, clips, output_name):
    """
    Create the 15s/15s/30s structure:
    - 15s: Training (struggle/chaos)
    - 15s: Learning (progress/improving)  
    - 30s: Pro (mastery/perfection)
    """
    if len(clips) < 3:
        print(f"❌ Need 3+ clips, got {len(clips)}")
        return None
    
    print(f"🎬 Creating Triple-Short: {output_name}")
    
    # Sort by performance
    scored = [(c, analyze_clip_performance(c)) for c in clips]
    scored.sort(key=lambda x: x[1])
    
    n = len(scored)
    training_clip = scored[0][0]  # Worst
    learning_clip = scored[n//2][0]  # Middle
    pro_clip = scored[-1][0]  # Best
    
    day = strategy['day']
    challenge = strategy['challenge']
    
    # Create segments
    segments = []
    
    # 1. TRAINING (15s) - Red, chaotic
    s1 = create_segment(
        training_clip, 15,
        f"🎓 TRAINING - Day {day}",
        '#FF4444',
        add_engine=True
    )
    if s1: segments.append(s1)
    
    # 2. LEARNING (15s) - Yellow, improving
    s2 = create_segment(
        learning_clip, 15,
        f"📈 LEARNING - Day {day}",
        '#FFAA00',
        add_engine=True
    )
    if s2: segments.append(s2)
    
    # 3. PRO (30s) - Green, mastery
    s3 = create_segment(
        pro_clip, 30,
        f"🏆 PRO LEVEL - Day {day}",
        '#44FF88',
        add_engine=True
    )
    if s3: segments.append(s3)
    
    if not segments:
        return None
    
    # Combine
    final = concatenate_videoclips(segments, method="compose")
    final = fadein(final, 0.5)
    final = fadeout(final, 1.0)
    
    # Export
    output_path = os.path.join(OUTPUT_DIR, output_name)
    final.write_videofile(
        output_path,
        fps=30,
        codec='libx264',
        audio_codec='aac',
        preset='medium',
        threads=4,
        logger=None
    )
    
    # Cleanup
    for s in segments:
        s.close()
    final.close()
    
    print(f"✅ Created: {output_path} ({final.duration}s)")
    return output_path

def main():
    print("=" * 60)
    print("🎬 TRIPLE-SHORT CREATOR (15s+15s+30s)")
    print("=" * 60)
    
    # Get strategy
    content = ContentStrategy()
    strategy = content.get_today_strategy()
    
    # Get challenge
    loader = ChallengeLoader()
    challenge = loader.get_active_challenge()
    challenge_name = challenge['name'] if challenge else "Training"
    content.update_challenge(challenge_name, strategy['day'])
    
    strategy['challenge'] = challenge_name
    
    print(f"\n📅 Day {strategy['day']} | {challenge_name}")
    
    # Get clips
    clips = get_all_clips()
    if len(clips) < 3:
        print(f"❌ Only {len(clips)} clips, need 3+")
        return
    
    print(f"📹 {len(clips)} clips available")
    
    # Create the triple-short
    today = datetime.now().strftime('%Y%m%d')
    output = create_triple_short(strategy, clips, f"triple_{today}.mp4")
    
    if output:
        # Also create individual shorts for variety
        print("\n🎬 Creating individual shorts...")
        
        scored = [(c, analyze_clip_performance(c)) for c in clips]
        scored.sort(key=lambda x: x[1])
        
        shorts = []
        
        # Training short (worst)
        s = create_segment(scored[0][0], 15, 
                          f"Training Day {strategy['day']} 💀", '#FF6666')
        if s:
            s.write_videofile(os.path.join(OUTPUT_DIR, f"training_{today}.mp4"),
                            fps=30, codec='libx264', audio_codec='aac',
                            preset='fast', logger=None)
            shorts.append(("09:00", "Training"))
        
        # Pro short (best)
        s = create_segment(scored[-1][0], 30,
                          f"Pro Level Day {strategy['day']} 🏆", '#66FF88')
        if s:
            s.write_videofile(os.path.join(OUTPUT_DIR, f"pro_{today}.mp4"),
                            fps=30, codec='libx264', audio_codec='aac',
                            preset='fast', logger=None)
            shorts.append(("21:00", "Pro"))
        
        print(f"\n✅ Created {len(shorts)+1} videos:")
        print(f"  📁 triple_{today}.mp4 (60s full)")
        for time, name in shorts:
            print(f"  📁 {name}_{today}.mp4 ({time})")
    
    content.advance_day()

if __name__ == "__main__":
    main()
