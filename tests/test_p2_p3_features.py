import pytest
from features.__init__ import auto_discover_features, feature_registry
from features.prank.effects import zalgo, reverse, leet, scramble, vaporwave
from features.prank.service import prank_service
from features.mini_games.service import game_service

def test_feature_registry():
    auto_discover_features()
    assert len(feature_registry) == 12
    for name in ['deleted_messages', 'edited_messages', 'one_time_messages',
                 'auto_responder', 'translator', 'rp',
                 'spam_protection', 'prank', 'repeater',
                 'mute', 'fonts', 'mini_games']:
        assert name in feature_registry
        assert not feature_registry[name].coming_soon

def test_prank_effects():
    assert reverse("hello") == "olleh"
    assert leet("leet") == "l337"
    assert vaporwave("a") != "a"
    assert "a" in zalgo("a")
    assert prank_service.apply_effect("test", "reverse") == "tset"
    
def test_mini_games_service():
    game_service.submit_score(1, "reaction", 500)
    scores = game_service.get_high_scores(1)
    assert scores["reaction"] == 500
    
    # Update with higher
    game_service.submit_score(1, "reaction", 700)
    assert game_service.get_high_scores(1)["reaction"] == 700
    
    # Lower should be ignored
    game_service.submit_score(1, "reaction", 600)
    assert game_service.get_high_scores(1)["reaction"] == 700
