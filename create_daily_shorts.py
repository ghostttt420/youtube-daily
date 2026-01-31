#!/usr/bin/env python3
"""
Create daily YouTube Shorts with EVOLVING content strategy.
Content changes based on training phase (Intro → Learning → Improving → Mastery)
"""
import os
import glob
import random
from datetime import datetime
from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip, AudioFileClip
from moviepy.video.fx.all import speedx, fadein, fadeout
from challenge_loader import ChallengeLoader
from content_strategy import ContentStrategy

VIDEO_DIR = "training_clips"
OUTPUT_DIR = "daily_shorts"
MUSIC_FILES = ["music.mp3", "music2.mp3", "music3.mp3", "engine.mp3"]

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def get_all_clips():
    """Get all mp4 clips from training_clips and subdirectories"""
    pattern = os.path.join(VIDEO_DIR, "**", "*.mp4")
    clips = glob.glob(pattern, recursive=True)
    
    def get_gen(filename):
        basename = os.path.basename(filename)
        try:
            return int(basename.split('_')[1].split('.')[0])
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

def get_clip_style_editing(phase, clip, text):
    """Apply different editing styles based on content phase"""
    
    if phase == "INTRO":
        # Chaotic: Fast, shaky, red tints
        clip = speedx(clip, 1.2)  # Speed up slightly
        text_color = '#FF4444'
        stroke_color = '#000000'
        
    elif phase == "LEARNING":
        # Progressive: Normal speed, orange
        text_color = '#FFAA00'
        stroke_color = '#000000'
        
    elif phase == "IMPROVING":
        # Highlight: Slight slow-mo on good parts
        text_color = '#00DDFF'
        stroke_color = '#000000'
        
    elif phase in ["MASTERY", "FINALE"]:
        # Cinematic: Smooth, green/cyan
        text_color = '#00FF88'
        stroke_color = '#000000'
        
    else:
        text_color = '#FFFFFF'
        stroke_color = '#000000'
    
    return clip, text_color, stroke_color

def add_text_overlay(clip, text, position='top', fontsize=70, 
                     color='white', stroke_color='black', stroke_width=3):
    """Add styled text to a clip"""
    try:
        txt_clip = TextClip(
            text,
            fontsize=fontsize,
            color=color,
            font='DejaVu-Sans-Bold',
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            method='caption',
            size=(clip.w - 100, None)
        ).set_duration(clip.duration)
        
        if position == 'top':
            txt_clip = txt_clip.set_position(('center', 50))
        elif position == 'bottom':
            txt_clip = txt_clip.set_position(('center', clip.h - 150))
        else:
            txt_clip = txt_clip.set_position('center')
        
        return CompositeVideoClip([clip, txt_clip])
    except Exception as e:
        print(f"⚠️ Text overlay failed: {e}")
        return clip

def create_short(strategy, clips, hook_text, output_name, is_highlight=False):
    """Create a single YouTube Short with phase-appropriate editing"""
    
    if not clips:
        print(f"❌ No clips available for {output_name}")
        return None
    
    phase = strategy['phase']
    print(f"🎬 Creating [{phase}]: {output_name}")
    
    # Pick the best clip
    if is_highlight:
        # Pick best performing clip
        scored = [(c, analyze_clip_performance(c)) for c in clips]
        scored.sort(key=lambda x: x[1], reverse=True)
        selected_clips = [scored[0][0]] if scored else clips[:1]
    else:
        # Pick representative clips
        selected_clips = clips[:1]
    
    # Load and process
    processed_clips = []
    for clip_path in selected_clips:
        try:
            clip = VideoFileClip(clip_path)
            
            # Apply phase-specific editing
            clip, text_color, stroke_color = get_clip_style_editing(
                phase, clip, hook_text
            )
            
            # Trim based on phase
            if phase == "INTRO":
                max_duration = 10  # Quick chaos
            elif phase == "MASTERY":
                max_duration = 20  # Savor the skill
            else:
                max_duration = 15
            
            if clip.duration > max_duration:
                clip = clip.subclip(0, max_duration)
            
            processed_clips.append((clip, text_color, stroke_color))
        except Exception as e:
            print(f"⚠️ Failed to load {clip_path}: {e}")
    
    if not processed_clips:
        return None
    
    # Concatenate
    final = concatenate_videoclips([c[0] for c in processed_clips], method="compose")
    text_color = processed_clips[0][1]
    stroke_color = processed_clips[0][2]
    
    # Keep under 60s
    if final.duration > 58:
        final = final.subclip(0, 58)
    
    # Add text overlays with phase colors
    final = add_text_overlay(final, hook_text, position='top', 
                            color=text_color, fontsize=80,
                            stroke_color=stroke_color, stroke_width=4)
    
    # Add day info at bottom
    day_info = f"Day {strategy['day']} • {strategy['challenge']}"
    final = add_text_overlay(final, day_info, position='bottom',
                            color='#CCCCCC', fontsize=40,
                            stroke_color='#000000', stroke_width=2)
    
    # Add music based on phase
    music_file = random.choice([m for m in MUSIC_FILES if os.path.exists(m)])
    if music_file and os.path.exists(music_file):
        try:
            audio = AudioFileClip(music_file).subclip(0, final.duration)
            # Adjust volume based on phase
            if phase == "INTRO":
                audio = audio.volumex(0.35)  # Louder for chaos
            elif phase == "MASTERY":
                audio = audio.volumex(0.20)  # Subtle for focus
            else:
                audio = audio.volumex(0.25)
            final = final.set_audio(audio)
        except:
            pass
    
    # Phase-specific transitions
    if phase in ["MASTERY", "FINALE"]:
        final = fadein(final, 1.0)  # Dramatic fade
        final = fadeout(final, 1.5)
    else:
        final = fadein(final, 0.3)
        final = fadeout(final, 0.5)
    
    # Export
    output_path = os.path.join(OUTPUT_DIR, output_name)
    print(f"💾 Exporting: {output_path}")
    
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
    for clip, _, _ in processed_clips:
        clip.close()
    final.close()
    
    print(f"✅ Created: {output_path}")
    return output_path

