import os
import random
import asyncio
import datetime
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

# --- TIME-BASED CONTENT ENGINE ---
def get_dynamic_theme():
    """Decides content based on the server's current hour"""
    # GitHub Actions usually runs in UTC. 
    # 08:00 UTC = 9:00 AM Nigeria (Morning)
    # 14:00 UTC = 3:00 PM Nigeria (Afternoon)
    # 20:00 UTC = 9:00 PM Nigeria (Night)
    
    hour = datetime.datetime.now().hour
    print(f"⏰ Server Time: {hour}:00")
    
    # MORNING (Logic & Brain Teasers)
    if hour < 12:
        print("☀️ Mode: ACTIVE BRAIN")
        return random.choice([
            ("Logic Puzzle", "abstract geometry white minimal"),
            ("Lateral Thinking", "chess board dark noir"),
            ("Impossible Riddle", "maze labyrinth abstract")
        ])
        
    # AFTERNOON (Psychology & Mind Tricks)
    elif hour < 18:
        print("🌤️ Mode: MIND BENDING")
        return random.choice([
            ("Psychology Trick", "hypnotic spiral optical illusion"),
            ("Paradox", "mirror reflection infinity"),
            ("Unsettling Fact", "liminal space empty hallway")
        ])
        
    # NIGHT (Horror & Dark Mystery)
    else:
        print("🌑 Mode: NIGHTMARE")
        return random.choice([
            ("Two Sentence Horror", "dark forest fog monster"),
            ("Dark Riddle", "noir rain window night"),
            ("Glitch Message", "glitch static noise tv horror")
        ])

# --- CUSTOM FX: VIGNETTE ---
def vignette(image, radius=None, opacity=0.5):
    """Darkens corners to focus attention on text"""
    h, w = image.shape[:2]
    if radius is None: radius = min(h, w)
    x, y = np.ogrid[:h, :w]
    mask = np.sqrt((x - h/2)**2 + (y - w/2)**2) / (radius / 2)
    mask = 1 - np.clip(mask, 0, 1)
    image = image.astype(float)
    image[:, :, 0] *= (1 - opacity * (1 - mask))
    image[:, :, 1] *= (1 - opacity * (1 - mask))
    image[:, :, 2] *= (1 - opacity * (1 - mask))
    return image.astype(np.uint8)

async def generate_content():
    print("1. Initiating Content Engine...")
    theme, visual_keyword = get_dynamic_theme()
    print(f"Target: {theme}")

    model = genai.GenerativeModel('gemini-1.5-flash')

    # PROMPT: Optimized for retention & pacing
    prompt = (
        f"Write a viral YouTube Short script about: {theme}. "
        "Format: [Hook/Riddle] || [Answer]. "
        "Strict Constraints: "
        "1. Total under 20 words. "
        "2. Ending MUST be a question (e.g., 'What am I?', 'Who is it?'). "
        "3. Use simple, punchy words. No emojis."
    )

    try:
        response = model.generate_content(prompt)
        full_text = response.text.strip()
        if "||" in full_text:
            riddle, answer = full_text.split("||")
        else:
            riddle = full_text
            answer = "Check Comments"
    except:
        riddle = "I have no face, but I watch you sleep. What am I?"
        answer = "A Clock"

    print(f"Script: {riddle}")

    print("3. Synthesizing Voice...")
    # Voice Selection Logic
    if "Horror" in theme or "Dark" in theme:
        voice = "en-US-ChristopherNeural"
        pitch = "-15Hz" # Deep Trailer Voice
    else:
        voice = "en-GB-RyanNeural"
        pitch = "-5Hz" # Sherlock Mystery Voice
    
    communicate = edge_tts.Communicate(riddle, voice, rate="+5%", pitch=pitch)
    await communicate.save("riddle_voice.mp3")

    print(f"4. Fetching Visuals for '{visual_keyword}'...")
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={visual_keyword}&per_page=3&orientation=portrait"

    visual_files = []
    try:
        r = requests.get(url, headers=headers)
        videos = r.json().get('videos', [])
        for i, vid in enumerate(videos[:3]):
            video_url = vid['video_files'][0]['link']
            filename = f"clip_{i}.mp4"
            with open(filename, "wb") as f:
                f.write(requests.get(video_url).content)
            visual_files.append(filename)
    except Exception as e:
        print(f"Pexels Error: {e}")
        return None, None, None, None

    return riddle, answer, visual_files, theme

