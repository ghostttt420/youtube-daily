import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

import glob
import json
from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip, AudioFileClip, CompositeAudioClip
from moviepy.video.fx.all import speedx, fadein, fadeout
from challenge_loader import ChallengeLoader

VIDEO_DIR = "training_clips"
OUTPUT_DIR = "final_shorts"
MUSIC_FILE = "assets/music.mp3"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def add_text_overlay(clip, text, position='top', fontsize=80, color='white', bg_color='black'):
    """Add text overlay to a clip"""
    
    # Position mapping
    positions = {
        'top': ('center', 50),
        'bottom': ('center', clip.h - 150),
        'center': ('center', 'center')
    }
    
    try:
        txt_clip = TextClip(
            text, 
            fontsize=fontsize, 
            color=color,
            font='DejaVu-Sans-Bold',
            stroke_color=bg_color,
            stroke_width=3,
            method='caption',
            size=(clip.w - 100, None)
        )
        
        txt_clip = txt_clip.set_position(positions.get(position, 'top')).set_duration(clip.duration)
        
        return CompositeVideoClip([clip, txt_clip])
    except Exception as e:
        print(f"⚠️  Text overlay error: {e}")
        return clip

def create_challenge_short(challenge):
    """
    Create a 60-second short for a completed challenge
    Shows: Struggle (10s) → Learning (10s) → Mastery (40s)
    """
    
    challenge_id = challenge['id']
    challenge_name = challenge['name']
    start_gen = challenge['start_gen']
    end_gen = challenge['end_gen']
    
    print(f"\n🎬 Creating short for: {challenge_name}")
    print(f"📊 Gen Range: {start_gen} → {end_gen}")
    
    clips = []
    
    # Helper function to find clip using challenge loader
    def find_clip(gen):
        challenge_loader = ChallengeLoader()
        return challenge_loader.get_clip_for_generation(gen)
    
    # 1. STRUGGLE (First gen of challenge) - 10 seconds
    struggle_file = find_clip(start_gen)
    if struggle_file and os.path.exists(struggle_file):
        print(f"📹 Loading struggle clip: Gen {start_gen}")
        struggle = VideoFileClip(struggle_file)
        struggle_duration = min(15, struggle.duration)
        struggle = struggle.subclip(0, struggle_duration)
        struggle = speedx(struggle, 1.5)  # Speed up to ~10s
        struggle = add_text_overlay(struggle, f"NEW: {challenge_name.upper()}", position='top', color='red')
        struggle = add_text_overlay(struggle, f"Gen {start_gen} - First Attempt", position='bottom', fontsize=60, color='yellow')
        clips.append(struggle)
    else:
        print(f"⚠️  Struggle clip not found for Gen {start_gen}")
    
    # 2. LEARNING (Mid-point) - 10 seconds
    mid_gen = (start_gen + end_gen) // 2
    # Find available generations in challenge range
    challenge_loader = ChallengeLoader()
    available_clips = challenge_loader.get_clips_for_challenge(challenge_id)
    
    if available_clips:
        # Extract generation numbers from filenames
        available_gens = []
        for clip_file in available_clips:
            gen_num = int(os.path.basename(clip_file).split('_')[1].split('.')[0])
            if start_gen <= gen_num <= end_gen:
                available_gens.append(gen_num)
        
        if available_gens:
            closest_mid = min(available_gens, key=lambda x: abs(x - mid_gen))
            learning_file = challenge_loader.get_clip_for_generation(closest_mid)
            
            if learning_file and os.path.exists(learning_file):
                print(f"📹 Loading learning clip: Gen {closest_mid}")
                learning = VideoFileClip(learning_file)
                learning_duration = min(14, learning.duration)
                learning = learning.subclip(0, learning_duration)
                learning = speedx(learning, 1.4)  # Speed up to ~10s
                learning = add_text_overlay(learning, f"Gen {closest_mid} - Improving...", position='bottom', fontsize=60, color='yellow')
                clips.append(learning)
            else:
                print(f"⚠️  Learning clip not found: Gen {closest_mid}")
        else:
            print(f"⚠️  No clips found in challenge range {start_gen}-{end_gen}")
    else:
        print(f"⚠️  No clips found for challenge {challenge_id}")
    
    # 3. MASTERY (Last gen of challenge) - 40 seconds
    mastery_file = find_clip(end_gen)
    if mastery_file and os.path.exists(mastery_file):
        print(f"📹 Loading mastery clip: Gen {end_gen}")
        mastery = VideoFileClip(mastery_file)
        mastery_duration = min(40, mastery.duration)
        mastery = mastery.subclip(0, mastery_duration)
        mastery = add_text_overlay(mastery, f"Gen {end_gen} - MASTERED 🏆", position='top', color='lime')
        clips.append(mastery)
    else:
        print(f"⚠️  Mastery clip not found for Gen {end_gen}")
    
    if len(clips) == 0:
        print("❌ No clips found to create short!")
        return None
    
    # Concatenate all clips
    print("🔗 Concatenating clips...")
    final_clip = concatenate_videoclips(clips, method="compose")
    
    # Add music if available
    if os.path.exists(MUSIC_FILE):
        print("🎵 Adding background music...")
        try:
            audio = AudioFileClip(MUSIC_FILE).subclip(0, final_clip.duration)
            audio = audio.volumex(0.3)  # Lower volume to 30%
            final_clip = final_clip.set_audio(audio)
        except Exception as e:
            print(f"⚠️  Could not add music: {e}")
    
    # Add fade in/out
    final_clip = fadein(final_clip, 0.5)
    final_clip = fadeout(final_clip, 0.5)
    
    # Export
    output_file = f"{OUTPUT_DIR}/{challenge_id}_gen{start_gen}-{end_gen}.mp4"
    print(f"💾 Exporting to: {output_file}")
    
    final_clip.write_videofile(
        output_file,
        fps=30,
        codec='libx264',
        audio_codec='aac',
        preset='medium',
        threads=4,
        logger=None
    )
    
    print(f"✅ Short created: {output_file}")
    print(f"📺 Suggested Title: {challenge['video_hook']}")
    
    return output_file

