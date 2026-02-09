"""YouTube video upload functionality."""

from pathlib import Path

from src.config import get_settings
from src.constants import YouTube
from src.logging_config import get_logger

logger = get_logger(__name__)

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False


class YouTubeUploader:
    """Uploads videos to YouTube."""

    def __init__(self) -> None:
        """Initialize the uploader."""
        if not GOOGLE_AVAILABLE:
            raise RuntimeError("Google API client is required for YouTube upload")
        
        self.settings = get_settings()
        self.youtube = None

    def authenticate(self) -> None:
        """Authenticate with YouTube API."""
        creds = Credentials(
            None,
            refresh_token=self.settings.youtube.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.settings.youtube.client_id,
            client_secret=self.settings.youtube.client_secret,
        )
        self.youtube = build("youtube", "v3", credentials=creds)
        logger.info("youtube_authenticated")

    def upload(self, video_path: Path, generation: int) -> str | None:
        """Upload a video to YouTube.
        
        Args:
            video_path: Path to video file
            generation: Final generation number for metadata
            
        Returns:
            Video ID if successful, None otherwise
        """
        if not self.settings.enable_youtube_upload:
            logger.info("youtube_upload_disabled")
            return None
        
        if not self.youtube:
            self.authenticate()
        
        # Get title from theme or generate
        theme = get_settings()
        from src.video.producer import VideoProducer
        producer = VideoProducer()
        title = producer.get_viral_title(generation)
        
        # Build description
        description = f"""Watch AI learn to drive from scratch! 🧬🚗 
This is Generation {generation} of an evolutionary algorithm.

Progression:
- Gen 0: Complete chaos
- Gen {generation}: Optimized neural network

Subscribe to see if it can master the track! 

#ai #machinelearning #python #coding #racing #simulation #neuralnetwork #tech #programming
"""
        
        body = {
            "snippet": {
                "title": title[:YouTube.MAX_TITLE_LENGTH],
                "description": description,
                "tags": YouTube.DEFAULT_TAGS,
                "categoryId": YouTube.CATEGORY_ID,
            },
            "status": {
                "privacyStatus": "public",
            },
        }
        
        logger.info(
            "uploading_to_yTube",
            title=title[:50],
            path=str(video_path),
        )
        
        try:
            request = self.youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=MediaFileUpload(str(video_path)),
            )
            response = request.execute()
            video_id = response["id"]
            
            logger.info(
                "upload_complete",
                video_id=video_id,
                url=f"https://youtu.be/{video_id}",
            )
            return video_id
            
        except Exception as e:
            logger.error("upload_failed", error=str(e))
            return None
