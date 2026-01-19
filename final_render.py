import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

import random
import json
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip, CompositeAudioClip, vfx
from moviepy.audio.fx.all import audio_loop

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# CONFIG
CLIPS_DIR = "training_clips"
OUTPUT_FILE = "evolution_short.mp4"
MUSIC_FILE = "music.mp3" 
ENGINE_FILE = "engine.mp3" # <--- NEW: You need to add this file

# LOAD THEME
try:
    with open("theme.json", "r") as f:
        THEME = json.load(f)
except:
    THEME = {"meta": {"title": "AI Learns to Drive 🧠🚗", "tags": ["ai"]}}

def make_video():
    print("🎬 Starting Montage-Edit...")
    
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
    
    # We will build a list of volume levels for the engine sound
    engine_volumes = []
    
    for i, filename in enumerate(selected_files):
        path = os.path.join(CLIPS_DIR, filename)
        clip = VideoFileClip(path)
        
        if clip.w > 1080: clip = clip.resize(width=1080)
        
        try:
            gen_num = int(filename.split('_')[1].split('.')[0])
            if i == len(selected_files) - 1: last_gen_num = gen_num
        except: gen_num = 0
        
        # --- NARRATIVE LOGIC & VOLUME CONTROL ---
        if i == 0:
            label = "Gen 0: NOOB 🤡"
            color = 'red'
            engine_vol = 0.3 # Quiet engine for noobs
            if clip.duration > 5: clip = clip.subclip(0, 5)
            
        elif i == len(selected_files) - 1:
            label = f"Gen {gen_num}: PRO 🏎️"
            color = '#00FF41'
            engine_vol = 0.8 # Loud engine for the pro run
            
        else:
            label = f"Gen {gen_num}: Learning... 🧠"
            color = 'yellow'
            engine_vol = 0.5 # Medium engine for learning
            if clip.duration > 5: clip = clip.subclip(0, 5)

        # Store the duration and volume for this segment
        engine_volumes.append((clip.duration, engine_vol))

        try:
            txt = TextClip(label, fontsize=80, color=color, font='DejaVu-Sans-Bold', stroke_color='black', stroke_width=3).set_position(('center', 200)).set_duration(clip.duration)
            comp = CompositeVideoClip([clip, txt])
            clips.append(comp)
        except:
            clips.append(clip)

    final_video = concatenate_videoclips(clips, method="compose")
    
    # --- ELASTIC TIME ---
    target_duration = 59.0
    ratio = 1.0
    if final_video.duration > 60.0:
        ratio = final_video.duration / target_duration
        print(f"⚡ Speeding up by {ratio:.2f}x")
        final_video = final_video.fx(vfx.speedx, ratio)
    elif final_video.duration < 50.0:
        ratio = final_video.duration / target_duration
        print(f"🐢 Slowing down by {ratio:.2f}x")
        final_video = final_video.fx(vfx.speedx, ratio)

    # --- AUDIO MIXER ---
    audio_tracks = []
    
    # 1. MUSIC TRACK
    if os.path.exists(MUSIC_FILE):
        music = AudioFileClip(MUSIC_FILE)
        if music.duration < final_video.duration:
            music = audio_loop(music, duration=final_video.duration)
        else:
            music = music.subclip(0, final_video.duration)
        music = music.volumex(0.5) # Background volume
        audio_tracks.append(music)

    # 2. ENGINE TRACK (Dynamic Volume)
    if os.path.exists(ENGINE_FILE):
        print("🏎️ Adding Engine Sounds...")
        base_engine = AudioFileClip(ENGINE_FILE)
        base_engine = audio_loop(base_engine, duration=final_video.duration)
        
        # We need to apply the speed effect to the audio too if we sped up the video
        if ratio != 1.0:
            # vfx.speedx on audio changes pitch too (Chipmunk effect), 
            # which is actually GOOD for F1 engines (higher RPM sound)
            base_engine = base_engine.fx(vfx.speedx, ratio)
            # Trim to match video exactly
            base_engine = base_engine.subclip(0, final_video.duration)

        # Apply the volume ramps? 
        # For simplicity in MoviePy, we'll just set a constant aggressive volume 
        # because simulating per-clip volume curves is error-prone without advanced mixing.
        # Instead, we let the "Speed Up" effect naturally raise the pitch/intensity.
        base_engine = base_engine.volumex(0.4) 
        audio_tracks.append(base_engine)
    else:
        print("⚠️ Warning: engine.mp3 not found.")

    if audio_tracks:
        final_audio = CompositeAudioClip(audio_tracks)
        final_video = final_video.set_audio(final_audio)

    final_video.write_videofile(OUTPUT_FILE, fps=30, codec='libx264', audio_codec='aac', preset='fast', logger=None)
    return OUTPUT_FILE, last_gen_num

def upload_video(last_gen):
    print("🚀 Uploading...")
    try:
        creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token", client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"])
        youtube = build("youtube", "v3", credentials=creds)
        
        raw_title = THEME['meta']['title']
        if "{gen}" in raw_title:
            clean_title = raw_title.replace("{gen}", str(last_gen))
        else:
            clean_title = f"{raw_title} (Gen {last_gen})"
            
        title = f"{clean_title} #shorts"
        description = "Evolutionary AI learns to race.\n#machinelearning #python #ai"
        
        request = youtube.videos().insert(part="snippet,status", body={"snippet": {"title": title, "description": description, "tags": THEME['meta']['tags'], "categoryId": "28"}, "status": { "privacyStatus": "public" }}, media_body=MediaFileUpload(OUTPUT_FILE))
        response = request.execute()
        print(f"✅ Upload Complete! https://youtu.be/{response['id']}")
    except Exception as e:
        print(f"❌ Upload Failed: {e}")

if __name__ == "__main__":
    output_path, generation_count = make_video()
    if output_path:
        upload_video(generation_count)
