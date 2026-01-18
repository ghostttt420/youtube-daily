import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import PIL.Image
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
        return None

    files = [f for f in os.listdir(CLIPS_DIR) if f.endswith(".mp4")]
    if not files:
        print("❌ Error: No .mp4 files found.")
        return None

    # Sort files naturally: gen_00, gen_05, gen_10...
    files.sort()
    
    # USE ALL FILES (Not just first and last)
    selected_files = files 
    print(f"🎞️ Stitching {len(selected_files)} clips: {selected_files}")
    
    clips = []
    
    for i, filename in enumerate(selected_files):
        path = os.path.join(CLIPS_DIR, filename)
        clip = VideoFileClip(path)
        
        if clip.w > 1080: clip = clip.resize(width=1080)
        
        # Get Gen Number
        try:
            # Filename is gen_05.mp4 -> 5
            gen_num = int(filename.split('_')[1].split('.')[0])
        except: gen_num = 0
        
        # --- NARRATIVE LOGIC ---
        if i == 0:
            label = "Gen 0: NOOB 🤡"
            color = 'red'
            # Gen 0: Force 5 seconds max
            if clip.duration > 5: clip = clip.subclip(0, 5)
            
        elif i == len(selected_files) - 1:
            label = f"Gen {gen_num}: PRO 🏎️"
            color = '#00FF41'
            # Final Gen: Keep it long, we want to see the finish
            
        else:
            label = f"Gen {gen_num}: Learning... 🧠"
            color = 'yellow'
            # Intermediate clips: Speed up to 5s max if they are long
            if clip.duration > 5: clip = clip.subclip(0, 5)

        try:
            # Add Text Overlay
            txt = TextClip(label, fontsize=80, color=color, font='DejaVu-Sans-Bold', stroke_color='black', stroke_width=3).set_position(('center', 200)).set_duration(clip.duration)
            comp = CompositeVideoClip([clip, txt])
            clips.append(comp)
        except:
            clips.append(clip)

    final_video = concatenate_videoclips(clips, method="compose")
    print(f"⏱️ Raw Stitch Duration: {final_video.duration} seconds")
    
    # --- ELASTIC TIME (GUARANTEE 59s) ---
    target_duration = 59.0
    
    # Calculate Ratio
    ratio = final_video.duration / target_duration
    
    # If video is 30s, Ratio is 0.5. We need to slow down (0.5x speed).
    # If video is 90s, Ratio is 1.5. We need to speed up (1.5x speed).
    
    print(f"⚖️ Adjusting speed by factor {ratio:.2f}x to hit 59s")
    final_video = final_video.fx(vfx.speedx, ratio)

    # Add Music
    if os.path.exists(MUSIC_FILE):
        music = AudioFileClip(MUSIC_FILE)
        if music.duration < final_video.duration:
            music = audio_loop(music, duration=final_video.duration)
        else:
            music = music.subclip(0, final_video.duration)
        music = music.volumex(0.6) 
        final_video = final_video.set_audio(music)

    final_video.write_videofile(OUTPUT_FILE, fps=30, codec='libx264', audio_codec='aac', preset='fast', logger=None)
    return OUTPUT_FILE

def upload_video():
    print("🚀 Uploading...")
    try:
        creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token", client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"])
        youtube = build("youtube", "v3", credentials=creds)
        title = f"{THEME['meta']['title']} #shorts"
        description = "Evolutionary AI learns to race.\n#machinelearning #python #ai"
        request = youtube.videos().insert(part="snippet,status", body={"snippet": {"title": title, "description": description, "tags": THEME['meta']['tags'], "categoryId": "28"}, "status": { "privacyStatus": "public" }}, media_body=MediaFileUpload(OUTPUT_FILE))
        response = request.execute()
        print(f"✅ Upload Complete! https://youtu.be/{response['id']}")
    except Exception as e:
        print(f"❌ Upload Failed: {e}")

if __name__ == "__main__":
    if make_video():
        upload_video()
