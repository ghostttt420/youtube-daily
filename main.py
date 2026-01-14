import os
import random
import asyncio
import numpy as np
import google.generativeai as genai
import edge_tts
import requests
from moviepy.editor import (
    VideoFileClip, TextClip, CompositeVideoClip, 
    AudioFileClip, CompositeAudioClip, vfx, concatenate_videoclips
)
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# CONFIGURATION
genai.configure(api_key=os.environ["GEMINI_KEY"])
PEXELS_API_KEY = os.environ["PEXELS_KEY"]

TOPICS = {
    "Dark Riddle": "horror abstract scary dark",
    "Psychology": "optical illusion eye hypnotic",
    "Paradox": "mirror reflection dark mystery",
    "Surreal": "liminal space empty hallway fog"
}

# --- CUSTOM FX: CINEMATIC VIGNETTE (Focus) ---
def vignette(image, radius=None, opacity=0.5):
    """Darkens the corners to focus attention on text"""
    h, w = image.shape[:2]
    if radius is None:
        radius = min(h, w)
    
    # Create a mask
    x, y = np.ogrid[:h, :w]
    mask = np.sqrt((x - h/2)**2 + (y - w/2)**2) / (radius / 2)
    mask = 1 - np.clip(mask, 0, 1)
    
    # Darken image based on mask
    image = image.astype(float)
    image[:, :, 0] *= (1 - opacity * (1 - mask))
    image[:, :, 1] *= (1 - opacity * (1 - mask))
    image[:, :, 2] *= (1 - opacity * (1 - mask))
    return image.astype(np.uint8)

async def generate_content():
    print("1. Initiating Cinematic Engine...")
    topic_name, visual_keyword = random.choice(list(TOPICS.items()))
    print(f"Target: {topic_name}")

    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = (
        f"Write a short, dark {topic_name}. "
        "Structure: [Riddle text ending with 'What am I?'] || [The Answer]. "
        "Keep the riddle UNDER 15 words. " # STRICT LIMIT for pacing
        "Style: Mysterious, engaging. No intro text."
    )

    try:
        response = model.generate_content(prompt)
        full_text = response.text.strip()
        if "||" in full_text:
            riddle, answer = full_text.split("||")
        else:
            riddle = full_text
            answer = "???"
    except:
        riddle = "I have no face, but I watch you sleep. What am I?"
        answer = "A Clock"

    print(f"Riddle: {riddle}")

    print("3. Synthesizing Voice...")
    # Christopher pitched down for authority
    voice = "en-US-ChristopherNeural" 
    communicate = edge_tts.Communicate(riddle, voice, rate="+5%", pitch="-10Hz")
    await communicate.save("riddle_voice.mp3")

    print(f"4. Fetching Visuals...")
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={visual_keyword}&per_page=3&orientation=portrait"

    visual_files = []
    try:
        r = requests.get(url, headers=headers)
        videos = r.json()['videos']
        for i, vid in enumerate(videos[:3]):
            video_url = vid['video_files'][0]['link']
            filename = f"clip_{i}.mp4"
            with open(filename, "wb") as f:
                f.write(requests.get(video_url).content)
            visual_files.append(filename)
    except Exception as e:
        print(f"Pexels Error: {e}")
        return None, None, None

    return riddle, answer, visual_files

