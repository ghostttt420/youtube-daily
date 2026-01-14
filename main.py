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

# --- TARGET TOPICS: LOGIC & DARK PSYCHOLOGY ---
TOPICS = {
    "Dark Riddle": "black smoke ink water abstract dark",
    "Paradox": "abstract geometry dark mystic",
    "Impossible Logic": "optical illusion dark abstract",
    "Psychology Test": "ink blot dark rorschach",
    "Detective Puzzle": "noir rain window dark",
    "Lateral Thinking": "abstract maze dark"
}

async def generate_content():
    print("1. Initiating Logic Trap...")
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

    print("2. Generating Riddle...")
    # PROMPT: STRICT FORMAT "Riddle || Answer"
    prompt = (
        f"Write a hard, short {topic_name}. "
        "Structure: The Riddle (2 short sentences) || The Answer (1-2 words). "
        "Style: Mysterious, Dark, Sherlock Holmes. "
        "Do not use emojis. Do not use intro text."
    )

    try:
        response = model.generate_content(prompt)
        full_text = response.text.strip()
        
        # Robust Splitting Logic
        if "||" in full_text:
            riddle, answer = full_text.split("||")
        else:
            # Fallback if AI forgets the separator
            print("Warning: format issue, using fallback.")
            riddle = full_text
            answer = "Check Comments" 
            
    except Exception as e:
        print(f"AI Error: {e}")
        riddle = "I speak without a mouth and hear without ears. I have no body, but I come alive with wind."
        answer = "Echo"
        visual_keyword = "dark smoke"

    print(f"Riddle: {riddle}")
    print(f"Answer: {answer}")

    print("3. Synthesizing Voice...")
    voice = "en-US-ChristopherNeural" 
    
    # Generate audio ONLY for the riddle. The answer is silent (visual reveal).
    communicate = edge_tts.Communicate(riddle, voice)
    await communicate.save("riddle_voice.mp3")

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
        # Create a dummy file or exit
        return None, None, None

    return riddle, answer, topic_name

def edit_video(riddle_text, answer_text, topic_name):
    print("5. Compiling Logic Trap (Word-by-Word)...")
    if not riddle_text: return

    voice_audio = AudioFileClip("riddle_voice.mp3")
    background = VideoFileClip("background.mp4")

    # Duration: Audio + 2s Pause + 2s Answer
    total_duration = voice_audio.duration + 4.0 
    
    # Loop background to fit total duration
    if background.duration < total_duration:
        background = background.loop(duration=total_duration)

    # Darken background heavily (0.3) so white text pops
    background = background.subclip(0, total_duration).resize(height=1920).fx(vfx.colorx, 0.3)

    clips = [background]
    
    # --- WORD STACKING ENGINE ---
    words = riddle_text.split()
    word_duration = voice_audio.duration / len(words)
    current_time = 0
    
    # Font Logic: Impact is best for memes/shorts. Fallback to DejaVu.
    font_choice = 'Impact' if 'Impact' in TextClip.list('font') else 'DejaVu-Sans-Bold'

    for word in words:
        # Clean punctuation for a cleaner visual look
        clean_word = word.replace(".", "").replace(",", "").replace("?", "").replace("!", "").replace('"', "")
        
        txt = TextClip(
            clean_word.upper(),
            fontsize=130,       # HUGE SIZE
            color='white',
            font=font_choice,
            stroke_color='black',
            stroke_width=4,
            size=(1000, None),
            method='caption'
        )
        
        txt = txt.set_pos('center').set_start(current_time).set_duration(word_duration)
        clips.append(txt)
        current_time += word_duration

    # --- THE "THINKING" PAUSE (2 Seconds) ---
    pause_txt = TextClip(
        "???",
        fontsize=160,
        color='red',
        font=font_choice
    ).set_pos('center').set_start(current_time).set_duration(2.0)
    clips.append(pause_txt)
    current_time += 2.0

    # --- THE ANSWER REVEAL (2 Seconds) ---
    answer_txt = TextClip(
        answer_text.strip().upper(),
        fontsize=110,
        color='#00FF41', # Green
        font=font_choice,
        stroke_color='black',
        stroke_width=5,
        size=(900, None),
        method='caption'
    ).set_pos('center').set_start(current_time).set_duration(2.0)
    clips.append(answer_txt)

    # AUDIO MIX
    final_audio = CompositeAudioClip([voice_audio.set_start(0)])
    
    final = CompositeVideoClip(clips).set_duration(total_duration).set_audio(final_audio)
    final.write_videofile("logic_trap.mp4", fps=24, codec='libx264', audio_codec='aac')
    print("Video saved as logic_trap.mp4")

def upload_to_youtube(riddle_text, answer_text, topic_name):
    print("6. Uploading to Network...")
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"]
    )

    youtube = build("youtube", "v3", credentials=creds)

    title = f"Only 1% Can Solve This 🧠 #shorts #riddle"
    
    description = (
        f"Test your logic.\n"
        f"Subscribe for daily challenges.\n\n"
        f"⬇️ ANSWER BELOW ⬇️\n\n\n\n\n"
        f"Answer: || {answer_text} ||\n\n"
        "#riddle #puzzle #logic #brainteaser #mindgames"
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": ["shorts", "riddle", "puzzle", "logic", "mind games"],
                "categoryId": "27" # Education
            },
            "status": {
                "privacyStatus": "public" 
            }
        },
        media_body=MediaFileUpload("logic_trap.mp4")
    )
    response = request.execute()
    print(f"Transmission Complete: https://youtu.be/{response['id']}")

if __name__ == "__main__":
    data = asyncio.run(generate_content())
    if data:
        riddle, answer, topic = data
        if riddle:
            edit_video(riddle, answer, topic)
            upload_to_youtube(riddle, answer, topic)
