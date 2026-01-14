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
    "Dark Riddle": "horror glitch scary abstract",
    "Psychology": "optical illusion eye hypnotic",
    "Paradox": "mirror reflection dark mystery",
    "Surreal": "liminal space empty hallway fog"
}

# --- CUSTOM FX: RGB SPLIT (GLITCH) ---
def rgb_split(image_frame):
    """Splits RGB channels and offsets them to create a 'Glitch' look"""
    # Create empty array
    result = np.zeros_like(image_frame)
    
    # Red Channel (Shift Left)
    result[:, :-5, 0] = image_frame[:, 5:, 0]
    # Green Channel (No Shift)
    result[:, :, 1] = image_frame[:, :, 1]
    # Blue Channel (Shift Right)
    result[:, 5:, 2] = image_frame[:, :-5, 2]
    
    return result

async def generate_content():
    print("1. Initiating Chaos Engine...")
    topic_name, visual_keyword = random.choice(list(TOPICS.items()))
    print(f"Target: {topic_name}")

    model = genai.GenerativeModel('gemini-1.5-flash')

    # PROMPT: Short & Scary
    prompt = (
        f"Write a scary, 1-sentence {topic_name}. "
        "Then provide the answer. "
        "Format: Riddle || Answer. "
        "Style: Creepy, Unsettling. "
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
        riddle = "I have no face, but I watch you sleep."
        answer = "A Clock"

    print(f"Riddle: {riddle}")

    print("3. Synthesizing Voice (Creepy Child)...")
    # --- VOICE HACK ---
    # Using a Child voice (Ana) pitched DOWN sounds demonic/creepy.
    # Much better than the 'News Anchor' voice.
    voice = "en-US-AnaNeural" 
    communicate = edge_tts.Communicate(riddle, voice, rate="-10%", pitch="-15Hz")
    await communicate.save("riddle_voice.mp3")

    print(f"4. Fetching 3 Visuals for '{visual_keyword}'...")
    headers = {"Authorization": PEXELS_API_KEY}
    # We fetch 3 clips instead of 1
    url = f"https://api.pexels.com/videos/search?query={visual_keyword}&per_page=3&orientation=portrait"

    visual_files = []
    try:
        r = requests.get(url, headers=headers)
        videos = r.json()['videos']
        
        # Download up to 3 videos
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
    print("5. Compiling Chaos Edit...")
    if not riddle_text: return

    voice_audio = AudioFileClip("riddle_voice.mp3")
    total_duration = voice_audio.duration + 4.0 

    # --- MULTI-SCENE LOGIC ---
    # We stitch the 3 downloaded clips together to create fast pacing
    clips_list = []
    clip_duration = total_duration / len(visual_files)
    
    for filename in visual_files:
        clip = VideoFileClip(filename).resize(height=1920)
        # Center crop
        clip = clip.crop(x1=0, y1=0, width=1080, height=1920, x_center=clip.w/2, y_center=clip.h/2)
        
        # Trim to short segment
        if clip.duration > clip_duration:
            clip = clip.subclip(0, clip_duration)
        else:
            clip = clip.loop(duration=clip_duration)
            
        clips_list.append(clip)
        
    # Combine the clips
    background = concatenate_videoclips(clips_list)
    # Ensure exact duration
    background = background.subclip(0, total_duration)

    # --- APPLY "GLITCH" FILTER ---
    # This applies the RGB Split function to every frame
    # Note: This is computationally heavy but looks cool.
    background = background.fl_image(rgb_split)
    
    # Darken
    background = background.fx(vfx.colorx, 0.4)

    clips = [background]
    
    # --- TEXT ENGINE ---
    words = riddle_text.split()
    word_duration = (voice_audio.duration * 0.9) / len(words) # 90% speed for safety
    current_time = 0
    font_choice = 'Impact' if 'Impact' in TextClip.list('font') else 'DejaVu-Sans-Bold'

    for word in words:
        clean_word = word.replace(".", "").replace(",", "").replace("?", "").replace("!", "")
        
        # Alternating Colors (White / Red) for "Flash" effect
        color = 'red' if random.random() > 0.8 else 'white'
        
        txt = TextClip(
            clean_word.upper(),
            fontsize=150,       
            color=color,
            font=font_choice,
            stroke_color='black',
            stroke_width=6,
            size=(1000, None),
            method='caption'
        )
        
        # Shake Effect (Random Position Offset)
        x_off = random.randint(-10, 10)
        y_off = random.randint(-10, 10)
        
        txt = txt.set_pos(('center', 'center')).set_start(current_time).set_duration(word_duration)
        clips.append(txt)
        current_time += word_duration

    # --- ANSWER REVEAL ---
    answer_txt = TextClip(
        answer_text.strip().upper(),
        fontsize=130,
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
    final.write_videofile("chaos_trap.mp4", fps=24, codec='libx264', audio_codec='aac')
    print("Video saved as chaos_trap.mp4")

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
    description = f"Answer: || {answer_text} ||\n\n#riddle #horror #creepy"

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": ["shorts", "scary", "horror"],
                "categoryId": "24" # Entertainment
            },
            "status": { "privacyStatus": "public" }
        },
        media_body=MediaFileUpload("chaos_trap.mp4")
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