def edit_video(riddle_text, answer_text, visual_files):
    print("5. Compiling Cinematic Edit...")
    if not riddle_text: return

    voice_audio = AudioFileClip("riddle_voice.mp3")
    total_duration = voice_audio.duration + 4.0 

    # --- VISUAL PROCESSING ---
    clips_list = []
    clip_duration = total_duration / len(visual_files)
    
    for filename in visual_files:
        clip = VideoFileClip(filename)
        
        # SMART CROP: Force 9:16 Aspect Ratio (1080x1920)
        # 1. Resize based on height first
        if clip.h < 1920:
            clip = clip.resize(height=1920)
        
        # 2. If width is still too small, resize by width
        if clip.w < 1080:
            clip = clip.resize(width=1080)
            
        # 3. Center Crop
        clip = clip.crop(x1=0, y1=0, width=1080, height=1920, x_center=clip.w/2, y_center=clip.h/2)
        
        # Loop if too short
        if clip.duration < clip_duration:
            clip = clip.loop(duration=clip_duration)
        else:
            clip = clip.subclip(0, clip_duration)
            
        # Add Slow Zoom (Ken Burns)
        clip = clip.resize(lambda t: 1 + 0.03 * t) 
            
        clips_list.append(clip)
        
    background = concatenate_videoclips(clips_list)
    background = background.subclip(0, total_duration)

    # Apply Vignette (Dark Corners)
    background = background.fl_image(vignette)
    # General Darkening
    background = background.fx(vfx.colorx, 0.4)

    clips = [background]
    
    # --- DYNAMIC TEXT ENGINE ---
    words = riddle_text.split()
    word_duration = (voice_audio.duration * 0.9) / len(words) 
    current_time = 0
    font_choice = 'Impact' if 'Impact' in TextClip.list('font') else 'DejaVu-Sans-Bold'

    for word in words:
        clean_word = word.replace(".", "").replace(",", "").replace("?", "").replace("!", "")
        
        # --- DYNAMIC SIZING ---
        # Adjust font size based on word length to prevent cutoff
        if len(clean_word) <= 4:
            f_size = 180 # Huge for short words
        elif len(clean_word) <= 7:
            f_size = 140 # Normal
        else:
            f_size = 100 # Smaller for long words
            
        color = 'red' if clean_word.lower() in ['what', 'am', 'i', 'who'] else 'white'
        
        txt = TextClip(
            clean_word.upper(),
            fontsize=f_size,       
            color=color,
            font=font_choice,
            stroke_color='black',
            stroke_width=6,
            size=(1080, None), # Constrain width to screen
            method='caption'
        )
        
        txt = txt.set_pos(('center', 'center')).set_start(current_time).set_duration(word_duration)
        clips.append(txt)
        current_time += word_duration

    # --- ANSWER REVEAL ---
    answer_txt = TextClip(
        answer_text.strip().upper(),
        fontsize=120,
        color='#00FF41', 
        font=font_choice,
        stroke_color='black',
        stroke_width=5
    ).set_pos('center').set_start(voice_audio.duration + 1.5).set_duration(2.5)
    clips.append(answer_txt)

    # --- AUDIO MIX ---
    final_audio_tracks = [voice_audio.set_start(0)]
    if os.path.exists("music.mp3"):
        music = AudioFileClip("music.mp3")
        if music.duration < total_duration:
            music = music.loop(duration=total_duration + 1)
        music = music.subclip(0, total_duration).volumex(0.3) 
        final_audio_tracks.append(music)

    final_audio = CompositeAudioClip(final_audio_tracks)
    
    final = CompositeVideoClip(clips).set_duration(total_duration).set_audio(final_audio)
    final.write_videofile("cinematic_trap.mp4", fps=24, codec='libx264', audio_codec='aac')
    print("Video saved as cinematic_trap.mp4")

def upload_to_youtube(riddle_text, answer_text):
    print("6. Uploading...")
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"]
    )

    youtube = build("youtube", "v3", credentials=creds)

    title = f"Do NOT Watch At Night 👁️ #shorts #scary"
    description = f"Can you answer this?\n\nAnswer: || {answer_text} ||\n\n#riddle #horror #creepy"

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": ["shorts", "scary", "horror"],
                "categoryId": "24"
            },
            "status": { "privacyStatus": "public" }
        },
        media_body=MediaFileUpload("cinematic_trap.mp4")
    )
    response = request.execute()
    print(f"Done: https://youtu.be/{response['id']}")

if __name__ == "__main__":
    data = asyncio.run(generate_content())
    if data:
        riddle, answer, visuals = data
        if riddle:
            edit_video(riddle, answer, visuals)
            upload_to_youtube(riddle, answer)
