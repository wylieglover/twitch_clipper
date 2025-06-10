import logging
import requests
import json
from pathlib import Path
from config import settings
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

PROCESSED_FILE = Path(settings.processed_clips_file) if getattr(settings, "processed_clips_file", None) \
                 else Path(__file__).parent / "processed_clips.json"

def _load_seen_ids() -> set[str]:
    if PROCESSED_FILE.exists():
        try:
            return set(json.loads(PROCESSED_FILE.read_text()))
        except Exception as e:
            logger.warning("Could not read processed-clips cache: %s", e)
    return set()

def _save_seen_ids(seen: set[str]) -> None:
    try:
        PROCESSED_FILE.write_text(json.dumps(list(seen)))
    except Exception as e:
        logger.error("Could not write processed-clips cache: %s", e)

def get_twitch_token() -> str:
    """Obtain OAuth token using client credentials flow."""
    try:
        resp = requests.post(
            settings.twitch_token_url,
            params={
                "client_id": settings.twitch_client_id,
                "client_secret": settings.twitch_client_secret,
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise RuntimeError("No access_token returned from Twitch")
        return token
    except requests.RequestException as e:
        logger.error("Error obtaining Twitch token: %s", e)
        raise


def get_user_info(token: str, username: str) -> dict:
    """Lookup Twitch user info by username - returns both ID and display name."""
    try:
        headers = {
            "Client-ID": settings.twitch_client_id,
            "Authorization": f"Bearer {token}"
        }
        resp = requests.get(
            settings.twitch_users_url,
            headers=headers,
            params={"login": username},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            raise ValueError(f"No user found for username '{username}'")
        user_data = data[0]
        return {
            "id": user_data["id"],
            "display_name": user_data.get("display_name", username),
            "login": user_data.get("login", username)
        }
    except (requests.RequestException, ValueError) as e:
        logger.error("Error fetching user info for '%s': %s", username, e)
        raise

def get_clips(user_id: str, token: str, time_window="week", desired_count=None, min_views=100) -> list[dict]:
    """
    Fetch clips for a given broadcaster ID, then filter out any we've already returned before.
    Only returns clips with at least min_views (default 1000).
    Uses pagination to ensure we get enough new clips.
    New clips get added to the cache on each call.
    """
    if desired_count is None:
        desired_count = settings.clips_first
        
    seen = _load_seen_ids()
    new_clips = []
    cursor = None
    max_pages = 10  # Safety limit to prevent infinite loops
    pages_fetched = 0

    # Validate time_window parameter
    valid_periods = ["day", "week", "month", "all"]
    if time_window not in valid_periods:
        logger.warning("Invalid time_window '%s', defaulting to 'week'", time_window)
        time_window = "week"

    logger.info("Fetching clips for user ID %s with period '%s' (min views: %d)", user_id, time_window, min_views)

    while len(new_clips) < desired_count and pages_fetched < max_pages:
        try:
            headers = {
                "Client-ID": settings.twitch_client_id,
                "Authorization": f"Bearer {token}"
            }
            
            # Build base parameters - fetch more clips since we're filtering by views
            params = {
                "broadcaster_id": user_id,
                "first": min(100, desired_count * 3),  # Fetch even more to account for view filtering
            }
            
            if time_window != "all":
                params["started_at"] = get_time_window_start(time_window)
            
            # Add pagination cursor if we have one
            if cursor:
                params["after"] = cursor
                
            logger.debug("API request params: %s", params)
                
            resp = requests.get(
                settings.twitch_clips_url,
                headers=headers,
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            response_data = resp.json()
            all_clips = response_data.get("data", [])
            
            # Get pagination cursor for next page
            pagination = response_data.get("pagination", {})
            cursor = pagination.get("cursor")
            
            pages_fetched += 1
            
            # If no clips returned, we've reached the end
            if not all_clips:
                logger.info("No more clips available for user ID %s in period '%s'", user_id, time_window)
                break
                
        except requests.RequestException as e:
            logger.error("Error fetching clips for user ID %s (page %d): %s", user_id, pages_fetched, e)
            break

        # Process clips from this page
        page_new_clips = 0
        page_filtered_views = 0
        for clip in all_clips:
            cid = clip.get("id")
            if not cid or cid in seen:
                continue

            # Check view count - filter out clips with fewer than min_views
            view_count = clip.get("view_count", 0)
            if view_count < min_views:
                page_filtered_views += 1
                continue

            # ensure broadcaster_name is present
            if not clip.get("broadcaster_name"):
                clip["broadcaster_name"] = clip.get("broadcaster_login", "Unknown")

            # Log clip info for debugging
            created_at = clip.get("created_at", "Unknown")
            logger.debug("Found new clip: %s (views: %d, created: %s)", 
                        clip.get("title", "Untitled"), view_count, created_at)

            new_clips.append(clip)
            seen.add(cid)
            page_new_clips += 1
            
            # Stop if we have enough clips
            if len(new_clips) >= desired_count:
                break
        
        logger.info("Page %d: Found %d new clips, filtered %d low-view clips (total: %d/%d)", 
                   pages_fetched, page_new_clips, page_filtered_views, len(new_clips), desired_count)
        
        # If no cursor, we've reached the end of available clips
        if not cursor:
            logger.info("Reached end of available clips for user ID %s", user_id)
            break
            
        # If this page had no new clips, we might be hitting mostly seen clips
        if page_new_clips == 0:
            logger.info("No new clips on page %d, continuing to next page...", pages_fetched)

    # persist updated seen set
    _save_seen_ids(seen)
    
    logger.info("Returning %d new clips for user ID %s (period: %s, min views: %d)", 
               len(new_clips), user_id, time_window, min_views)
    return new_clips


def get_time_window_start(time_window: str) -> str:
    """Convert time window to ISO 8601 timestamp for Twitch API"""
    
    now = datetime.now(timezone.utc)
    
    if time_window == "day":
        start_time = now - timedelta(days=1)
    elif time_window == "week":
        start_time = now - timedelta(weeks=1)
    elif time_window == "month":
        start_time = now - timedelta(days=30)
    else:
        # Default to week if unknown
        start_time = now - timedelta(weeks=1)
    
    # Return in RFC 3339 format (ISO 8601)
    return start_time.isoformat().replace("+00:00", "Z")

def get_user_id(token: str, username: str) -> str:
    """Lookup Twitch user ID by username (backwards compatibility)."""
    return get_user_info(token, username)["id"]


def get_latest_vod_url(username: str) -> str:
    """Return the URL for the most recent VOD of a user."""
    token = get_twitch_token()
    user_id = get_user_id(token, username)
    try:
        headers = {
            "Client-ID": settings.twitch_client_id,
            "Authorization": f"Bearer {token}"
        }
        resp = requests.get(
            settings.twitch_videos_url,
            headers=headers,
            params={"user_id": user_id, "type": "archive"},
            timeout=10,
        )
        resp.raise_for_status()
        vids = resp.json().get("data", [])
        if not vids:
            raise ValueError(f"No VODs found for user '{username}'")
        return vids[0]["url"]
    except (requests.RequestException, ValueError) as e:
        logger.error("Error fetching latest VOD URL for '%s': %s", username, e)
        raise