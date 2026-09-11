"""
YouTube Video Validation
========================
Validates YouTube videos before displaying in UI.
"""
import asyncio
import logging
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)

class YouTubeValidator:
    """Validates YouTube video availability"""
    
    def __init__(self):
        self.oembed_endpoint = "https://www.youtube.com/oembed"
    
    async def validate_video(self, video_id: str, url: str, search_id: str = "unknown") -> Dict[str, Any]:
        """
        Validate YouTube video availability using oEmbed API
        Returns validation result with metadata
        """
        logger.info(f"[{search_id}] Validating YouTube video: {video_id}")
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    self.oembed_endpoint,
                    params={
                        'url': url,
                        'format': 'json'
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"[{search_id}] YouTube video valid: {video_id} - {data.get('title', 'Unknown')}")
                    return {
                        'valid': True,
                        'availability_status': 'available',
                        'title': data.get('title', f'YouTube Video {video_id}'),
                        'author_name': data.get('author_name', 'Unknown Channel'),
                        'thumbnail_url': data.get('thumbnail_url'),
                        'error': None
                    }
                elif response.status_code == 404:
                    logger.warning(f"[{search_id}] YouTube video not found: {video_id}")
                    return {
                        'valid': False,
                        'availability_status': 'not_found',
                        'title': f'Video {video_id}',
                        'author_name': '',
                        'error': 'Video not found or unavailable'
                    }
                elif response.status_code == 401 or response.status_code == 403:
                    logger.warning(f"[{search_id}] YouTube video private/restricted: {video_id}")
                    return {
                        'valid': False,
                        'availability_status': 'private_or_restricted',
                        'title': f'Video {video_id}',
                        'author_name': '',
                        'error': 'Video is private or age-restricted'
                    }
                else:
                    logger.warning(f"[{search_id}] YouTube validation failed with status {response.status_code}")
                    return {
                        'valid': False,
                        'availability_status': 'unknown',
                        'title': f'Video {video_id}',
                        'author_name': '',
                        'error': f'Validation failed: HTTP {response.status_code}'
                    }
                    
        except asyncio.TimeoutError:
            logger.warning(f"[{search_id}] YouTube validation timeout for: {video_id}")
            return {
                'valid': True,  # Assume valid on timeout to avoid false negatives
                'availability_status': 'timeout',
                'title': f'YouTube Video {video_id}',
                'author_name': 'Unknown Channel',
                'error': 'Validation timeout - assuming available'
            }
        except Exception as e:
            logger.error(f"[{search_id}] YouTube validation error for {video_id}: {e}")
            return {
                'valid': True,  # Assume valid on error to avoid false negatives
                'availability_status': 'error',
                'title': f'YouTube Video {video_id}',
                'author_name': 'Unknown Channel',
                'error': f'Validation error: {str(e)}'
            }
    
    async def validate_multiple(self, videos: list, search_id: str = "unknown") -> list:
        """Validate multiple videos concurrently"""
        tasks = [
            self.validate_video(v['video_id'], v['url'], search_id) 
            for v in videos 
            if v.get('video_id')
        ]
        
        if not tasks:
            return []
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        validated = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[{search_id}] Video validation exception: {result}")
                validated.append({
                    'valid': False,
                    'availability_status': 'exception',
                    'error': str(result)
                })
            else:
                validated.append(result)
        
        return validated