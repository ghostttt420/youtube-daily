import os

# --- HEADLESS SERVER FIXES ---
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import PIL.Image
# MONKEY PATCH: Fix for MoviePy vs Pillow 10 incompatibility
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

import random
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip, vfx
# Import audio loop
from moviepy.audio.fx.all import audio_loop

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# CONFIG
CLIPS_DIR = "training_clips"
OUTPUT_FILE = "evolution_short.mp4"
MUSIC_FILE = "music.mp3" 

# --- TIME BUDGET CONFIG ---
# Strict 59s limit for Shorts. We leave 1s buffer.
TOTAL_DURATION_LIMIT = 58 
GEN_1_LIMIT = 8   # Only show 8s of failing
GEN_MID_LIMIT = 5 # Show 5s of progress

def make_video():
    print("🎬 Starting Smart-Edit...")
    
    # 1. Validation
    if not os.path.exists(CLIPS_DIR):
        print(f"❌ Error: Directory '{CLIPS_DIR}' not found.")
        return None

    files = [f for f in os.listdir(CLIPS_DIR) if f.endswith(".mp4")]
    if not files:
        print("❌ Error: No .mp4 files found.")
        return None

    # 2. Sort Clips
    try:
        files = sorted(files, key=lambda x: int(x.split('_')[1].split('.')[0]))
    except Exception as e:
        print(f"⚠️ Warning: Sorting failed. ({e})")
        files.sort()

    # 3. Select Narrative Arc
    if len(files) >= 3:
        # Start, Middle, End
        selected_files = [files[0], files[len(files)//2], files[-1]]
    else:
        selected_files = files 

    print(f"🎞️ Stitching: {selected_files}")
    
    clips = []
    
    # --- SMART EDITING LOOP ---
    for i, filename in enumerate(selected_files):
        path = os.path.join(CLIPS_DIR, filename)
        clip = VideoFileClip(path)
        
        # Resize if needed
        if clip.w > 1080: clip = clip.resize(width=1080)
        
        # Get Gen Number
        try:
            gen_num = int(filename.split('_')[1].split('.')[0])
        except: gen_num = 0
        
        # --- TIME BUDGETING LOGIC ---
        # Clip 0 (Gen 1 - The Noob): Hard Cut at 8 seconds
        if i == 0:
            if clip.duration > GEN_1_LIMIT:
                clip = clip.subclip(0, GEN_1_LIMIT)
            label = f"Gen {gen_num}: NOOB 🤡"
            color = 'red'

        # Clip 1 (The Middle - Progress): Speed Up 2x, Cut to 5s
        elif i == 1 and len(selected_files) > 2:
            clip = clip.fx(vfx.speedx, 2.0) # Double speed
            if clip.duration > GEN_MID_LIMIT:
                clip = clip.subclip(0, GEN_MID_LIMIT)
            label = f"Gen {gen_num}: Learning..."
            color = 'white'

        # Clip 2 (The Hero): Fill remaining time
        else:
            # Calculate time used so far
            current_duration = sum([c.duration for c in clips])
            time_left = TOTAL_DURATION_LIMIT - current_duration
            
            if time_left < 5: time_left = 10 # Safety buffer
            
            # If the run is longer than time left, SPEED IT UP to fit!
            # This ensures we see the finish line, just faster.
            if clip.duration > time_left:
                speed_factor = clip.duration / time_left
                # Cap speed to avoid looking ridiculous (max 4x)
                speed_factor = min(speed_factor, 4.0) 
                clip = clip.fx(vfx.speedx, speed_factor)
                
                # Hard cut if still too long (rare)
                if clip.duration > time_left:
                    clip = clip.subclip(0, time_left)

            label = f"Gen {gen_num}: PRO 🏎️"
            color = '#00FF41' 

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

    # 4. Concatenate
    final_video = concatenate_videoclips(clips, method="compose")
    print(f"⏱️ Final Duration: {final_video.duration} seconds")

    # 5. Add Music
    if os.path.exists(MUSIC_FILE):
        print(f"🎵 Layering Music: {MUSIC_FILE}")
        music = AudioFileClip(MUSIC_FILE)
        
        if music.duration < final_video.duration:
            music = audio_loop(music, duration=final_video.duration)
        else:
            music = music.subclip(0, final_video.duration)
            
        music = music.volumex(0.6) 
        final_video = final_video.set_audio(music)

    # 6. Render
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

        title = "AI Learns to Drive (Gen 1 vs Gen 30) 🧠🚗 #shorts"
        description = (
            "Evolutionary AI learns to race from scratch.\n"
            "Watch the progress from crashing to drifting!\n\n"
            "#machinelearning #python #ai #neuralnetwork"
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": ["ai", "python", "machine learning", "coding"],
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
