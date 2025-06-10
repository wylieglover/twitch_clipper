# app/tiktok_uploader.py

import requests
import json
import os
import time
from urllib.parse import urlencode
from config import settings


class TikTokUploader:
    def __init__(self, redirect_uri: str = None):
        """
        Automatically reads the TikTok client key/secret (and optional override URI)
        from `settings`. If you pass a custom redirect_uri, it uses that; otherwise,
        it defaults to settings.tiktok_redirect_uri (loaded from the environment).
        """
        # Pull credentials from pydantic Settings:
        self.client_key: str = settings.tiktok_client_key
        self.client_secret: str = settings.tiktok_client_secret

        # Redirect URI from settings unless explicitly overridden
        self.redirect_uri: str = redirect_uri or settings.tiktok_redirect_uri

        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.base_url: str = "https://open.tiktokapis.com"

    def get_authorization_url(self) -> str:
        """
        Builds the TikTok OAuth URL that the front-end should navigate to.
        After user approves, TikTok will redirect to:
            <redirect_uri>?code=...&state=...
        """
        params = {
            "client_key": self.client_key,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "video.upload,video.publish",
            "state": "random_state_string",  # You should generate a real random state
        }
        return f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}"

    def exchange_code_for_token(self, authorization_code: str) -> dict:
        """
        Exchanges the `code` from TikTok (sent to redirect_uri) for an access_token + refresh_token.
        Raises an exception on non-200 responses.
        """
        url = f"{self.base_url}/v2/oauth/token/"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": authorization_code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }

        print(f"[DEBUG] Token exchange URL: {url}")
        print(f"[DEBUG] Token exchange data: {data}")
        print(f"[DEBUG] Headers: {headers}")

        response = requests.post(url, headers=headers, data=data)
        print(f"[DEBUG] Response status: {response.status_code}")
        print(f"[DEBUG] Response headers: {dict(response.headers)}")
        print(f"[DEBUG] Response text: {response.text}")

        if response.status_code == 200:
            try:
                response_json = response.json()
                print(f"[DEBUG] Parsed JSON response: {response_json}")
                
                # Handle both response formats - some TikTok APIs return data wrapped, others don't
                if "data" in response_json:
                    # Wrapped format: {"data": {"access_token": "...", ...}}
                    token_data = response_json["data"]
                    print("[DEBUG] Using wrapped response format")
                else:
                    # Direct format: {"access_token": "...", "refresh_token": "...", ...}
                    token_data = response_json
                    print("[DEBUG] Using direct response format")
                
                # Check for required fields
                if "access_token" not in token_data:
                    print(f"[ERROR] Response missing 'access_token'. Token data: {token_data}")
                    raise Exception(f"Invalid token data: missing 'access_token'. Data: {token_data}")
                
                self.access_token = token_data.get("access_token")
                self.refresh_token = token_data.get("refresh_token")
                
                print(f"[DEBUG] Access token set: {self.access_token[:10] if self.access_token else 'None'}...")
                print(f"[DEBUG] Refresh token set: {self.refresh_token[:10] if self.refresh_token else 'None'}...")
                
                # Return the original response for consistency
                return response_json
                
            except ValueError as json_error:
                print(f"[ERROR] Failed to parse JSON response: {json_error}")
                raise Exception(f"Invalid JSON response from TikTok: {response.text}")
        else:
            error_msg = f"TikTok token exchange failed with status {response.status_code}: {response.text}"
            print(f"[ERROR] {error_msg}")
            raise Exception(error_msg)

   
    def refresh_access_token(self) -> dict:
        """
        Uses the stored `self.refresh_token` to obtain a new access_token.
        Raises if `self.refresh_token` is None or if the HTTP call fails.
        """
        if not self.refresh_token:
            raise Exception("No refresh_token available. Cannot refresh.")

        url = f"{self.base_url}/v2/oauth/token/"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }

        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            response_json = response.json()
            
            # Handle both response formats - same fix as token exchange
            if "data" in response_json:
                # Wrapped format: {"data": {"access_token": "...", ...}}
                token_data = response_json["data"]
            else:
                # Direct format: {"access_token": "...", "refresh_token": "...", ...}
                token_data = response_json
            
            self.access_token = token_data.get("access_token")
            # Update refresh token if provided in response
            if "refresh_token" in token_data:
                self.refresh_token = token_data.get("refresh_token")
                
            return response_json
        else:
            raise Exception(f"TikTok token refresh failed: {response.text}")

    def save_tokens(self, filename: str = "tiktok_tokens.json") -> None:
        """
        Persists the current access_token + refresh_token to a JSON file.
        """
        tokens = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
        }
        with open(filename, "w") as f:
            json.dump(tokens, f)

    def load_tokens(self, filename: str = "tiktok_tokens.json") -> bool:
        """
        Loads access_token + refresh_token from a JSON file.
        Returns True if loaded successfully; False if file does not exist.
        """
        try:
            with open(filename, "r") as f:
                tokens = json.load(f)
                self.access_token = tokens.get("access_token")
                self.refresh_token = tokens.get("refresh_token")
                return True
        except FileNotFoundError:
            return False

    def upload_video_direct(self, video_path: str, description: str = "", hashtags: list[str] | None = None, 
                            privacy_level: str = "SELF_ONLY") -> dict:
        """
        Alternative method for direct posting (if supported by your TikTok app permissions).
        This uses the direct post endpoint which may require special approval from TikTok.
        
        NOTE: Most TikTok apps only have inbox upload permissions, not direct posting.
        """
        if not self.access_token:
            raise Exception("No access_token available. Please authenticate first.")
        
        print(f"[DEBUG] Attempting DIRECT POST upload for: {video_path}")
        
        # This endpoint may not be available for all apps
        init_url = f"{self.base_url}/v2/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        
        # Build caption + hashtags
        caption = description.strip()
        if hashtags:
            tag_string = " ".join(f"#{tag.lstrip('#')}" for tag in hashtags)
            caption = f"{caption} {tag_string}".strip()
        
        print(f"[DEBUG] Final caption: {caption}")
        
        post_info = {
            "title": caption,
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "video_cover_timestamp_ms": 1000,
        }
        
        file_size = os.path.getsize(video_path)
        print(f"[DEBUG] Video file size: {file_size} bytes")
        
        init_data = {
            "post_info": post_info,
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": min(file_size, 10_000_000),
                "total_chunk_count": 1,
            },
        }
        
        print(f"[DEBUG] Sending direct post init request to: {init_url}")
        print(f"[DEBUG] Init data: {init_data}")
        
        response = requests.post(init_url, headers=headers, json=init_data)
        print(f"[DEBUG] Init response status: {response.status_code}")
        print(f"[DEBUG] Init response: {response.text}")
        
        if response.status_code == 403:
            raise Exception("Direct posting not permitted. Your app may only have inbox upload permissions.")
        elif response.status_code == 401:
            raise Exception("TikTok API returned 401 Unauthorized. Token may be expired or invalid.")
        elif response.status_code != 200:
            raise Exception(f"TikTok direct post initialization failed: {response.text}")
        
        # Continue with upload and status checking if initialization succeeds...
        # (Implementation continues similar to original but with fixed endpoints)
        
        return {
            "success": False,
            "message": "Direct posting implementation incomplete - use inbox upload instead"
        }


    def _finalize_upload(self, publish_id: str, post_mode: str, max_retries: int = 30) -> dict:
        """
        Polls the TikTok status endpoint up to max_retries times (with 2s sleeps)
        until the status is either:
          - "PUBLISHED"   → video is live
          - "SEND_TO_USER_INBOX" → draft (if post_mode=MEDIA_UPLOAD)
          - "FAILED"      → error

        Returns a dict indicating success/failure and messages.
        """
        status_url = f"{self.base_url}/v2/post/publish/status/"  # FIXED endpoint
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        for attempt in range(max_retries):
            resp = requests.post(status_url, headers=headers, json={"publish_id": publish_id})
            if resp.status_code != 200:
                raise Exception(f"TikTok status check failed: {resp.text}")

            status_data = resp.json()["data"]
            status = status_data.get("status")

            if status == "PROCESSING_UPLOAD":
                time.sleep(2)
                continue
            elif status == "PROCESSING_DOWNLOAD":
                time.sleep(2)
                continue
            elif status == "SEND_TO_USER_INBOX":
                # MEDIA_UPLOAD draft mode
                return {
                    "success": True,
                    "message": "Video uploaded as draft to TikTok inbox",
                    "publish_id": publish_id,
                }
            elif status == "PUBLISHED":
                return {
                    "success": True,
                    "message": "Video published successfully",
                    "publish_id": publish_id,
                }
            elif status == "FAILED":
                return {
                    "success": False,
                    "message": "Upload failed",
                    "error": status_data.get("fail_reason", "Unknown"),
                }

            time.sleep(2)

        # If no terminal status by max_retries
        return {
            "success": False,
            "message": "Upload timed out—check TikTok for details",
            "publish_id": publish_id,
        }
