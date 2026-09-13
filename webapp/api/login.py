from fastapi import APIRouter, Depends, HTTPException, status
from telegram_client.auth import auth_manager
from telegram_client.manager import client_manager
from utils.rate_limiter import auth_rate_limiter
from webapp.api.auth import get_current_user_id
from webapp.schemas import Login2FASubmit, LoginCodeRequest, LoginCodeSubmit
from utils.logger import logger

router = APIRouter(prefix="/login", tags=["Secure Login"])


@router.get("/status")
async def get_auth_status(user_id: int = Depends(get_current_user_id)):
    """Checks whether the user currently has an active, authenticated session or pending flow."""
    auth_state = await auth_manager.get_auth_state(user_id)
    return {
        "user_id": user_id,
        "is_authorized": auth_state.is_authorized,
        "status": auth_state.status.value,
        "step": auth_state.step,
        "phone": auth_state.phone,
        "expires_at": auth_state.expires_at,
    }


@router.post("/send-code")
@router.post("/request-code")
async def request_code(req: LoginCodeRequest, user_id: int = Depends(get_current_user_id)):
    """Step 1: Mini App requests SMS/Telegram code securely."""
    await auth_rate_limiter.check(str(user_id))
    try:
        auth_state = await auth_manager.request_phone_code(
            telegram_id=user_id,
            phone=req.phone,
            api_id=req.api_id,
            api_hash=req.api_hash,
        )
        return {
            "success": True,
            "status": auth_state.status.value,
            "step": auth_state.step,
            "expires_at": auth_state.expires_at,
            "message": "Код подтверждения отправлен в ваш Telegram.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in request-code: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/verify-code")
@router.post("/submit-code")
async def submit_code(req: LoginCodeSubmit, user_id: int = Depends(get_current_user_id)):
    """Step 2: Mini App submits authentication code."""
    await auth_rate_limiter.check(str(user_id))
    try:
        auth_state, session_file = await auth_manager.submit_auth_code(user_id, req.code)
        return {
            "success": True,
            "status": auth_state.status.value,
            "step": auth_state.step,
            "is_authorized": auth_state.is_authorized,
            "message": "Аккаунт успешно подключён!" if auth_state.is_authorized else "Требуется 2FA пароль.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in submit-code: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/verify-2fa")
@router.post("/submit-2fa")
async def submit_2fa(req: Login2FASubmit, user_id: int = Depends(get_current_user_id)):
    """Step 3: Mini App submits 2FA cloud password."""
    await auth_rate_limiter.check(str(user_id))
    try:
        auth_state, session_file = await auth_manager.submit_2fa_password(user_id, req.password)
        return {
            "success": True,
            "status": auth_state.status.value,
            "step": auth_state.step,
            "is_authorized": auth_state.is_authorized,
            "message": "Аккаунт успешно подключён!",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in submit-2fa: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/cancel")
async def cancel_login(user_id: int = Depends(get_current_user_id)):
    """Cancels any pending login attempt and frees resources."""
    await auth_manager.cancel_auth(user_id)
    return {"success": True, "message": "Авторизация отменена."}


@router.post("/logout")
async def logout(user_id: int = Depends(get_current_user_id)):
    """Securely erases user session from disk and database."""
    await client_manager.logout_user(user_id)
    return {"success": True, "message": "Сессия успешно завершена и удалена."}
