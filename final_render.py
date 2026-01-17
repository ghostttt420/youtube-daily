import os

# --- HEADLESS SERVER FIXES ---
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import PIL.Image
# MONKEY PATCH: Fix for MoviePy vs Pillow 10 incompatibility
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

import random
import json
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip, vfx
from moviepy.audio.fx.all import audio_loop

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# CONFIG
CLIPS_DIR = "training_clips"
OUTPUT_FILE = "evolution_short.mp4"
MUSIC_FILE = "music.mp3" 

# LOAD THEME FOR TITLE
try:
    with open("theme.json", "r") as f:
        THEME = json.load(f)
except:
    THEME = {"meta": {"title": "AI Learns to Drive 🧠🚗", "tags": ["ai"]}}

def make_video():
    print("🎬 Starting Narrative-Edit...")
    
    if not os.path.exists(CLIPS_DIR):
        print(f"❌ Error: Directory '{CLIPS_DIR}' not found.")
        return None

    files = [f for f in os.listdir(CLIPS_DIR) if f.endswith(".mp4")]
    if not files:
        print("❌ Error: No .mp4 files found.")
        return None

    # Sort Clips by generation number
    try:
        files = sorted(files, key=lambda x: int(x.split('_')[1].split('.')[0]))
    except Exception as e:
        print(f"⚠️ Warning: Sorting failed. ({e})")
        files.sort()

    # Select only the first (FAIL) and last (SUCCESS) clips
    if len(files) >= 2:
        selected_files = [files[0], files[-1]]
    else:
        # Fallback if only one clip exists
        selected_files = files
    
    print(f"🎞️ Stitching Narrative: {selected_files}")
    
    clips = []
    
    for i, filename in enumerate(selected_files):
        path = os.path.join(CLIPS_DIR, filename)
        clip = VideoFileClip(path)
        
        # Resize if needed
        if clip.w > 1080: clip = clip.resize(width=1080)
        
        try:
            gen_num = int(filename.split('_')[1].split('.')[0])
        except: gen_num = 0
        
        # --- NARRATIVE LOGIC ---
        # Clip 1: The FAIL (Gen 0)
        if i == 0:
            label = "Gen 0: NOOB 🤡"
            color = 'red'
            # Hard cut to 8 seconds max for the fail clip
            if clip.duration > 8:
                clip = clip.subclip(0, 8)

        # Clip 2: The SUCCESS (Final Gen)
        else:
            label = f"Gen {gen_num}: PRO 🏎️"
            color = '#00FF41' 
            # Allow this clip to be long to show the full run

        # Add Text Overlay
        try:
            txt = TextClip(
                label, 
                fontsize=80, 
                color=color, 
                font='DejaVu-Sans-Bold', 
                stroke_color='black', 
                stroke_width=3
            ).set_position(('center', 200)).set_duration(clip.duration)
            
            comp = CompositeVideoClip([clip, txt])
            clips.append(comp)
        except Exception as e:
            print(f"⚠️ Text Error: {e}")
            clips.append(clip)

    # Concatenate
    final_video = concatenate_videoclips(clips, method="compose")
    print(f"⏱️ Final Duration: {final_video.duration} seconds")
    
    # Speed up if over 60s
    if final_video.duration > 59:
        speed_factor = final_video.duration / 59.0
        print(f"⚡ Speeding up by {speed_factor:.2f}x to fit 60s")
        final_video = final_video.fx(vfx.speedx, speed_factor)

    # Add Music
    if os.path.exists(MUSIC_FILE):
        print(f"🎵 Layering Music: {MUSIC_FILE}")
        music = AudioFileClip(MUSIC_FILE)
        
        if music.duration < final_video.duration:
            music = audio_loop(music, duration=final_video.duration)
        else:
            music = music.subclip(0, final_video.duration)
            
        music = music.volumex(0.6) 
        final_video = final_video.set_audio(music)

    # Render
    print(f"💾 Rendering {OUTPUT_FILE}...")
    final_video.write_videofile(
        OUTPUT_FILE, 
        fps=30, 
        codec='libx264', 
        audio_codec='aac',
        preset='fast',
        logger=None 
    )
    return OUTPUT_FILE

def upload_video():
    print("🚀 Uploading to YouTube...")
    try:
        creds = Credentials(
            None,
            refresh_token=os.environ["YT_REFRESH_TOKEN"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["YT_CLIENT_ID"],
            client_secret=os.environ["YT_CLIENT_SECRET"]
        )
        youtube = build("youtube", "v3", credentials=creds)

        # Use dynamic title and tags from the theme
        title = f"{THEME['meta']['title']} #shorts"
        description = (
            "Evolutionary AI learns to race from scratch.\n"
            "Watch the journey from crashing to pro driving!\n\n"
            "#machinelearning #python #ai #neuralnetwork"
        )
        tags = THEME['meta']['tags'] + ["ai", "python", "machine learning", "coding"]

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "categoryId": "28"
                },
                "status": { "privacyStatus": "public" }
            },
            media_body=MediaFileUpload(OUTPUT_FILE)
        )
        response = request.execute()
        print(f"✅ Upload Complete! URL: https://youtu.be/{response['id']}")
    except Exception as e:
        print(f"❌ Upload Failed: {e}")

if __name__ == "__main__":
    if make_video():
        upload_video()