def edit_video(riddle_text, answer_text, visual_files, theme):
    print("5. Editing Professional Cut...")
    if not riddle_text: return

    voice_audio = AudioFileClip("riddle_voice.mp3")
    total_duration = voice_audio.duration + 4.0 

    # --- VISUAL STITCH & CROP ---
    clips_list = []
    # If 3 clips, divide duration equally
    clip_duration = total_duration / max(1, len(visual_files))
    
    for filename in visual_files:
        clip = VideoFileClip(filename)
        
        # FORCE 9:16 (1080x1920)
        # 1. Resize height to 1920 (or larger)
        if clip.h < 1920:
            clip = clip.resize(height=1920)
        
        # 2. If width is still < 1080, resize by width
        if clip.w < 1080:
            clip = clip.resize(width=1080)
            
        # 3. Center Crop
        clip = clip.crop(x1=0, y1=0, width=1080, height=1920, x_center=clip.w/2, y_center=clip.h/2)

        # Loop if needed
        if clip.duration < clip_duration:
            clip = clip.loop(duration=clip_duration)
        
        clip = clip.subclip(0, clip_duration)
        
        # Ken Burns Zoom (Subtle movement)
        clip = clip.resize(lambda t: 1 + 0.02 * t)
        clips_list.append(clip)
        
    background = concatenate_videoclips(clips_list)
    background = background.subclip(0, total_duration)

    # Apply Vignette & Color Grade
    background = background.fl_image(vignette)
    background = background.fx(vfx.colorx, 0.4) # Darken for text readability

    clips = [background]
    
    # --- TEXT ENGINE (Safety Margins) ---
    words = riddle_text.split()
    # 95% speed makes text feel "snappy"
    word_duration = (voice_audio.duration * 0.95) / len(words) 
    current_time = 0
    font_choice = 'Impact' if 'Impact' in TextClip.list('font') else 'DejaVu-Sans-Bold'

    for word in words:
        clean_word = word.replace(".", "").replace(",", "").replace("?", "").replace("!", "")
        
        # DYNAMIC FONT SIZING
        base_size = 170
        if len(clean_word) > 6: base_size = 130
        if len(clean_word) > 9: base_size = 100
        
        # Highlight Keywords
        is_keyword = clean_word.lower() in ['you', 'dead', 'kill', 'run', 'what', 'who']
        color = 'red' if is_keyword else 'white'
        
        txt = TextClip(
            clean_word.upper(),
            fontsize=base_size,       
            color=color,
            font=font_choice,
            stroke_color='black',
            stroke_width=5,
            size=(1000, None), # Constrain width to safe area
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
            music = music.loop(duration=total_duration + 5)
        music = music.subclip(0, total_duration).volumex(0.3) 
        final_audio_tracks.append(music)

    final_audio = CompositeAudioClip(final_audio_tracks)
    
    final = CompositeVideoClip(clips).set_duration(total_duration).set_audio(final_audio)
    final.write_videofile("final_render.mp4", fps=24, codec='libx264', audio_codec='aac')
    print("Video ready.")

def upload_to_youtube(riddle_text, answer_text, theme):
    print("6. Uploading...")
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"]
    )

    youtube = build("youtube", "v3", credentials=creds)

    # Random Title Logic for variety
    title_options = [
        f"Only 1% Can Solve This 🧠 #shorts",
        f"Test Your Logic: {theme} 👁️ #shorts",
        f"Do NOT Watch At Night ⚠️ #shorts",
        f"Can You Guess The Answer? #shorts"
    ]
    title = random.choice(title_options)
    
    description = (
        f"Can you answer this?\n\n"
        f"Answer: || {answer_text} ||\n\n"
        f"#riddle #horror #{theme.replace(' ', '')} #logic"
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": ["shorts", "scary", "riddle", "logic", "mystery"],
                "categoryId": "24"
            },
            "status": { "privacyStatus": "public" }
        },
        media_body=MediaFileUpload("final_render.mp4")
    )
    response = request.execute()
    print(f"Live: https://youtu.be/{response['id']}")

if __name__ == "__main__":
    data = asyncio.run(generate_content())
    if data:
        riddle, answer, visuals, theme = data
        if riddle:
            edit_video(riddle, answer, visuals, theme)
            upload_to_youtube(riddle, answer, theme)
