"""
Mastodon Publisher

Posts digests to Mastodon using the Mastodon.py library.
"""

from typing import Optional
import structlog

from mastodon import Mastodon

from src.config import settings

logger = structlog.get_logger()


def get_mastodon_client() -> Mastodon:
    """Initialize Mastodon client with credentials."""
    return Mastodon(
        access_token=settings.MASTODON_ACCESS_TOKEN,
        api_base_url=settings.MASTODON_INSTANCE
    )


def post_to_mastodon(text: str, image_path: Optional[str] = None) -> bool:
    """
    Post content to Mastodon.
    
    Args:
        text: Post text (max 500 chars for most instances)
        image_path: Optional path to image file
        
    Returns:
        True if successful, False otherwise
    """
    if not settings.MASTODON_ACCESS_TOKEN:
        logger.warning("mastodon_credentials_missing")
        return False
    
    logger.info("mastodon_post_started", text_length=len(text))
    
    try:
        mastodon = get_mastodon_client()
        
        # Truncate text if needed (most instances have 500 char limit)
        if len(text) > 500:
            text = text[:497] + "..."
        
        if image_path:
            # Upload image and post with media
            media = mastodon.media_post(
                image_path,
                description='Zeitgeist digest illustration'
            )
            response = mastodon.status_post(text, media_ids=[media['id']])
        else:
            response = mastodon.status_post(text)
        
        logger.info("mastodon_post_success", 
                    id=response['id'],
                    url=response.get('url', ''))
        return True
        
    except Exception as e:
        logger.error("mastodon_post_failed", error=str(e))
        return False


def get_mastodon_account_info():
    """Get the current Mastodon account info."""
    try:
        mastodon = get_mastodon_client()
        account = mastodon.account_verify_credentials()
        
        return {
            "username": account['username'],
            "display_name": account['display_name'],
            "followers": account['followers_count'],
            "following": account['following_count'],
            "statuses": account['statuses_count'],
            "instance": settings.MASTODON_INSTANCE
        }
    except Exception as e:
        logger.error("mastodon_account_failed", error=str(e))
        return None


if __name__ == "__main__":
    # Test connection
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Check account
    account = get_mastodon_account_info()
    if account:
        print(f"Connected as: @{account['username']}@{account['instance'].replace('https://', '')}")
        print(f"Followers: {account['followers']}")
    
    # Test post (commented out to avoid accidental posting)
    # post_to_mastodon("🧪 Test post from Zeitgeist Engine #test")
