import importlib
from .base import BaseFeatureModule

# Global registry of discovered features
feature_registry = {}

def auto_discover_features():
    from features.deleted_messages import deleted_messages_module
    from features.edited_messages import edited_messages_module
    from features.one_time_messages import one_time_messages_module
    from features.auto_responder import auto_responder_module
    from features.translator import translator_module
    from features.rp import rp_module
    from features.spam_protection import spam_protection_module
    from features.prank import prank_module
    from features.repeater import repeater_module
    from features.mute import mute_module
    from features.fonts import fonts_module
    from features.mini_games import mini_games_module
    
    # 12 modules
    modules = [
        deleted_messages_module, edited_messages_module, one_time_messages_module,
        auto_responder_module, translator_module, rp_module,
        spam_protection_module, prank_module, repeater_module,
        mute_module, fonts_module, mini_games_module
    ]
    
    for mod in modules:
        mod.coming_soon = False
        feature_registry[mod.feature_id] = mod
        
def get_feature(feature_id: str) -> BaseFeatureModule:
    return feature_registry.get(feature_id)
