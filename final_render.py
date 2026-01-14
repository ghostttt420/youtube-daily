import os
import random
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# CONFIG
CLIPS_DIR = "training_clips"
OUTPUT_FILE = "evolution_short.mp4"

def make_video():
    print("🎬 Starting Auto-Edit...")
    
    # We expect clips like 'gen_1.mp4', 'gen_10.mp4', 'gen_29.mp4'
    # Sort them by generation number
    files = sorted([f for f in os.listdir(CLIPS_DIR) if f.endswith(".mp4")], 
                   key=lambda x: int(x.split('_')[1].split('.')[0]))
    
    if not files:
        print("❌ No training clips found!")
        return None

    # Pick key moments: Start (Gen 1), Middle, and End (Best)
    # We want a 60s video max.
    selected_files = [files[0], files[len(files)//2], files[-1]]
    
    clips = []
    for filename in selected_files:
        path = os.path.join(CLIPS_DIR, filename)
        clip = VideoFileClip(path)
        
        # 1. Resize/Crop to 9:16 (if not already)
        # Assuming Pygame recorded 1080x1920, we just ensure it fits
        if clip.w > 1080: clip = clip.resize(width=1080)
        
        # 2. Add Overlay Text (e.g., "GENERATION 1")
        gen_num = filename.split('_')[1].split('.')[0]
        
        # Text Logic
        if int(gen_num) < 5: 
            label = f"Gen {gen_num}: NOOB 🤡"
            color = 'red'
        elif int(gen_num) > 20: 
            label = f"Gen {gen_num}: GOD MODE 🤯"
            color = '#00FF41' # Matrix Green
        else:
            label = f"Gen {gen_num}: Training..."
            color = 'white'

        txt = TextClip(
            label, 
            fontsize=100, 
            color=color, 
            font='Impact', 
            stroke_color='black', 
            stroke_width=4
        ).set_position(('center', 200)).set_duration(clip.duration)
        
        # Composite
        comp = CompositeVideoClip([clip, txt])
        clips.append(comp)

    # Concatenate all parts
    final = concatenate_videoclips(clips)
    final.write_videofile(OUTPUT_FILE, fps=30, codec='libx264', audio_codec='aac')
    print("✅ Video Rendered.")
    return OUTPUT_FILE

def upload_video():
    print("🚀 Uploading to YouTube...")
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"]
    )
    youtube = build("youtube", "v3", credentials=creds)

    title = "AI Learns to Drive from Scratch 🧠🚗 #shorts #ai"
    description = (
        "I built an AI that learns to drive using evolution.\n"
        "Watch Generation 1 vs Generation 30.\n\n"
        "#machinelearning #python #simulation #artificialintelligence"
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["ai", "machine learning", "python", "simulation"],
                "categoryId": "28" # Science & Tech
            },
            "status": { "privacyStatus": "public" }
        },
        media_body=MediaFileUpload(OUTPUT_FILE)
    )
    response = request.execute()
    print(f"✅ Upload Complete: https://youtu.be/{response['id']}")

if __name__ == "__main__":
    if make_video():
        upload_video()
