#!/usr/bin/env python3
"""
Content Strategy Manager - Ensures daily content evolves with the AI
"""
import json
import os
from datetime import datetime

CONTENT_STATE_FILE = ".content_state.json"

class ContentStrategy:
    """
    Manages what type of content to create based on:
    - How many days into current challenge
    - AI's current skill level
    - Narrative arc (beginning → middle → climax)
    """
    
    PHASES = {
        "INTRO": {
            "days": "1-3",
            "theme": "The Challenge Begins",
            "hooks": [
                "Can AI learn to {challenge}?",
                "Day 1 of {challenge}: Complete chaos",
                "500 generations to master this...",
                "The journey begins 💀"
            ],
            "style": "chaotic",  # Fast cuts, crash sounds, red colors
            "frequency": 3  # 3 videos/day
        },
        "LEARNING": {
            "days": "4-15", 
            "theme": "The Grind",
            "hooks": [
                "Day {day}: Small wins 📈",
                "It's learning... slowly",
                "The breakthrough moment! ✨",
                "From crashes to confidence",
                "The evolution is REAL",
                "Watch it adapt 🧠"
            ],
            "style": "progressive",  # Side-by-side comparisons
            "frequency": 3
        },
        "IMPROVING": {
            "days": "16-30",
            "theme": "Getting Good",
            "hooks": [
                "Day {day}: Actually impressive 🤯",
                "Wait... it's getting GOOD",
                "This lap is CLEAN ✨",
                "Almost perfect...",
                "The improvement is insane",
                "Almost there! 🎯"
            ],
            "style": "highlight",  # Cinematic angles, slow-mo on drifts
            "frequency": 2  # Reduce to 2/day - quality over quantity
        },
        "MASTERY": {
            "days": "31-45",
            "theme": "Perfection",
            "hooks": [
                "Day {day}: PURE PERFECTION 🏆",
                "Watch this line... 🤌",
                "It can't get better than this",
                "The PERFECT lap",
                "AI has transcended",
                "Absolutely dialed in ✨"
            ],
            "style": "cinematic",  # Epic music, smooth cuts
            "frequency": 1  # 1 highlight video/day
        },
        "FINALE": {
            "days": "46-50",
            "theme": "Challenge Complete",
            "hooks": [
                "FINAL DAY: The master at work 🏆",
                "Challenge COMPLETE! 🎉",
                "From zero to hero",
                "The complete journey",
                "Next challenge loading... 👀"
            ],
            "style": "compilation",  # Full story recap
            "frequency": 1
        }
    }
    
    def __init__(self):
        self.state = self.load_state()
    
    def load_state(self):
        if os.path.exists(CONTENT_STATE_FILE):
            with open(CONTENT_STATE_FILE, 'r') as f:
                return json.load(f)
        return {
            "current_day": 1,
            "current_challenge": None,
            "challenge_start_gen": 0,
            "total_posts": 0,
            "phase": "INTRO"
        }
    
    def save_state(self):
        with open(CONTENT_STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def update_challenge(self, challenge_name, start_gen):
        """Called when a new challenge starts"""
        if self.state.get("current_challenge") != challenge_name:
            # New challenge! Reset day counter
            self.state = {
                "current_day": 1,
                "current_challenge": challenge_name,
                "challenge_start_gen": start_gen,
                "total_posts": self.state.get("total_posts", 0),
                "phase": "INTRO"
            }
            self.save_state()
            print(f"🎯 New challenge: {challenge_name} - Day 1")
    
    def get_current_phase(self):
        """Determine which content phase we're in"""
        day = self.state.get("current_day", 1)
        
        if day <= 3:
            return "INTRO"
        elif day <= 15:
            return "LEARNING"
        elif day <= 30:
            return "IMPROVING"
        elif day <= 45:
            return "MASTERY"
        else:
            return "FINALE"
    
    def advance_day(self):
        """Call this after each daily training run"""
        self.state["current_day"] = self.state.get("current_day", 1) + 1
        new_phase = self.get_current_phase()
        
        if new_phase != self.state.get("phase"):
            print(f"🎬 Content phase change: {self.state['phase']} → {new_phase}")
            self.state["phase"] = new_phase
        
        self.save_state()
    
    def get_today_strategy(self):
        """Get the content strategy for today"""
        phase_name = self.get_current_phase()
        phase = self.PHASES[phase_name]
        day = self.state["current_day"]
        
        # Pick hooks based on day
        hooks = phase["hooks"]
        hook_index = (day - 1) % len(hooks)
        
        return {
            "phase": phase_name,
            "day": day,
            "theme": phase["theme"],
            "hook_template": hooks[hook_index],
            "style": phase["style"],
            "videos_per_day": phase["frequency"],
            "challenge": self.state.get("current_challenge", "Training")
        }
    
    def get_video_count_for_today(self):
        """How many videos should we post today?"""
        strategy = self.get_today_strategy()
        return strategy["videos_per_day"]
    
    def format_hook(self, hook_template, challenge_name):
        """Format a hook template with variables"""
        day = self.state.get("current_day", 1)
        return hook_template.format(
            challenge=challenge_name,
            day=day
        )


# Standalone test
if __name__ == "__main__":
    strategy = ContentStrategy()
    
    # Simulate days
    print("Content Strategy Simulation:\n")
    
    for day in range(1, 52, 5):  # Every 5 days
        strategy.state["current_day"] = day
        today = strategy.get_today_strategy()
        
        print(f"Day {day:2d} | Phase: {today['phase']:12s} | Videos: {today['videos_per_day']} | Theme: {today['theme']}")
        print(f"       Hook: {strategy.format_hook(today['hook_template'], 'Drift Master')}")
        print()
