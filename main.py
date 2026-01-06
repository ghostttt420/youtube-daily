import os
import random
import asyncio
import google.generativeai as genai
import edge_tts
import requests
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# CONFIGURATION
genai.configure(api_key=os.environ["GEMINI_KEY"])
PEXELS_API_KEY = os.environ["PEXELS_KEY"]

async def generate_content():
    print("1. Finding Available Model...")
    # SMART MODEL FINDER
    # This loop asks Google what models are actually available to your key
    # instead of guessing and crashing.
    chosen_model = 'gemini-1.5-flash' # Default fallback
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'gemini' in m.name:
                    chosen_model = m.name
                    print(f"Success! Using model: {chosen_model}")
                    break
    except Exception as e:
        print(f"Warning: Could not list models ({e}). Trying default.")

    model = genai.GenerativeModel(chosen_model)
    
    print("2. Generating Script...")
    prompt = "Write a shocking fun fact about history, space, or oceans. Keep it under 25 words. No intro. No hashtags."
    
    try:
        response = model.generate_content(prompt)
        script = response.text.strip()
    except Exception as e:
        # If Gemini fails, we use a backup fact so the bot doesn't crash
        print(f"AI Error: {e}. Using backup script.")
        script = "Honey never spoils. Archaeologists have found pots of honey in ancient Egyptian tombs that are over 3,000 years old."
    
    print(f"Script: {script}")

    print("3. Generating Voice...")
    voice = "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(script, voice)
    await communicate.save("voice.mp3")

    print("4. Finding Video...")
    headers = {"Authorization": Pexels_API_KEY}
    query = random.choice(["technology", "ocean", "space", "abstract", "city"])
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=1&orientation=portrait"
    
    try:
        r = requests.get(url, headers=headers)
        video_data = r.json()
        video_url = video_data['videos'][0]['video_files'][0]['link']
        with open("background.mp4", "wb") as f:
            f.write(requests.get(video_url).content)
    except Exception as e:
        print(f"Pexels Error: {e}")
        return None
        
    return script

def edit_video(script_text):
    print("5. Editing Video...")
    if not script_text: return
    
    audio = AudioFileClip("voice.mp3")
    background = VideoFileClip("background.mp4")
    
    if background.duration < audio.duration:
        background = background.loop(duration=audio.duration + 0.5)
            
    background = background.subclip(0, audio.duration).resize(height=1920)
    
    # Text settings
    txt_clip = TextClip(script_text, fontsize=70, color='white', font='DejaVu-Sans-Bold', 
                       size=(800, None), method='caption', stroke_color='black', stroke_width=2)
    txt_clip = txt_clip.set_pos('center').set_duration(audio.duration)
    
    final = CompositeVideoClip([background, txt_clip]).set_audio(audio)
    final.write_videofile("short.mp4", fps=24, codec='libx264', audio_codec='aac')
    print("Video saved as short.mp4")

def upload_to_youtube(title):
    print("6. Uploading to YouTube...")
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"]
    )
    
    youtube = build("youtube", "v3", credentials=creds)
    
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": f"{title} #shorts",
                "description": "Daily Fact #shorts",
                "tags": ["shorts", "facts", "ai"],
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "public" 
            }
        },
        media_body=MediaFileUpload("short.mp4")
    )
    response = request.execute()
    print(f"Uploaded! Link: https://youtu.be/{response['id']}")

if __name__ == "__main__":
    script = asyncio.run(generate_content())
    if script:
        edit_video(script)
        upload_to_youtube("Daily Fact")
