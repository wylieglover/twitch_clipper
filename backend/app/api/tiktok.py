import os
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi import status

from app.session_manager import SessionManager
from app.pipeline import OUTPUT_DIR
from app.processing.clips.uploader import TikTokUploader
from config import settings

router = APIRouter(prefix="/api/tiktok")

tiktok_uploader = TikTokUploader(redirect_uri=settings.tiktok_redirect_uri)

@router.get("/auth_url")
async def get_tiktok_auth_url():
    """
    Returns the TikTok OAuth URL that the front‐end should redirect the user to.
    After the user logs in/approves in TikTok, TikTok will redirect back to:
      https://twitchtok.web.app/auth/tiktok/callback?code=...&state=...
    """
    try:
         return {"auth_url": tiktok_uploader.get_authorization_url()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not generate auth URL: {e}")
    
@router.get("/callback")
async def tiktok_callback(code: str = None, state: str = None):
    """
    Enhanced TikTok callback with proper token saving
    """
    if code is None:
        raise HTTPException(status_code=400, detail="Missing code in callback")

    print(f"[DEBUG] Received callback with code: {code[:20]}...")
    print(f"[DEBUG] State: {state}")

    try:
        # Exchange code for tokens
        token_data = tiktok_uploader.exchange_code_for_token(code)
        print(f"[DEBUG] Token exchange successful: {token_data}")
        
        # Verify tokens are set in the uploader instance
        if not tiktok_uploader.access_token:
            raise Exception("Access token not set after exchange")
            
        print(f"[DEBUG] Access token in uploader: {tiktok_uploader.access_token[:20]}...")
        print(f"[DEBUG] Refresh token in uploader: {tiktok_uploader.refresh_token[:20] if tiktok_uploader.refresh_token else 'None'}...")
        
        # Save tokens to file - specify full path for clarity
        token_file_path = "tiktok_tokens.json"
        tiktok_uploader.save_tokens(token_file_path)
        print(f"[DEBUG] Tokens saved to: {os.path.abspath(token_file_path)}")
        
        # Verify file was created
        if os.path.exists(token_file_path):
            with open(token_file_path, 'r') as f:
                saved_tokens = json.load(f)
            print(f"[DEBUG] Verified saved tokens: access_token={saved_tokens.get('access_token', 'MISSING')[:20]}...")
        else:
            print("[ERROR] Token file was not created!")
            raise Exception("Failed to save token file")
        
        return {
            "status": "success", 
            "message": "TikTok authentication successful - tokens saved",
            "token_file": os.path.abspath(token_file_path),
            "has_access_token": bool(tiktok_uploader.access_token),
            "has_refresh_token": bool(tiktok_uploader.refresh_token)
        }
    except Exception as e:
        print(f"[ERROR] Token exchange/save failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Token exchange failed: {e}")

@router.get("/token_status")
async def check_tiktok_token_status():
    """
    Check if TikTok tokens are available and valid
    """
    token_file = "tiktok_tokens.json"
    
    if not os.path.exists(token_file):
        return {
            "status": "no_tokens",
            "message": "No token file found. Please authenticate first.",
            "file_path": os.path.abspath(token_file)
        }
    
    try:
        # Load tokens into a temporary uploader instance to test
        temp_uploader = TikTokUploader(redirect_uri=settings.tiktok_redirect_uri)
        tokens_loaded = temp_uploader.load_tokens(token_file)
        
        if not tokens_loaded:
            return {
                "status": "load_failed",
                "message": "Failed to load tokens from file"
            }
        
        return {
            "status": "tokens_available",
            "message": "Tokens loaded successfully",
            "has_access_token": bool(temp_uploader.access_token),
            "has_refresh_token": bool(temp_uploader.refresh_token),
            "access_token_preview": temp_uploader.access_token[:20] + "..." if temp_uploader.access_token else None,
            "file_path": os.path.abspath(token_file)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error checking tokens: {e}",
            "file_path": os.path.abspath(token_file)
        }
    
@router.post("/upload")
async def tiktok_upload(
    session_id: str = Form(...),
    video_filename: str = Form(...),
    description: str = Form(""),
    hashtags: str = Form(None),
    privacy_level: str = Form("SELF_ONLY"),
    post_mode: str = Form("DIRECT_POST")
):
    """
    Upload a single processed video to TikTok with enhanced debugging.
    """
    try:
        # 1) Session validation
        if not SessionManager.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        
        print(f"[DEBUG] Session {session_id} found")

        # 2) File validation
        local_path = Path(OUTPUT_DIR) / session_id / video_filename
        if not local_path.exists():
            print(f"[DEBUG] File not found at: {local_path}")
            raise HTTPException(status_code=404, detail=f"Video file {video_filename} not found")
        
        print(f"[DEBUG] File found at: {local_path}")

        # 3) Token loading with detailed debugging
        tokens_loaded = tiktok_uploader.load_tokens("tiktok_tokens.json")
        print(f"[DEBUG] Tokens loaded: {tokens_loaded}")
        
        if not tokens_loaded:
            print("[DEBUG] No tokens file found")
            raise HTTPException(
                status_code=401, 
                detail="Not authenticated with TikTok. Please complete OAuth flow first."
            )
        
        # Check if tokens exist but are None/empty
        if not tiktok_uploader.access_token:
            print("[DEBUG] Access token is None or empty")
            raise HTTPException(
                status_code=401,
                detail="Access token is invalid. Please re-authenticate with TikTok."
            )
        
        print(f"[DEBUG] Access token exists: {tiktok_uploader.access_token[:10]}...")
        
        # 4) Try to refresh token if we have a refresh token
        if tiktok_uploader.refresh_token:
            print("[DEBUG] Attempting to refresh access token")
            try:
                refresh_result = tiktok_uploader.refresh_access_token()
                print(f"[DEBUG] Token refresh successful: {refresh_result.get('data', {}).get('access_token', 'No token')[:10]}...")
                # Save refreshed tokens
                tiktok_uploader.save_tokens("tiktok_tokens.json")
            except Exception as refresh_err:
                print(f"[DEBUG] Token refresh failed: {refresh_err}")
                raise HTTPException(
                    status_code=401,
                    detail=f"Token refresh failed: {refresh_err}. Please re-authenticate."
                )

        # 5) Prepare hashtags
        hashtag_list = []
        if hashtags:
            hashtag_list = [tag.strip().lstrip("#") for tag in hashtags.split(",") if tag.strip()]
        
        print(f"[DEBUG] Hashtags prepared: {hashtag_list}")

        # 6) Attempt upload with detailed error handling
        print(f"[DEBUG] Starting upload for video: {video_filename}")
        upload_resp = tiktok_uploader.upload_video_direct(
            video_path=str(local_path),
            description=description,
            hashtags=hashtag_list,
            privacy_level=privacy_level
        )
        
        print(f"[DEBUG] Upload successful: {upload_resp}")
        return {"status": "uploaded", "upload_response": upload_resp}
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"[ERROR] TikTok upload failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"TikTok upload failed: {str(e)}")
    