def create_evolution_short_simple():
    """
    Simpler version: Just show Gen 1 vs Latest Gen
    Good for when you don't have challenge system set up yet
    """
    # Search all challenge subdirectories for clips
    all_gens = []
    challenge_loader = ChallengeLoader()
    
    # Get clips from all challenge directories
    for challenge_dir in glob.glob(f"{VIDEO_DIR}/*/"):
        clips = glob.glob(os.path.join(challenge_dir, "gen_*.mp4"))
        all_gens.extend(clips)
    
    # Also check root directory for backward compatibility
    root_clips = glob.glob(f"{VIDEO_DIR}/gen_*.mp4")
    all_gens.extend(root_clips)
    
    # Sort by generation number
    all_gens = sorted(all_gens, key=lambda x: int(os.path.basename(x).split('_')[1].split('.')[0]))
    
    if len(all_gens) < 2:
        print("❌ Need at least 2 generations to create evolution short")
        return None
    
    gen1_file = all_gens[0]
    latest_file = all_gens[-1]
    
    gen1_num = int(os.path.basename(gen1_file).split('_')[1].split('.')[0])
    latest_num = int(os.path.basename(latest_file).split('_')[1].split('.')[0])
    
    print(f"🎬 Creating evolution short: Gen {gen1_num} vs Gen {latest_num}")
    print(f"📹 Using clips: {os.path.basename(gen1_file)} and {os.path.basename(latest_file)}")
    
    clips = []
    
    # Gen 1 - 10 seconds
    gen1 = VideoFileClip(gen1_file)
    gen1_duration = min(15, gen1.duration)
    gen1 = gen1.subclip(0, gen1_duration)
    gen1 = speedx(gen1, 1.5)
    gen1 = add_text_overlay(gen1, f"GEN {gen1_num}: CHAOS 🤡", position='top', color='red')
    clips.append(gen1)
    
    # Latest gen - 50 seconds
    latest = VideoFileClip(latest_file)
    latest_duration = min(50, latest.duration)
    latest = latest.subclip(0, latest_duration)
    latest = add_text_overlay(latest, f"GEN {latest_num}: MASTERED 🏆", position='top', color='lime')
    clips.append(latest)
    
    final = concatenate_videoclips(clips, method="compose")
    
    # Add music
    if os.path.exists(MUSIC_FILE):
        try:
            audio = AudioFileClip(MUSIC_FILE).subclip(0, final.duration)
            audio = audio.volumex(0.3)
            final = final.set_audio(audio)
        except Exception as e:
            print(f"⚠️  Could not add music: {e}")
    
    # Add fades
    final = fadein(final, 0.5)
    final = fadeout(final, 0.5)
    
    output_file = f"{OUTPUT_DIR}/evolution_gen{gen1_num}-{latest_num}.mp4"
    
    final.write_videofile(
        output_file,
        fps=30,
        codec='libx264',
        audio_codec='aac',
        preset='medium',
        threads=4,
        logger=None
    )
    
    print(f"✅ Evolution short created: {output_file}")
    return output_file

if __name__ == "__main__":
    # Check for completed challenges
    challenge_loader = ChallengeLoader()
    last_completed = challenge_loader.get_last_completed_challenge()
    
    if last_completed:
        print(f"🎯 Found completed challenge: {last_completed['name']}")
        output = create_challenge_short(last_completed)
        
        if output:
            # Mark as video created
            challenge_loader.mark_video_posted(last_completed['id'])
            print(f"\n🎉 SHORT READY TO POST!")
            print(f"📁 File: {output}")
            print(f"📝 Suggested Title: {last_completed['video_hook']}")
            print(f"📝 Suggested Description: AI learns {last_completed['name']} through evolution. Gen {last_completed['start_gen']} → Gen {last_completed['end_gen']}")
        else:
            # Challenge completed but clips don't exist - mark as posted and skip
            print("⚠️  Challenge completed but video clips not available (recorded in earlier sessions)")
            print("📹 Marking challenge as posted to move on to next challenge")
            challenge_loader.mark_video_posted(last_completed['id'])
            
            # Try creating simple evolution short instead
            print("\nℹ️  Attempting to create simple evolution short from available clips...")
            simple_output = create_evolution_short_simple()
            if simple_output:
                print(f"✅ Created fallback evolution short: {simple_output}")
    else:
        print("ℹ️  No completed challenges found. Creating simple evolution short...")
        create_evolution_short_simple()
