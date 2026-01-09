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

# TOPIC WHEEL (From Old Script)
TOPICS = {
    "Space & Universe": "space stars planets",
    "Ancient History": "ancient ruins history",
    "Futuristic Tech": "cyberpunk technology future",
    "Deep Ocean": "underwater ocean sea",
    "Psychology Facts": "abstract brain mind",
    "Scary Stories": "dark spooky forest mist"
}

async def generate_content():
    print("1. Selecting Topic...")
    topic_name, visual_keyword = random.choice(list(TOPICS.items()))
    print(f"Selected Topic: {topic_name}")
    
    # SMART MODEL FINDER
    chosen_model = 'gemini-1.5-flash'
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'gemini' in m.name:
                    chosen_model = m.name
                    break
    except:
        pass
    
    print(f"Using Model: {chosen_model}")
    model = genai.GenerativeModel(chosen_model)
    
    print("2. Generating Script...")
    # --- NEW CHANGE: Retention Prompt ---
    # Forces 3 punchy sentences instead of one block
    prompt = f"Write a {topic_name} fact in 3 short, punchy sentences. Use simple words a 10-year-old would understand. Start with 'Imagine' or 'Did you know'. Total under 30 words."
    
    try:
        response = model.generate_content(prompt)
        script = response.text.strip()
    except Exception as e:
        print(f"AI Error: {e}")
        script = "The Eiffel Tower can be 15 cm taller during the summer due to thermal expansion."
        visual_keyword = "Paris city"
    
    print(f"Script: {script}")

    print("3. Generating Voice...")
    voice = "en-US-ChristopherNeural" 
    communicate = edge_tts.Communicate(script, voice)
    await communicate.save("voice.mp3")

    print(f"4. Finding Video for '{visual_keyword}'...")
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
    print("5. Editing Video...")
    if not script_text: return
    
    # Load Audio
    voice_audio = AudioFileClip("voice.mp3")
    
    # Load Background Video
    background = VideoFileClip("background.mp4")
    
    # Loop video if shorter than audio
    if background.duration < voice_audio.duration:
        background = background.loop(duration=voice_audio.duration + 0.5)
            
    background = background.subclip(0, voice_audio.duration).resize(height=1920)
    
    # --- MUSIC LAYER (From Old Script) ---
    final_audio = voice_audio
    try:
        if os.path.exists("music.mp3"):
            music = AudioFileClip("music.mp3")
            if music.duration < voice_audio.duration:
                music = music.loop(duration=voice_audio.duration + 1)
            music = music.subclip(0, voice_audio.duration)
            music = music.volumex(0.15)
            final_audio = CompositeAudioClip([voice_audio, music])
        else:
            print("No music.mp3 found. using voice only.")
    except Exception as e:
        print(f"Music Error: {e}")

    # --- NEW CHANGE: Dynamic Text Chunking ---
    # Instead of one big text block, we split it by sentences
    sentences = script_text.replace(".", ".|").replace("?", "?|").replace("!", "!|").split("|")
    sentences = [s.strip() for s in sentences if len(s) > 2]
    
    clips = [background]
    
    # Calculate how long each sentence stays on screen
    chunk_duration = voice_audio.duration / len(sentences)
    current_time = 0
    
    for sentence in sentences:
        txt = TextClip(sentence, fontsize=80, color='yellow', font='DejaVu-Sans-Bold', 
                       size=(850, None), method='caption', 
                       stroke_color='black', stroke_width=4)
        
        txt = txt.set_pos('center').set_start(current_time).set_duration(chunk_duration)
        clips.append(txt)
        current_time += chunk_duration
    
    # Combine Everything
    final = CompositeVideoClip(clips).set_audio(final_audio)
    final.write_videofile("short.mp4", fps=24, codec='libx264', audio_codec='aac')
    print("Video saved as short.mp4")

def upload_to_youtube(script_text, topic_name):
    print("6. Uploading to YouTube...")
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"]
    )
    
    youtube = build("youtube", "v3", credentials=creds)
    
    # Title Logic (From Old Script)
    title = f"{topic_name}: Did you know? 🤯 #shorts"
    if len(script_text) < 50:
        title = f"{script_text} #shorts"

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title[:100],
                "description": f"{script_text}\n\n#facts #learning #{topic_name.split()[0]}",
                "tags": ["shorts", "facts", topic_name.split()[0]],
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
    script, topic = asyncio.run(generate_content())
    if script:
        edit_video(script, topic)
        upload_to_youtube(script, topic)
