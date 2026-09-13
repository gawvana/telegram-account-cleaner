"""Feature system API endpoints."""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from webapp.api.auth import get_current_user_id
from database import db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/features", tags=["features"])


class FeatureSettingsUpdate(BaseModel):
    settings: dict


@router.get("")
async def list_features(user_id: int = Depends(get_current_user_id)):
    """Get all features with user-specific states."""
    from features.registry import feature_registry
    
    definitions = feature_registry.get_all()
    states = await feature_registry.get_user_states(user_id)
    favorites = await db.get_favorites(user_id)
    
    features = []
    for fdef in definitions:
        state = states.get(fdef.id)
        features.append({
            'id': fdef.id,
            'name': fdef.name,
            'description': fdef.description,
            'icon': fdef.icon,
            'category': fdef.category.value,
            'requires_telegram': fdef.requires_telegram,
            'requires_admin': fdef.requires_admin,
            'has_settings': fdef.has_settings,
            'coming_soon': fdef.coming_soon,
            'enabled': state.enabled if state else False,
            'enabled_at': state.enabled_at if state else None,
            'is_favorite': fdef.id in favorites,
            'actions_count': state.activity.actions_count if state and state.activity else 0,
            'errors_count': state.activity.errors_count if state and state.activity else 0,
        })
    
    return {'features': features, 'favorites': favorites}


@router.get("/search")
async def search_features(q: str, user_id: int = Depends(get_current_user_id)):
    from features.registry import feature_registry
    results = feature_registry.search(q)
    return {'results': [{'id': f.id, 'name': f.name, 'description': f.description, 'category': f.category.value, 'icon': f.icon} for f in results]}


@router.get("/favorites")
async def get_favorites(user_id: int = Depends(get_current_user_id)):
    favorites = await db.get_favorites(user_id)
    return {'favorites': favorites}


@router.post("/favorites/{feature_id}")
async def toggle_favorite(feature_id: str, user_id: int = Depends(get_current_user_id)):
    from features.registry import feature_registry
    if not feature_registry.get_definition(feature_id):
        raise HTTPException(status_code=404, detail="Feature not found")
    is_fav = await db.toggle_favorite(user_id, feature_id)
    return {'success': True, 'is_favorite': is_fav}


@router.get("/analytics")
async def get_analytics(user_id: int = Depends(get_current_user_id)):
    from features.registry import feature_registry
    states = await feature_registry.get_user_states(user_id)
    
    active_count = sum(1 for s in states.values() if s.enabled)
    total_actions = sum(s.activity.actions_count for s in states.values() if s.activity)
    total_errors = sum(s.activity.errors_count for s in states.values() if s.activity)
    storage = await db.get_storage_usage(user_id)
    
    return {
        'features_active': active_count,
        'total_actions': total_actions,
        'total_errors': total_errors,
        'deleted_archive_count': storage.get('deleted_messages_count', 0),
        'deleted_archive_bytes': storage.get('deleted_messages_bytes', 0),
        'edited_count': storage.get('edited_messages_count', 0),
        'storage_used_bytes': storage.get('deleted_messages_bytes', 0),
        'storage_quota_bytes': storage.get('storage_quota_bytes', 104857600),
    }


@router.get("/{feature_id}")
async def get_feature_detail(feature_id: str, user_id: int = Depends(get_current_user_id)):
    from features.registry import feature_registry
    fdef = feature_registry.get_definition(feature_id)
    if not fdef:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    state = await db.get_feature_state(user_id, feature_id)
    module = feature_registry.get_module(feature_id)
    activity_log = await db.get_feature_activity_log(user_id, feature_id, limit=20)
    
    result = {
        'id': fdef.id,
        'name': fdef.name,
        'description': fdef.description,
        'icon': fdef.icon,
        'category': fdef.category.value,
        'requires_telegram': fdef.requires_telegram,
        'requires_admin': fdef.requires_admin,
        'has_settings': fdef.has_settings,
        'coming_soon': fdef.coming_soon,
        'enabled': bool(state and state.get('enabled', 0)),
        'settings': json.loads(state['settings_json']) if state and state.get('settings_json') else (module.get_default_settings() if module else {}),
        'actions_count': state.get('actions_count', 0) if state else 0,
        'errors_count': state.get('errors_count', 0) if state else 0,
        'enabled_at': state.get('enabled_at') if state else None,
        'last_activity': state.get('last_activity') if state else None,
        'activity_log': activity_log,
    }
    
    # Get settings schema if module supports it
    if module:
        try:
            result['settings_schema'] = await module.get_settings_schema()
        except Exception:
            result['settings_schema'] = {}
    
    return result


