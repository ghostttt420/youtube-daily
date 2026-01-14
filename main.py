import os
import random
import asyncio
import google.generativeai as genai
import edge_tts
import requests
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip, CompositeAudioClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# CONFIGURATION
genai.configure(api_key=os.environ["GEMINI_KEY"])
PEXELS_API_KEY = os.environ["PEXELS_KEY"]

# --- CHANGE 1: THE GHOST PROTOCOL TOPICS ---
# We focus purely on Data, Privacy, and Security.
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

    # MODEL SELECTION (Kept your logic, it's good)
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
    # --- CHANGE 2: THE "HACKER" PROMPT ---
    # We remove "Did you know". We use "WARNING" or "ALERT".
    # We ask for a "Terminal Log" style.
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
    # Kept Christopher, but you should eventually look for a deeper voice if available.
    # 'en-US-EricNeural' is often good for serious tones if available, otherwise Christopher is fine.
    voice = "en-US-ChristopherNeural" 
    communicate = edge_tts.Communicate(script, voice)
    await communicate.save("voice.mp3")

    print(f"4. Fetching Visual Context '{visual_keyword}'...")
    headers = {"Authorization": PEXELS_API_KEY}
    # Added "abstract" and "dark" to ensure we don't get bright, happy videos.
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

    # Darken the background so the Green text pops
    background = background.subclip(0, voice_audio.duration).resize(height=1920).fx(lambda c: c.colorx(0.5))

    # Audio Layering
    final_audio = voice_audio
    try:
        if os.path.exists("music.mp3"):
            music = AudioFileClip("music.mp3")
            if music.duration < voice_audio.duration:
                music = music.loop(duration=voice_audio.duration + 1)
            music = music.subclip(0, voice_audio.duration)
            music = music.volumex(0.20) # Slightly louder for dramatic effect
            final_audio = CompositeAudioClip([voice_audio, music])
    except Exception as e:
        print(f"Music Error: {e}")

    # --- CHANGE 3: TERMINAL AESTHETIC CAPTIONS ---
    sentences = script_text.replace(".", ".|").replace("?", "?|").replace("!", "!|").split("|")
    sentences = [s.strip() for s in sentences if len(s) > 2]

    clips = [background]
    chunk_duration = voice_audio.duration / len(sentences)
    current_time = 0

    for sentence in sentences:
        # Changed Font to Courier (Monospace)
        # Changed Color to Matrix Green (#00FF41)
        # Added a black background box to the text for readability
        txt = TextClip(
            sentence.upper(), # Uppercase looks more like a warning
            fontsize=65, 
            color='#00FF41', # HACKER GREEN
            font='Courier-Bold', # If Courier isn't available, try 'Consolas' or 'DejaVu-Sans-Mono'
            size=(900, None), 
            method='caption',
            bg_color='rgba(0,0,0,0.6)' # Semi-transparent black box behind text
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

    # --- CHANGE 4: CLICK-THROUGH TITLES ---
    # Titles should trigger curiosity/fear.
    title = f"WARNING: {topic_name} Exposed ⚠️ #shorts"
    
    # Description Logic
    description = (
        f"{script_text}\n\n"
        "🔒 SECURE YOUR DATA:\n"
        "[Link to Affiliate 1]\n"
        "[Link to Affiliate 2]\n\n"
        "#privacy #cybersecurity #darkweb #technology"
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": ["shorts", "privacy", "cybersecurity", "hacker"],
                "categoryId": "28" # Changed to 'Science & Technology' (28) from 'People & Blogs' (22)
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
