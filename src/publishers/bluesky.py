"""
Bluesky Publisher

Posts digests to Bluesky using the AT Protocol.
"""

from typing import Optional
import structlog

from atproto import Client

from src.config import settings

logger = structlog.get_logger()


def post_to_bluesky(text: str, image_path: Optional[str] = None) -> bool:
    """
    Post content to Bluesky.
    
    Args:
        text: Post text (max 300 chars)
        image_path: Optional path to image file
        
    Returns:
        True if successful, False otherwise
    """
    if not settings.BLUESKY_HANDLE or not settings.BLUESKY_APP_PASSWORD:
        logger.warning("bluesky_credentials_missing")
        return False
    
    logger.info("bluesky_post_started", text_length=len(text))
    
    try:
        client = Client()
        client.login(settings.BLUESKY_HANDLE, settings.BLUESKY_APP_PASSWORD)
        
        # Truncate text if needed (Bluesky limit is 300 chars)
        if len(text) > 300:
            text = text[:297] + "..."
        
        if image_path:
            # Upload image and post with embed
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            blob = client.upload_blob(image_data)
            
            embed = {
                '$type': 'app.bsky.embed.images',
                'images': [{
                    'image': blob.blob,
                    'alt': 'Zeitgeist digest illustration'
                }]
            }
            
            response = client.post(text=text, embed=embed)
        else:
            response = client.post(text=text)
        
        logger.info("bluesky_post_success", uri=response.uri)
        return True
        
    except Exception as e:
        logger.error("bluesky_post_failed", error=str(e))
        return False


def get_bluesky_profile():
    """Get the current Bluesky profile info."""
    try:
        client = Client()
        client.login(settings.BLUESKY_HANDLE, settings.BLUESKY_APP_PASSWORD)
        
        profile = client.get_profile(settings.BLUESKY_HANDLE)
        return {
            "handle": profile.handle,
            "display_name": profile.display_name,
            "followers": profile.followers_count,
            "following": profile.follows_count,
            "posts": profile.posts_count
        }
    except Exception as e:
        logger.error("bluesky_profile_failed", error=str(e))
        return None


if __name__ == "__main__":
    # Test posting
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Check profile
    profile = get_bluesky_profile()
    if profile:
        print(f"Connected as: @{profile['handle']}")
        print(f"Followers: {profile['followers']}")
    
    # Test post (commented out to avoid accidental posting)
    # post_to_bluesky("🧪 Test post from Zeitgeist Engine #test")
