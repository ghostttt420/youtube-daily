import os
import random
import asyncio
import requests
import wikipediaapi
import numpy as np
import google.generativeai as genai
import edge_tts
from moviepy.editor import (
    VideoFileClip, TextClip, CompositeVideoClip, 
    AudioFileClip, CompositeAudioClip, ImageClip, vfx, concatenate_videoclips
)
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# CONFIGURATION
genai.configure(api_key=os.environ["GEMINI_KEY"])

# Wikipedia requires a user agent to prevent blocking
user_agent = "FactGhostBot/2.0 (contact: your-email@gmail.com)"
wiki_wiki = wikipediaapi.Wikipedia(user_agent=user_agent, language='en')

# --- 1. THE RESEARCHER (Finds Real Content) ---
def get_real_story():
    print("1. Searching Archives...")
    # These categories contain "High Tier" mystery/creepy content
    categories = [
        "Category:Unexplained disappearances",
        "Category:Out-of-place artifacts",
        "Category:Unidentified sounds",
        "Category:Urban legends",
        "Category:Internet mysteries",
        "Category:Ghost ships",
        "Category:Unidentified flying objects",
        "Category:Atmospheric ghost lights"
    ]
    
    # Retry logic: Try up to 5 times to find a page with a valid image
    for attempt in range(5):
        try:
            target_cat = random.choice(categories)
            cat = wiki_wiki.page(target_cat)
            
            # Get pages, filter out "List of" and sub-categories
            pages = list(cat.categorymembers.values())
            valid_pages = [p for p in pages if "List of" not in p.title and "Category:" not in p.title]
            
            if not valid_pages: continue

            chosen_page = random.choice(valid_pages)
            print(f"Scanning: {chosen_page.title}...")
            
            # Fetch the main image URL
            image_url = get_wiki_image(chosen_page.title)
            
            if image_url and image_url.endswith(('.jpg', '.jpeg', '.png')):
                print(f"✅ Target Acquired: {chosen_page.title}")
                return chosen_page.title, chosen_page.summary[0:600], image_url
                
        except Exception as e:
            print(f"Search Error: {e}")
            continue
    
    # Fallback if scraping fails
    print("⚠️ Research failed. Using Emergency Backup.")
    return "The Bloop", "The Bloop was an ultra-low-frequency and extremely powerful underwater sound detected by the U.S. National Oceanic and Atmospheric Administration (NOAA) in 1997.", "https://upload.wikimedia.org/wikipedia/commons/6/6f/The_Bloop_Spectrogram.jpeg"

def get_wiki_image(title):
    """Fetches the main high-res image URL from Wikipedia"""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "pageimages",
        "pithumbsize": 1080 # Request High Res (1080px width)
    }
    try:
        r = requests.get(url, params=params, headers={"User-Agent": user_agent})
        data = r.json()
        pages = data["query"]["pages"]
        for k, v in pages.items():
            if "thumbnail" in v:
                return v["thumbnail"]["source"]
    except:
        pass
    return None

# --- 2. THE WRITER (Scripting) ---
async def create_documentary_script(title, summary):
    print("2. Writing Documentary Script...")
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = (
        f"Create a viral YouTube Short script about: {title}. "
        f"Source Material: {summary}. "
        "Style: True Crime / Mystery Documentary. "
        "Structure: "
        "- Hook (1 short sentence): Make them curious. "
        "- The Fact (2 sentences): Explain the weirdest part. "
        "- The Mystery (1 sentence): End with a lingering question. "
        "Constraints: Total under 45 words. No emojis. Tone is serious."
    )
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return f"This is the mystery of {title}. Experts are still baffled by what was found here. What do you think really happened?"

