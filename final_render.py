import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

import random
import json
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip, CompositeAudioClip, vfx, ColorClip
from moviepy.audio.fx.all import audio_loop

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# CONFIG
CLIPS_DIR = "training_clips"
OUTPUT_FILE = "evolution_short.mp4"

# --- DJ SYSTEM ---
MUSIC_OPTIONS = ["music.mp3", "music2.mp3", "music3.mp3"] 
ENGINE_FILE = "engine.mp3" 

# --- 1. VIRAL TITLE LIBRARY (Fixing "Titles need work") ---
# The bot will pick one of these to make each video feel unique
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
    "Gen {gen}: The AI's final form 🏎️"
]

def get_viral_title(generation):
    template = random.choice(VIRAL_TITLES)
    return template.format(gen=generation)

def make_video():
    print("🎬 Starting Viral-Montage-Edit...")
    
    if not os.path.exists(CLIPS_DIR):
        print(f"❌ Error: Directory '{CLIPS_DIR}' not found.")
        return None, 0

    files = [f for f in os.listdir(CLIPS_DIR) if f.endswith(".mp4")]
    if not files:
        print("❌ Error: No .mp4 files found.")
        return None, 0

    files.sort()
    selected_files = files 
    print(f"🎞️ Stitching {len(selected_files)} clips...")
    
    clips = []
    last_gen_num = 0
    engine_volumes = []
    
    # --- 2. ADDING THE "HOOK" OVERLAY (Fixing Thumbnails/Hooks) ---
    # We create a list of "Hooks" to burn into the first few seconds
    hooks = [
        "WAIT FOR IT... 💀",
        "GEN 1 VS GEN 100",
        "PURE CHAOS 🤡",
        "SATISFYING 🤤",
        "AI TRAINING... 🧬"
    ]
    chosen_hook = random.choice(hooks)
    
    for i, filename in enumerate(selected_files):
        path = os.path.join(CLIPS_DIR, filename)
        clip = VideoFileClip(path)
        
        if clip.w > 1080: clip = clip.resize(width=1080)
        
        try:
            gen_num = int(filename.split('_')[1].split('.')[0])
            if i == len(selected_files) - 1: last_gen_num = gen_num
        except: gen_num = 0
        
        # LOGIC:
        # Clip 0 = The "Hook" (Needs big text)
        # Last Clip = The "Payoff" (Needs celebration text)
        
        if i == 0:
            label = "Gen 0: TOTAL NOOB 🤡"
            color = 'red'
            engine_vol = 0.3
            if clip.duration > 4: clip = clip.subclip(0, 4)
            
            # ADD THE HOOK OVERLAY (Big Text in center)
            try:
                # Big white text with black border
                txt_hook = TextClip(chosen_hook, fontsize=110, color='white', font='DejaVu-Sans-Bold', stroke_color='black', stroke_width=5)
                txt_hook = txt_hook.set_position(('center', 'center')).set_duration(clip.duration)
                
                # Smaller label below
                txt_label = TextClip(label, fontsize=60, color=color, font='DejaVu-Sans-Bold', stroke_color='black', stroke_width=2)
                txt_label = txt_label.set_position(('center', 0.8), relative=True).set_duration(clip.duration)
                
                clip = CompositeVideoClip([clip, txt_hook, txt_label])
            except Exception as e:
                print(f"⚠️ Text error: {e}")
            
        elif i == len(selected_files) - 1:
            # Only call it PRO if it's actually performing well (completed at least one lap)
            # gen_num represents the generation count, and at 50+ gens per day, it should be decent
            is_actually_pro = gen_num >= 100
            if is_actually_pro:
                label = f"Gen {gen_num}: PRO LEVEL 🏎️"
                color = '#00FF41' # Matrix Green
            else:
                label = f"Gen {gen_num}: IMPROVING 📈"
                color = '#FFA500' # Orange - still learning
            engine_vol = 0.8
            
            try:
                txt = TextClip(label, fontsize=90, color=color, font='DejaVu-Sans-Bold', stroke_color='black', stroke_width=4).set_position(('center', 0.2), relative=True).set_duration(clip.duration)
                clip = CompositeVideoClip([clip, txt])
            except: pass
            
        else:
            # Middle clips (Learning phase)
            label = f"Gen {gen_num}: Learning..."
            color = 'yellow'
            engine_vol = 0.5
            if clip.duration > 3: clip = clip.subclip(0, 3) # Keep middle clips short/fast
            
            try:
                txt = TextClip(label, fontsize=60, color=color, font='DejaVu-Sans-Bold', stroke_color='black', stroke_width=2).set_position(('center', 0.8), relative=True).set_duration(clip.duration)
                clip = CompositeVideoClip([clip, txt])
            except: pass

        engine_volumes.append((clip.duration, engine_vol))
        clips.append(clip)

    final_video = concatenate_videoclips(clips, method="compose")
    
    # --- ELASTIC TIME ---
    target_duration = 58.0 # Aim slightly under 60s for safety
    ratio = 1.0
    if final_video.duration > 60.0:
        ratio = final_video.duration / target_duration
        print(f"⚡ Speeding up by {ratio:.2f}x")
        final_video = final_video.fx(vfx.speedx, ratio)
    elif final_video.duration < 15.0: # If too short, slow it down
        ratio = final_video.duration / 58.0
        # This effectively loops/stretches content, careful not to slow too much
        # Better strategy for short videos: Loop it!
        pass 

    # --- AUDIO MIXER ---
    audio_tracks = []
    
    # 1. MUSIC (DJ System)
    available_music = [m for m in MUSIC_OPTIONS if os.path.exists(m)]
    if available_music:
        chosen_song = random.choice(available_music)
        print(f"🎵 DJ Selected: {chosen_song}")
        music = AudioFileClip(chosen_song)
        if music.duration < final_video.duration:
            music = audio_loop(music, duration=final_video.duration)
        else:
            music = music.subclip(0, final_video.duration)
        music = music.volumex(0.5)
        audio_tracks.append(music)

    # 2. ENGINE (Dynamic)
    if os.path.exists(ENGINE_FILE):
        base_engine = AudioFileClip(ENGINE_FILE)
        base_engine = audio_loop(base_engine, duration=final_video.duration)
        if ratio != 1.0:
            base_engine = base_engine.fx(vfx.speedx, ratio)
            base_engine = base_engine.subclip(0, final_video.duration)
        base_engine = base_engine.volumex(0.4) 
        audio_tracks.append(base_engine)

    if audio_tracks:
        final_audio = CompositeAudioClip(audio_tracks)
        final_video = final_video.set_audio(final_audio)

    final_video.write_videofile(OUTPUT_FILE, fps=30, codec='libx264', audio_codec='aac', preset='medium', logger=None)
    return OUTPUT_FILE, last_gen_num

