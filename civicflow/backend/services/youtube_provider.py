import traceback
from typing import Optional, Dict, Any
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

class YouTubeProvider:
    """Safely extracts metadata and transcripts from YouTube."""
    
    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        if "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        if "youtube.com/watch" in url:
            try:
                params = url.split("?")[1]
                for param in params.split("&"):
                    if param.startswith("v="):
                        return param[2:]
            except IndexError:
                pass
        return None

    @staticmethod
    def get_transcript(video_id: str) -> Dict[str, Any]:
        """Fetches transcript, safely handling failures."""
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            formatter = TextFormatter()
            text = formatter.format_transcript(transcript_list)
            return {
                "available": True,
                "text": text,
                "error": None
            }
        except Exception as e:
            return {
                "available": False,
                "text": "",
                "error": str(e)
            }
