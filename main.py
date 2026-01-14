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
user_agent = "FactGhostBot/1.0 (contact: your@email.com)"
wiki_wiki = wikipediaapi.Wikipedia(user_agent=user_agent, language='en')

# --- 1. THE RESEARCHER (Finds Real Content) ---
def get_real_story():
    print("1. Searching Archives...")
    # List of categories that contain "High Tier" weird/interesting content
    categories = [
        "Category:Unexplained disappearances",
        "Category:Out-of-place artifacts",
        "Category:Unidentified sounds",
        "Category:Urban legends",
        "Category:Internet mysteries"
    ]
    
    # We pick a random category, then a random page from it
    target_cat = random.choice(categories)
    cat = wiki_wiki.page(target_cat)
    
    # Get all pages in category
    pages = list(cat.categorymembers.values())
    # Filter out boring "List of..." pages
    valid_pages = [p for p in pages if "List of" not in p.title and "Category:" not in p.title]
    
    if not valid_pages:
        # Fallback if category is empty
        return "The Bloop", "https://upload.wikimedia.org/wikipedia/commons/6/6f/The_Bloop_Spectrogram.jpeg"

    chosen_page = random.choice(valid_pages)
    print(f"Target Acquired: {chosen_page.title}")
    
    # Get the Main Image (This makes it 'Top Tier' - REAL visuals)
    # Note: Wikipedia API image handling is tricky, we scrape the main image URL
    image_url = get_wiki_image(chosen_page.title)
    
    return chosen_page.title, chosen_page.summary[0:500], image_url

def get_wiki_image(title):
    """Fetches the main image URL from a Wikipedia page title using MediaWiki API"""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "pageimages",
        "pithumbsize": 1000 # High res
    }
    try:
        r = requests.get(url, params=params)
        data = r.json()
        pages = data["query"]["pages"]
        for k, v in pages.items():
            if "thumbnail" in v:
                return v["thumbnail"]["source"]
    except:
        pass
    return None # Return None if no image found

# --- 2. THE WRITER (Scripting) ---
async def create_documentary_script(title, summary):
    print("2. Writing Script...")
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = (
        f"Create a viral YouTube Short script about: {title}. "
        f"Context: {summary}. "
        "Style: True Crime / Documentary / Mystery. "
        "Structure: "
        "- Hook (1 sentence): Make them curious. "
        "- The Fact (2 sentences): Explain the mystery. "
        "- The Question (1 sentence): Ask what they think. "
        "Total under 40 words. No intro."
    )
    
    response = model.generate_content(prompt)
    return response.text.strip()

# --- 3. THE EDITOR (Ken Burns Effect) ---
def create_ken_burns_clip(image_path, duration):
    """Creates a slow zoom/pan effect on a static image"""
    clip = ImageClip(image_path).set_duration(duration)
    
    # Force 9:16 Aspect Ratio (1080x1920)
    # We resize so the image covers the whole height, then center crop
    clip = clip.resize(height=1920)
    if clip.w < 1080:
        clip = clip.resize(width=1080)
        
    clip = clip.crop(x1=0, y1=0, width=1080, height=1920, x_center=clip.w/2, y_center=clip.h/2)
    
    # The Zoom: Scale from 1.0 to 1.10 over the duration
    clip = clip.resize(lambda t: 1 + 0.04 * t)
    
    return clip

async def main_pipeline():
    # A. RESEARCH
    title, summary, image_url = "None", "None", None
    
    # Retry logic if we find a page with no image (Images are CRITICAL for this format)
    for attempt in range(3):
        title, summary, image_url = get_real_story()
        if image_url: 
            break
        print("No image found, retrying...")
    
    if not image_url:
        # Final fallback
        image_url = "https://upload.wikimedia.org/wikipedia/commons/e/ee/Chain_link_fence_with_barbed_wire_in_mist.jpg" 
        print("Using fallback image.")

    # Download Image
    with open("evidence.jpg", "wb") as f:
        f.write(requests.get(image_url).content)

    # B. SCRIPT
    script = await create_documentary_script(title, summary)
    print(f"Script: {script}")

    # C. VOICE (Narrator)
    # Deep, serious documentary voice
    voice = "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(script, voice, rate="+0%", pitch="-10Hz")
    await communicate.save("narration.mp3")

    # D. EDITING
    print("4. editing Documentary...")
    voice_audio = AudioFileClip("narration.mp3")
    total_duration = voice_audio.duration + 1.5 # Padding

    # Create visual
    video = create_ken_burns_clip("evidence.jpg", total_duration)
    
    # Add Dark Filter (Cinematic)
    video = video.fx(vfx.colorx, 0.6)

    # Add Captions (Professional Style)
    # Instead of flashing words, we use a "Lower Third" or specific subtitles
    # For now, let's stick to the Word-by-Word but with a cleaner font
    clips = [video]
    
    words = script.split()
    word_duration = voice_audio.duration / len(words)
    current_time = 0
    
    for word in words:
        clean_word = word.replace(".", "").replace(",", "")
        txt = TextClip(
            clean_word.upper(),
            fontsize=120,
            color='white',
            font='Impact', # Clean and bold
            stroke_color='black',
            stroke_width=3,
            method='caption',
            size=(1000, None)
        )
        txt = txt.set_pos('center').set_start(current_time).set_duration(word_duration)
        clips.append(txt)
        current_time += word_duration

    # Audio Mix
    final_audio_tracks = [voice_audio.set_start(0)]
    if os.path.exists("music.mp3"):
        music = AudioFileClip("music.mp3")
        if music.duration < total_duration:
            music = music.loop(duration=total_duration + 5)
        music = music.subclip(0, total_duration).volumex(0.2) # Low background
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

    video_title = f"{title}: The Truth 👁️ #shorts"
    description = f"{script}\n\n#mystery #documentary #history #facts"

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": video_title[:100],
                "description": description,
                "tags": ["shorts", "mystery", "documentary"],
                "categoryId": "28" # Science & Tech
            },
            "status": { "privacyStatus": "public" }
        },
        media_body=MediaFileUpload("documentary.mp4")
    )
    print(f"Uploaded: {title}")
    request.execute()

if __name__ == "__main__":
    script, title = asyncio.run(main_pipeline())
    if script:
        upload_to_youtube(script, title)