def upload_video(last_gen):
    print("🚀 Uploading...")
    try:
        creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token", client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"])
        youtube = build("youtube", "v3", credentials=creds)
        
        # --- 3. DYNAMIC METADATA (Fixing Discoverability) ---
        title = get_viral_title(last_gen) + " #shorts"
        
        description = f"""
        Watch AI learn to drive from scratch! 🧬🚗 
        This is Generation {last_gen} of an evolutionary algorithm.
        
        Progression:
        - Gen 0: Complete chaos
        - Gen {last_gen}: Optimized neural network
        
        Subscribe to see if it can master the track! 
        
        #ai #machinelearning #python #coding #racing #simulation #neuralnetwork #tech #programming
        """
        
        request = youtube.videos().insert(part="snippet,status", body={"snippet": {"title": title, "description": description, "tags": ["ai", "machine learning", "python", "racing", "simulation", "coding"], "categoryId": "28"}, "status": { "privacyStatus": "public" }}, media_body=MediaFileUpload(OUTPUT_FILE))
        response = request.execute()
        print(f"✅ Upload Complete! https://youtu.be/{response['id']}")
    except Exception as e:
        print(f"❌ Upload Failed: {e}")

if __name__ == "__main__":
    output_path, generation_count = make_video()
    if output_path:
        upload_video(generation_count)
