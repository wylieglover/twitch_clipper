from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path

class Settings(BaseSettings):
    # Twitch API credentials
    
    twitch_client_id: str = Field(..., env="TWITCH_CLIENT_ID")
    twitch_client_secret: str = Field(..., env="TWITCH_CLIENT_SECRET")
    hf_token: str = Field(None, env="HF_TOKEN")
    gemini_api_key: str = Field(None, env="GEMINI_API_KEY")
    rapid_api_key: str = Field(None, env="RAPID_API_KEY")
    # Output directories
    vod_output_dir: Path = Field(default=Path("vod_clips"), env="OUTPUT_DIR")

    # Highlight clipping parameters
    highlight_max_clips: int = Field(default=5, env="HIGHLIGHT_MAX_CLIPS")
    highlight_segment_duration: int = Field(default=30, env="HIGHLIGHT_SEGMENT_DURATION")

    # Twitch clip fetch parameters
    clips_period: str = Field(default="week", env="TWITCH_CLIPS_PERIOD")
    clips_first: int = Field(default=10, env="TWITCH_CLIPS_FIRST")

    # Twitch API endpoints (override if needed)
    twitch_token_url: str = Field(default="https://id.twitch.tv/oauth2/token")
    twitch_users_url: str = Field(default="https://api.twitch.tv/helix/users")
    twitch_clips_url: str = Field(default="https://api.twitch.tv/helix/clips")
    twitch_videos_url: str = Field(default="https://api.twitch.tv/helix/videos")

    tiktok_client_key: str = Field(..., env="TIKTOK_CLIENT_KEY")
    tiktok_client_secret: str = Field(..., env="TIKTOK_CLIENT_SECRET")
    tiktok_redirect_uri: str = Field(
        default="https://twitchtok.web.app/auth/tiktok/callback",
        env="TIKTOK_REDIRECT_URI"
    )
    
    processed_clips_file: Path = Field(
        default=Path("processed_clips.json")
    )

    class Config:
        # load environment variables from .env
        env_file = ".env"
        case_sensitive = False

# Instantiate a single Settings object for application-wide use
settings = Settings()