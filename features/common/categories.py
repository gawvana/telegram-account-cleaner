from enum import Enum

class FeatureCategory(str, Enum):
    MESSAGES = "MESSAGES"
    AUTOMATION = "AUTOMATION"
    COMMUNICATION = "COMMUNICATION"
    MODERATION = "MODERATION"
    FUN = "FUN"
    TEXT = "TEXT"
    GAMES = "GAMES"