def main():
    print("=" * 60)
    print("🎬 EVOLVING DAILY SHORTS CREATOR")
    print("=" * 60)
    
    # Get content strategy
    content = ContentStrategy()
    strategy = content.get_today_strategy()
    
    print(f"\n📅 Today is Day {strategy['day']}")
    print(f"🎬 Content Phase: {strategy['phase']} - {strategy['theme']}")
    print(f"🎯 Videos to create: {strategy['videos_per_day']}")
    print(f"🎨 Editing Style: {strategy['style']}")
    
    # Get challenge info
    loader = ChallengeLoader()
    challenge = loader.get_active_challenge()
    challenge_name = challenge['name'] if challenge else "AI Training"
    
    # Update strategy with challenge
    content.update_challenge(challenge_name, strategy.get('day', 1))
    
    # Get all clips
    all_clips = get_all_clips()
    print(f"\n📹 Found {len(all_clips)} training clips")
    
    if len(all_clips) < 1:
        print("❌ Not enough clips")
        return
    
    # Categorize clips by performance
    scored = [(c, analyze_clip_performance(c)) for c in all_clips]
    scored.sort(key=lambda x: x[1])  # Worst first
    
    n = len(scored)
    struggle = scored[:n//3]
    progress = scored[n//3:2*n//3]
    mastery = scored[2*n//3:]
    
    print(f"📊 Categorized: {len(struggle)} struggle, {len(progress)} progress, {len(mastery)} mastery")
    
    # Get hook
    hook_template = strategy['hook_template']
    hook = content.format_hook(hook_template, challenge_name)
    
    # Create videos based on phase
    shorts_created = []
    today_str = datetime.now().strftime('%Y%m%d')
    
    if strategy['videos_per_day'] >= 3:
        # INTRO/LEARNING: 3 videos (struggle/progress/mastery arc)
        
        # Morning: Struggle (worst)
        if struggle:
            s = create_short(
                strategy, [c[0] for c in struggle[:3]], 
                hook, f"01_morning_{today_str}.mp4", is_highlight=False
            )
            if s:
                shorts_created.append(("09:00", s, f"💀 The Struggle - Day {strategy['day']}"))
        
        # Afternoon: Progress (middle)
        if progress:
            hook2 = content.format_hook(random.choice(content.PHASES[strategy['phase']]['hooks']), challenge_name)
            s = create_short(
                strategy, [c[0] for c in progress[:3]],
                hook2, f"02_afternoon_{today_str}.mp4", is_highlight=False
            )
            if s:
                shorts_created.append(("15:00", s, f"📈 Making Progress - Day {strategy['day']}"))
        
        # Evening: Mastery (best)
        if mastery:
            hook3 = content.format_hook(random.choice(content.PHASES[strategy['phase']]['hooks']), challenge_name)
            s = create_short(
                strategy, [c[0] for c in mastery[-3:]],  # Best of best
                hook3, f"03_evening_{today_str}.mp4", is_highlight=True
            )
            if s:
                shorts_created.append(("21:00", s, f"🏆 Mastery - Day {strategy['day']}"))
    
    elif strategy['videos_per_day'] == 2:
        # IMPROVING: 2 videos (progress comparison)
        
        # Morning: Yesterday vs Today comparison
        if len(all_clips) >= 2:
            yesterday = all_clips[0]  # First clip of batch
            today_best = mastery[-1][0] if mastery else all_clips[-1]
            
            s = create_short(
                strategy, [yesterday, today_best],
                f"Day {strategy['day']} improvement 📈", 
                f"01_comparison_{today_str}.mp4", is_highlight=True
            )
            if s:
                shorts_created.append(("12:00", s, f"📈 Getting Better - Day {strategy['day']}"))
        
        # Evening: Best of today
        if mastery:
            s = create_short(
                strategy, [mastery[-1][0]],
                "This is INSANE 🤯",
                f"02_highlight_{today_str}.mp4", is_highlight=True
            )
            if s:
                shorts_created.append(("20:00", s, f"🔥 Best Moment - Day {strategy['day']}"))
    
    else:
        # MASTERY/FINALE: 1 highlight video
        if mastery:
            s = create_short(
                strategy, [mastery[-1][0]],
                hook, f"daily_highlight_{today_str}.mp4", is_highlight=True
            )
            if s:
                shorts_created.append(("19:00", s, f"✨ Day {strategy['day']} - {challenge_name}"))
    
    # Summary
    print("\n" + "=" * 60)
    print("📅 TODAY'S UPLOAD SCHEDULE")
    print("=" * 60)
    for time, path, title in shorts_created:
        print(f"{time} | {title}")
        print(f"       📁 {os.path.basename(path)}")
    
    print(f"\n✅ Created {len(shorts_created)} shorts for Day {strategy['day']}!")
    
    # Save for workflow
    with open(os.path.join(OUTPUT_DIR, "upload_schedule.txt"), "w") as f:
        for time, path, title in shorts_created:
            f.write(f"{time}|{path}|{title}\n")
    
    # Advance to next day
    content.advance_day()

if __name__ == "__main__":
    main()
