import os
import random
import asyncio
import google.generativeai as genai
import edge_tts
import requests
import math
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip, CompositeAudioClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

genai.configure(api_key=os.environ["GEMINI_KEY"])
PEXELS_API_KEY = os.environ["PEXELS_KEY"]

TOPICS = {
    "Deep Space": "galaxy universe stars",
    "Dark History": "ancient warrior ruins",
    "Future Tech": "cyberpunk robot neon",
    "Ocean Mystery": "deep sea underwater jellyfish",
    "Human Psych": "brain mind abstract"
}

async def generate_content():
    print("1. Selecting Topic...")
    topic_name, visual_keyword = random.choice(list(TOPICS.items()))
    
    # FIND MODEL
    chosen_model = 'gemini-1.5-flash'
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'gemini' in m.name:
                    chosen_model = m.name
                    break
    except: pass
    
    model = genai.GenerativeModel(chosen_model)
    
    # PROMPT FOR RETENTION (Short sentences)
    print("2. Generating Script...")
    prompt = f"Write a {topic_name} fact in 3 short, punchy sentences. Use simple words a 10-year-old would understand. Start with 'Imagine' or 'Did you know'. Total under 30 words."
    try:
        response = model.generate_content(prompt)
        script = response.text.strip()
    except:
        script = "The universe is expanding. It is moving faster than light. We will never catch up."
        visual_keyword = "space"
    
    print(f"Script: {script}")

    print("3. Generating Voice...")
    voice = "en-US-ChristopherNeural" 
    communicate = edge_tts.Communicate(script, voice)
    await communicate.save("voice.mp3")

    print("4. Finding Video...")
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={visual_keyword}&per_page=1&orientation=portrait"
    
    try:
        r = requests.get(url, headers=headers)
        video_url = r.json()['videos'][0]['video_files'][0]['link']
        with open("background.mp4", "wb") as f:
            f.write(requests.get(video_url).content)
    except:
        return None, None
        
    return script, topic_name

def edit_video(script_text, topic_name):
    print("5. Editing Video...")
    if not script_text: return
    
    voice_audio = AudioFileClip("voice.mp3")
    background = VideoFileClip("background.mp4")
    
    # Loop background
    if background.duration < voice_audio.duration:
        background = background.loop(duration=voice_audio.duration + 0.5)
    background = background.subclip(0, voice_audio.duration).resize(height=1920)
    
    # --- DYNAMIC CAPTION LOGIC ---
    # Split text into chunks (by sentences or every 5 words)
    # This keeps the screen active!
    sentences = script_text.replace(".", ".|").replace("?", "?|").replace("!", "!|").split("|")
    sentences = [s.strip() for s in sentences if len(s) > 2]
    
    clips = [background]
    
    # Calculate time per sentence roughly
    chunk_duration = voice_audio.duration / len(sentences)
    current_time = 0
    
    for sentence in sentences:
        txt = TextClip(sentence, fontsize=80, color='yellow', font='DejaVu-Sans-Bold', 
                       size=(900, None), method='caption', 
                       stroke_color='black', stroke_width=5)
        
        txt = txt.set_pos('center').set_start(current_time).set_duration(chunk_duration)
        clips.append(txt)
        current_time += chunk_duration

    # Add Music Layer
    final_audio = voice_audio
    if os.path.exists("music.mp3"):
        try:
            music = AudioFileClip("music.mp3")
            if music.duration < voice_audio.duration: music = music.loop(duration=voice_audio.duration+1)
            music = music.subclip(0, voice_audio.duration).volumex(0.15)
            final_audio = CompositeAudioClip([voice_audio, music])
        except: pass

    final = CompositeVideoClip(clips).set_audio(final_audio)
    final.write_videofile("short.mp4", fps=24, codec='libx264', audio_codec='aac')

def upload_to_youtube(script_text, topic_name):
    print("6. Uploading...")
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token", client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"])
    youtube = build("youtube", "v3", credentials=creds)
    
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": f"Wait for the end 💀 #{topic_name.split()[0]} #shorts",
                "description": f"{script_text} #facts",
                "tags": ["shorts", "viral", "facts"],
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "public" 
            }
        },
        media_body=MediaFileUpload("short.mp4")
    )
    request.execute()

if __name__ == "__main__":
    script, topic = asyncio.run(generate_content())
    if script:
        edit_video(script, topic)
        upload_to_youtube(script, topic)
