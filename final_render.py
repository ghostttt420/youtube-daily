import os

# --- HEADLESS SERVER FIXES (MUST BE FIRST) ---
# This prevents the ALSA audio errors on GitHub Actions
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import PIL.Image
# MONKEY PATCH: Fix for MoviePy vs Pillow 10 incompatibility
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

import random
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# CONFIG
CLIPS_DIR = "training_clips"
OUTPUT_FILE = "evolution_short.mp4"
MUSIC_FILE = "music.mp3"  # Make sure you upload a royalty-free track with this name!

def make_video():
    print("🎬 Starting Auto-Edit...")
    
    # 1. Validation: Do we have clips?
    if not os.path.exists(CLIPS_DIR):
        print(f"❌ Error: Directory '{CLIPS_DIR}' not found. You must run the simulation first.")
        return None

    files = [f for f in os.listdir(CLIPS_DIR) if f.endswith(".mp4")]
    if not files:
        print("❌ Error: No .mp4 files found in clips directory. Simulation might have failed.")
        return None

    # 2. Sort Clips (Gen 1, Gen 2, etc.)
    # Filename format expected: "gen_1.mp4", "gen_10.mp4"
    try:
        files = sorted(files, key=lambda x: int(x.split('_')[1].split('.')[0]))
    except Exception as e:
        print(f"⚠️ Warning: Filenames weird, sorting alphabetically. ({e})")
        files.sort()

    # 3. Select the Narrative Arc (Start -> Struggle -> Success)
    # We pick: First Generation, Middle Generation, Final Generation
    if len(files) >= 3:
        selected_files = [files[0], files[len(files)//2], files[-1]]
    else:
        selected_files = files # Just use what we have

    print(f"🎞️ Stitching these clips: {selected_files}")
    
    clips = []
    for filename in selected_files:
        path = os.path.join(CLIPS_DIR, filename)
        clip = VideoFileClip(path)
        
        # Resize to Vertical 1080p (if needed)
        if clip.w > 1080: clip = clip.resize(width=1080)
        
        # Get Generation Number for Text
        try:
            gen_num = int(filename.split('_')[1].split('.')[0])
        except: 
            gen_num = 0
        
        # Dynamic Text Logic
        if gen_num <= 5: 
            label = f"Gen {gen_num}: NOOB 🤡"
            color = 'red'
        elif gen_num >= 20: 
            label = f"Gen {gen_num}: GOD MODE 🤯"
            color = '#00FF41' # Matrix Green
        else:
            label = f"Gen {gen_num}: Training..."
            color = 'white'

        # Overlay Text (With Linux Fallback)
        try:
            # 'DejaVu-Sans-Bold' is safer on Linux servers than 'Impact'
            txt = TextClip(
                label, 
                fontsize=80, 
                color=color, 
                font='DejaVu-Sans-Bold', 
                stroke_color='black', 
                stroke_width=3
            ).set_position(('center', 200)).set_duration(clip.duration)
            
            # Combine Clip + Text
            comp = CompositeVideoClip([clip, txt])
            clips.append(comp)
        except Exception as e:
            print(f"⚠️ TextClip Failed (ImageMagick missing?): {e}")
            # Fallback: Use clip without text
            clips.append(clip)

    # 4. Concatenate All Parts
    final_video = concatenate_videoclips(clips, method="compose")

    # 5. Add Music (Viral Necessity)
    if os.path.exists(MUSIC_FILE):
        print(f"🎵 Layering Background Music: {MUSIC_FILE}")
        music = AudioFileClip(MUSIC_FILE)
        
        # Loop music if video is longer, cut if shorter
        if music.duration < final_video.duration:
            music = music.loop(duration=final_video.duration)
        else:
            music = music.subclip(0, final_video.duration)
            
        music = music.volumex(0.6) # 60% volume
        final_video = final_video.set_audio(music)
    else:
        print("⚠️ Warning: 'music.mp3' not found. Video will be silent.")

    # 6. Render Final File
    print(f"💾 Rendering {OUTPUT_FILE}...")
    final_video.write_videofile(
        OUTPUT_FILE, 
        fps=30, 
        codec='libx264', 
        audio_codec='aac',
        preset='fast',
        logger=None # Keep logs clean
    )
    print("✅ Video Successfully Rendered.")
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

        title = "AI Learns to Drive in 60 Seconds 🧠🚗 #shorts"
        description = (
            "I built an evolutionary AI in Python to learn how to drive.\n"
            "Watch it go from crashing instantly to drifting like a pro.\n\n"
            "Source Code: [Link in Bio]\n"
            "#machinelearning #python #ai #neuralnetwork"
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": ["ai", "python", "machine learning", "coding"],
                    "categoryId": "28" # Science & Tech
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
