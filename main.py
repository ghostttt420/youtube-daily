import os
import random
import asyncio
import google.generativeai as genai
import edge_tts
import requests
from moviepy.editor import (
    VideoFileClip, TextClip, CompositeVideoClip, 
    AudioFileClip, CompositeAudioClip, vfx
)
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# CONFIGURATION
genai.configure(api_key=os.environ["GEMINI_KEY"])
PEXELS_API_KEY = os.environ["PEXELS_KEY"]

# --- GHOST PROTOCOL TOPICS ---
TOPICS = {
    "Digital Privacy": "matrix code glitch abstract technology",
    "Cyber Security": "hacker hood server room dark",
    "Surveillance": "cctv camera eye abstract",
    "Dark Web": "deep web binary code dark aesthetic",
    "AI Danger": "artificial intelligence robot red eyes",
    "Data Leaks": "cyberpunk city rain night"
}

async def generate_content():
    print("1. Initializing Ghost Protocol...")
    topic_name, visual_keyword = random.choice(list(TOPICS.items()))
    print(f"Target: {topic_name}")

    # MODEL SELECTION
    chosen_model = 'gemini-1.5-flash'
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'gemini' in m.name:
                    chosen_model = m.name
                    break
    except:
        pass
    
    model = genai.GenerativeModel(chosen_model)

    print("2. Generating Manifest...")
    # THE "HACKER" PROMPT
    prompt = (
        f"Write a dark, urgent fact about {topic_name}. "
        "Style: Cyber-thriller, Informative, Warning. "
        "Strictly 3 short sentences. "
        "Start with words like 'WARNING:', 'ALERT:', or 'SYSTEM FAILURE:'. "
        "Do not use emojis. Do not use 'Did you know'."
    )

    try:
        response = model.generate_content(prompt)
        script = response.text.strip()
    except Exception as e:
        print(f"AI Error: {e}")
        script = "WARNING: Your digital footprint is permanent. Deleting history does not remove the data from the server."
        visual_keyword = "matrix code"

    print(f"Payload: {script}")

    print("3. Synthesizing Voice...")
    voice = "en-US-ChristopherNeural" 
    communicate = edge_tts.Communicate(script, voice)
    await communicate.save("voice.mp3")

    print(f"4. Fetching Visual Context '{visual_keyword}'...")
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={visual_keyword}&per_page=1&orientation=portrait"

    try:
        r = requests.get(url, headers=headers)
        video_data = r.json()
        video_url = video_data['videos'][0]['video_files'][0]['link']
        with open("background.mp4", "wb") as f:
            f.write(requests.get(video_url).content)
    except Exception as e:
        print(f"Pexels Error: {e}")
        return None, None

    return script, topic_name

def edit_video(script_text, topic_name):
    print("5. Compiling Visuals...")
    if not script_text: return

    voice_audio = AudioFileClip("voice.mp3")
    background = VideoFileClip("background.mp4")

    # Loop video logic
    if background.duration < voice_audio.duration:
        background = background.loop(duration=voice_audio.duration + 0.5)

    # --- FIX APPLIED HERE ---
    # We now use vfx.colorx correctly to darken the video by 50%
    background = background.subclip(0, voice_audio.duration).resize(height=1920).fx(vfx.colorx, 0.5)

    # Audio Layering
    final_audio = voice_audio
    try:
        if os.path.exists("music.mp3"):
            music = AudioFileClip("music.mp3")
            if music.duration < voice_audio.duration:
                music = music.loop(duration=voice_audio.duration + 1)
            music = music.subclip(0, voice_audio.duration)
            music = music.volumex(0.20)
            final_audio = CompositeAudioClip([voice_audio, music])
    except Exception as e:
        print(f"Music Error: {e}")

    # TERMINAL AESTHETIC CAPTIONS
    sentences = script_text.replace(".", ".|").replace("?", "?|").replace("!", "!|").split("|")
    sentences = [s.strip() for s in sentences if len(s) > 2]

    clips = [background]
    chunk_duration = voice_audio.duration / len(sentences)
    current_time = 0

    # Font fallback for Linux servers
    font_choice = 'Courier-Bold' if 'Courier' in TextClip.list('font') else 'DejaVu-Sans-Mono'

    for sentence in sentences:
        txt = TextClip(
            sentence.upper(),
            fontsize=65, 
            color='#00FF41', # HACKER GREEN
            font=font_choice,
            size=(900, None), 
            method='caption',
            bg_color='rgba(0,0,0,0.6)'
        )

        txt = txt.set_pos('center').set_start(current_time).set_duration(chunk_duration)
        clips.append(txt)
        current_time += chunk_duration

    final = CompositeVideoClip(clips).set_audio(final_audio)
    final.write_videofile("ghost_protocol.mp4", fps=24, codec='libx264', audio_codec='aac')
    print("Video saved as ghost_protocol.mp4")

def upload_to_youtube(script_text, topic_name):
    print("6. Uploading to Network...")
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"]
    )

    youtube = build("youtube", "v3", credentials=creds)

    title = f"WARNING: {topic_name} Exposed ⚠️ #shorts"
    
    description = (
        f"{script_text}\n\n"
        "🔒 SECURE YOUR DATA:\n"
        "Check if you've been breached: https://haveibeenpwned.com\n\n"
        "#privacy #cybersecurity #darkweb #technology"
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": ["shorts", "privacy", "cybersecurity", "hacker"],
                "categoryId": "28"
            },
            "status": {
                "privacyStatus": "public" 
            }
        },
        media_body=MediaFileUpload("ghost_protocol.mp4")
    )
    response = request.execute()
    print(f"Transmission Complete: https://youtu.be/{response['id']}")

if __name__ == "__main__":
    script, topic = asyncio.run(generate_content())
    if script:
        edit_video(script, topic)
        upload_to_youtube(script, topic)