@router.post("/{feature_id}/enable")
async def enable_feature(feature_id: str, user_id: int = Depends(get_current_user_id)):
    from features.registry import feature_registry
    fdef = feature_registry.get_definition(feature_id)
    if not fdef:
        raise HTTPException(status_code=404, detail="Feature not found")
    if fdef.coming_soon:
        raise HTTPException(status_code=400, detail="Feature is not yet available")
    
    success = await feature_registry.enable_feature(user_id, feature_id)
    if success:
        await db.log_feature_activity(user_id, feature_id, 'enabled')
        await db.append_audit_log(user_id, f'FEATURE_ENABLED:{feature_id}')
    return {'success': success, 'enabled': True}


@router.post("/{feature_id}/disable")
async def disable_feature(feature_id: str, user_id: int = Depends(get_current_user_id)):
    from features.registry import feature_registry
    fdef = feature_registry.get_definition(feature_id)
    if not fdef:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    success = await feature_registry.disable_feature(user_id, feature_id)
    if success:
        await db.log_feature_activity(user_id, feature_id, 'disabled')
        await db.append_audit_log(user_id, f'FEATURE_DISABLED:{feature_id}')
    return {'success': success, 'enabled': False}


@router.get("/{feature_id}/settings")
async def get_feature_settings(feature_id: str, user_id: int = Depends(get_current_user_id)):
    from features.registry import feature_registry
    fdef = feature_registry.get_definition(feature_id)
    if not fdef:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    state = await db.get_feature_state(user_id, feature_id)
    module = feature_registry.get_module(feature_id)
    defaults = module.get_default_settings() if module else {}
    
    if state and state.get('settings_json'):
        settings = json.loads(state['settings_json'])
    else:
        settings = defaults
    
    return {'feature_id': feature_id, 'settings': settings, 'defaults': defaults}


@router.post("/{feature_id}/settings")
async def update_feature_settings(feature_id: str, body: FeatureSettingsUpdate,
                                   user_id: int = Depends(get_current_user_id)):
    from features.registry import feature_registry
    fdef = feature_registry.get_definition(feature_id)
    if not fdef:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    await db.update_feature_settings(user_id, feature_id, json.dumps(body.settings))
    await db.log_feature_activity(user_id, feature_id, 'settings_updated')
    return {'success': True, 'settings': body.settings}


@router.get("/{feature_id}/activity")
async def get_feature_activity(feature_id: str, user_id: int = Depends(get_current_user_id)):
    from features.registry import feature_registry
    if not feature_registry.get_definition(feature_id):
        raise HTTPException(status_code=404, detail="Feature not found")
    
    log = await db.get_feature_activity_log(user_id, feature_id)
    module = feature_registry.get_module(feature_id)
    activity = await module.get_activity(user_id) if module else None
    
    return {
        'feature_id': feature_id,
        'actions_count': activity.actions_count if activity else 0,
        'errors_count': activity.errors_count if activity else 0,
        'last_activity': activity.last_activity.isoformat() if activity and activity.last_activity else None,
        'enabled_since': activity.enabled_since.isoformat() if activity and activity.enabled_since else None,
        'log': log
    }


@router.post("/stop-all")
async def stop_all_automations(user_id: int = Depends(get_current_user_id)):
    from features.registry import feature_registry
    stopped = await feature_registry.stop_all_automations(user_id)
    if stopped:
        await db.append_audit_log(user_id, 'EMERGENCY_STOP_ALL')
        for fid in stopped:
            await db.log_feature_activity(user_id, fid, 'emergency_stopped')
    return {'success': True, 'stopped_features': stopped}