# --- 3. THE EDITOR (Ken Burns Engine) ---
def create_ken_burns_clip(image_path, duration):
    """Creates a slow zoom/pan effect on a static image"""
    clip = ImageClip(image_path).set_duration(duration)
    
    # RESIZE LOGIC: Cover the 1080x1920 frame
    # 1. Scale height to 1920
    if clip.h < 1920:
        clip = clip.resize(height=1920)
    # 2. If width is still too small, scale width to 1080
    if clip.w < 1080:
        clip = clip.resize(width=1080)
        
    # 3. Center Crop
    clip = clip.crop(x1=0, y1=0, width=1080, height=1920, x_center=clip.w/2, y_center=clip.h/2)
    
    # 4. The Zoom: Scale from 1.0 to 1.15 (Slow push in)
    clip = clip.resize(lambda t: 1 + 0.02 * t)
    
    return clip

async def main_pipeline():
    # A. RESEARCH & DOWNLOAD
    title, summary, image_url = get_real_story()

    # Download Image
    try:
        img_data = requests.get(image_url, headers={"User-Agent": user_agent}).content
        with open("evidence.jpg", "wb") as f:
            f.write(img_data)
    except:
        print("Image download failed.")
        return None, None

    # B. SCRIPT
    script = await create_documentary_script(title, summary)
    print(f"Script: {script}")

    # C. VOICE (Narrator)
    # Using Christopher pitched down for that "History Channel" vibe
    voice = "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(script, voice, rate="+0%", pitch="-10Hz")
    await communicate.save("narration.mp3")

    # D. EDITING
    print("4. Editing Documentary...")
    voice_audio = AudioFileClip("narration.mp3")
    total_duration = voice_audio.duration + 2.0

    # Visual Track
    video = create_ken_burns_clip("evidence.jpg", total_duration)
    
    # Cinematic Filter (Darken + Slight Blue Tint for Mystery)
    video = video.fx(vfx.colorx, 0.5)

    clips = [video]
    
    # Text Track (Dynamic Subtitles)
    words = script.split()
    word_duration = (voice_audio.duration * 0.95) / len(words)
    current_time = 0
    font_choice = 'Impact' if 'Impact' in TextClip.list('font') else 'DejaVu-Sans-Bold'
    
    for word in words:
        clean_word = word.replace(".", "").replace(",", "").replace("?", "").replace("!", "")
        
        # Highlight Keywords
        color = 'red' if len(clean_word) > 6 or clean_word.isupper() else 'white'
        
        txt = TextClip(
            clean_word.upper(),
            fontsize=110,
            color=color,
            font=font_choice,
            stroke_color='black',
            stroke_width=4,
            method='caption',
            size=(1000, None)
        )
        txt = txt.set_pos(('center', 1400)).set_start(current_time).set_duration(word_duration) # Positioned lower (subtitle style)
        clips.append(txt)
        current_time += word_duration

    # Audio Mix
    final_audio_tracks = [voice_audio.set_start(0)]
    if os.path.exists("music.mp3"):
        music = AudioFileClip("music.mp3")
        if music.duration < total_duration:
            music = music.loop(duration=total_duration + 5)
        music = music.subclip(0, total_duration).volumex(0.25) 
        final_audio_tracks.append(music)

    final = CompositeVideoClip(clips).set_duration(total_duration).set_audio(CompositeAudioClip(final_audio_tracks))
    final.write_videofile("documentary.mp4", fps=24, codec='libx264', audio_codec='aac')
    
    return script, title

# --- UPLOAD LOGIC ---
def upload_to_youtube(script, title):
    print("5. Uploading...")
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"]
    )
    youtube = build("youtube", "v3", credentials=creds)

    video_title = f"{title}: Unexplained 👁️ #shorts"
    description = f"{script}\n\n#mystery #history #unexplained #creepy #{title.replace(' ', '')}"

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": video_title[:100],
                "description": description,
                "tags": ["shorts", "mystery", "documentary", "history", "creepy"],
                "categoryId": "28" 
            },
            "status": { "privacyStatus": "public" }
        },
        media_body=MediaFileUpload("documentary.mp4")
    )
    response = request.execute()
    print(f"Uploaded: https://youtu.be/{response['id']}")

if __name__ == "__main__":
    data = asyncio.run(main_pipeline())
    if data:
        script, title = data
        if script:
            upload_to_youtube(script, title)
