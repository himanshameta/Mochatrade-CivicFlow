"""
YouTube Enhancement Providers
============================
Handles YouTube metadata and transcript extraction with safe failure handling.
"""
import re
import asyncio
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

class YouTubeMetadataProvider:
    """Extracts YouTube video metadata from URL"""
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
            r'youtube\.com\/watch\?.*v=([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def is_youtube_url(self, url: str) -> bool:
        """Check if URL is a YouTube video"""
        return 'youtube.com' in url.lower() or 'youtu.be' in url.lower()
    
    def get_basic_metadata(self, url: str) -> Dict[str, Any]:
        """Extract basic metadata from YouTube URL"""
        video_id = self.extract_video_id(url)
        if not video_id:
            return {"error": "Invalid YouTube URL"}
        
        return {
            "video_id": video_id,
            "url": url,
            "title": f"YouTube Video {video_id}",  # Fallback title
            "channel": "Unknown Channel",
            "duration": None,
            "thumbnail": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        }

class YouTubeTranscriptProvider:
    """Handles YouTube transcript extraction with safe failure"""
    
    def __init__(self):
        self._youtube_transcript_api = None
        self._import_attempted = False
    
    def _lazy_import_transcript_api(self) -> bool:
        """Lazy import youtube_transcript_api with safe failure"""
        if self._import_attempted:
            return self._youtube_transcript_api is not None
            
        self._import_attempted = True
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            self._youtube_transcript_api = YouTubeTranscriptApi
            return True
        except ImportError:
            print("[YouTube] youtube_transcript_api not available")
            return False
        except Exception as e:
            print(f"[YouTube] Failed to import transcript API: {e}")
            return False
    
    async def get_transcript(self, video_id: str, languages: list = None) -> Dict[str, Any]:
        """Get transcript with safe failure handling"""
        if not self._lazy_import_transcript_api():
            return {
                "transcript_available": False,
                "error": "transcript_api_unavailable",
                "transcript_text": None
            }
        
        if languages is None:
            languages = ['en', 'hi', 'en-US', 'en-GB']
        
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            transcript_list = await loop.run_in_executor(
                None, 
                self._youtube_transcript_api.list_transcripts, 
                video_id
            )
            
            # Try to get transcript in preferred languages
            transcript = None
            for lang in languages:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    break
                except:
                    continue
            
            if not transcript:
                # Try first available transcript
                available = list(transcript_list)
                if available:
                    transcript = available[0]
            
            if transcript:
                transcript_data = await loop.run_in_executor(
                    None, transcript.fetch
                )
                
                # Combine all text
                full_text = " ".join([entry['text'] for entry in transcript_data])
                
                return {
                    "transcript_available": True,
                    "transcript_source": transcript.language,
                    "transcript_text": full_text,
                    "transcript_entries": len(transcript_data)
                }
            else:
                return {
                    "transcript_available": False,
                    "error": "no_transcript_available",
                    "transcript_text": None
                }
                
        except Exception as e:
            error_type = "unknown_error"
            if "disabled" in str(e).lower():
                error_type = "transcript_disabled"
            elif "private" in str(e).lower() or "unavailable" in str(e).lower():
                error_type = "video_unavailable"
            elif "quota" in str(e).lower() or "rate" in str(e).lower():
                error_type = "rate_limited"
            
            return {
                "transcript_available": False,
                "error": error_type,
                "error_message": str(e),
                "transcript_text": None
            }

class GuidanceSummarizer:
    """Generates guidance summaries from transcript text"""
    
    def __init__(self, llm_client):
        self.llm = llm_client
    
    async def summarize_transcript(self, transcript_text: str, service_name: str) -> Dict[str, Any]:
        """Summarize transcript into actionable guidance"""
        if not transcript_text or not self.llm.api_key:
            return {
                "transcript_summary": None,
                "key_steps": [],
                "mentioned_documents": [],
                "mentioned_warnings": []
            }
        
        # Truncate very long transcripts
        max_length = 3000
        if len(transcript_text) > max_length:
            transcript_text = transcript_text[:max_length] + "..."
        
        prompt = f"""
        Analyze this YouTube video transcript about "{service_name}" and extract:
        
        Transcript: {transcript_text}
        
        Return ONLY valid JSON:
        {{
          "transcript_summary": "Brief 2-sentence summary",
          "key_steps": ["step1", "step2"],
          "mentioned_documents": ["doc1", "doc2"],
          "mentioned_warnings": ["warning1", "warning2"]
        }}
        """
        
        try:
            response = await self.llm.generate_content(
                prompt=prompt, 
                temperature=0.1, 
                max_tokens=400
            )
            
            # Clean JSON
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            import json
            return json.loads(response.strip())
            
        except Exception as e:
            print(f"[YouTube] Transcript summarization failed: {e}")
            return {
                "transcript_summary": "Video contains guidance but analysis failed",
                "key_steps": [],
                "mentioned_documents": [],
                "mentioned_warnings": []
            }