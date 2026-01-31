import json
import os
import glob

class ChallengeLoader:
    def __init__(self):
        self.file = "challenges.json"
        self.load()
    
    def load(self):
        """Load challenges from JSON file"""
        if os.path.exists(self.file):
            with open(self.file, 'r') as f:
                self.data = json.load(f)
        else:
            print("⚠️  challenges.json not found. Creating default...")
            self.data = {
                "active_challenge": None, 
                "challenge_history": [], 
                "upcoming_challenges": []
            }
            self.save()
    
    def save(self):
        """Save challenges to JSON file"""
        with open(self.file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def get_active_challenge(self):
        """Get currently active challenge"""
        return self.data.get("active_challenge")
    
    def should_switch_challenge(self, current_gen):
        """Check if we've reached target gen for current challenge"""
        active = self.get_active_challenge()
        if active and current_gen >= active.get("target_gen", 999999):
            return True
        return False
    
    def switch_to_next_challenge(self, current_gen):
        """Move current challenge to history, activate next one"""
        active = self.get_active_challenge()
        
        # Archive current challenge
        if active:
            active['end_gen'] = current_gen
            active['completed'] = True
            active['video_posted'] = False  # Mark for video creation
            self.data['challenge_history'].append(active)
        
        # Get next challenge
        upcoming = self.data.get('upcoming_challenges', [])
        if upcoming:
            next_challenge = upcoming.pop(0)
            next_challenge['start_gen'] = current_gen + 1
            # Set target based on difficulty or default to 200 gens
            default_duration = 200
            next_challenge['target_gen'] = current_gen + default_duration
            self.data['active_challenge'] = next_challenge
            self.data['upcoming_challenges'] = upcoming
            self.save()
            
            print(f"\n{'='*60}")
            print(f"🎯 NEW CHALLENGE ACTIVATED: {next_challenge['name']}")
            print(f"📊 Gen Range: {next_challenge['start_gen']} → {next_challenge['target_gen']}")
            print(f"🎬 Hook: {next_challenge['video_hook']}")
            print(f"{'='*60}\n")
            
            return next_challenge
        else:
            print("\n🏆 ALL CHALLENGES COMPLETED! Add more to challenges.json")
            return None
    
    def apply_challenge_config(self, challenge):
        """Apply challenge config changes to theme.json"""
        with open("theme.json", 'r') as f:
            theme = json.load(f)
        
        changes = challenge.get("config_changes", {})
        
        # Deep merge the changes
        if "physics" in changes:
            if "physics" not in theme:
                theme["physics"] = {}
            theme["physics"].update(changes["physics"])
        
        if "visuals" in changes:
            if "visuals" not in theme:
                theme["visuals"] = {}
            theme["visuals"].update(changes["visuals"])
        
        if "controls" in changes:
            if "controls" not in theme:
                theme["controls"] = {}
            theme["controls"].update(changes["controls"])
        
        if "sensors" in changes:
            if "sensors" not in theme:
                theme["sensors"] = {}
            theme["sensors"].update(changes["sensors"])
        
        if "map" in changes:
            if "map" not in theme:
                theme["map"] = {}
            theme["map"].update(changes["map"])
        
        # Apply car style if specified
        if "car_style" in challenge:
            theme["car_style"] = challenge["car_style"]
            print(f"🚗 Car style set to: {challenge['car_style']}")
        
        with open("theme.json", 'w') as f:
            json.dump(theme, f, indent=2)
        
        print(f"✅ Applied challenge config: {challenge['name']}")
        return theme
    
    def get_last_completed_challenge(self):
        """Get the most recently completed challenge (for video creation)"""
        history = self.data.get('challenge_history', [])
        if history:
            for challenge in reversed(history):
                if not challenge.get('video_posted', False):
                    return challenge
        return None
    
    def mark_video_posted(self, challenge_id):
        """Mark that a video has been created for this challenge"""
        history = self.data.get('challenge_history', [])
        for challenge in history:
            if challenge['id'] == challenge_id:
                challenge['video_posted'] = True
                break
        self.save()
    
    def get_challenge_dir_name(self, challenge):
        """Get directory-safe name for challenge"""
        if not challenge:
            return "training"
        return challenge['name'].lower().replace(" ", "_")
    
    def get_clips_for_challenge(self, challenge_id):
        """Get all video clips for a specific challenge"""
        challenge = None
        
        # Find challenge in history
        for hist_challenge in self.data.get('challenge_history', []):
            if hist_challenge['id'] == challenge_id:
                challenge = hist_challenge
                break
        
        # Check active challenge
        if not challenge:
            active = self.get_active_challenge()
            if active and active['id'] == challenge_id:
                challenge = active
        
        if not challenge:
            return []
        
        challenge_dir = os.path.join("training_clips", self.get_challenge_dir_name(challenge))
        
        if not os.path.exists(challenge_dir):
            return []
        
        clips = sorted(glob.glob(os.path.join(challenge_dir, "gen_*.mp4")))
        return clips
    
    def get_clip_for_generation(self, generation):
        """Find the clip file for a specific generation"""
        # First check active challenge
        active = self.get_active_challenge()
        if active and active['start_gen'] <= generation <= active.get('target_gen', 999999):
            challenge_dir = os.path.join("training_clips", self.get_challenge_dir_name(active))
            clip_path = os.path.join(challenge_dir, f"gen_{generation:05d}.mp4")
            if os.path.exists(clip_path):
                return clip_path
        
        # Check challenge history
        for challenge in self.data.get('challenge_history', []):
            if challenge.get('start_gen') <= generation <= challenge.get('end_gen', 999999):
                challenge_dir = os.path.join("training_clips", self.get_challenge_dir_name(challenge))
                clip_path = os.path.join(challenge_dir, f"gen_{generation:05d}.mp4")
                if os.path.exists(clip_path):
                    return clip_path
        
        # Fallback: search all directories
        all_clips = glob.glob(os.path.join("training_clips", "**", f"gen_{generation:05d}.mp4"), recursive=True)
        if all_clips:
            return all_clips[0]
        
        return None
