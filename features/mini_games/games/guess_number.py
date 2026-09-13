def calculate_score(attempts: int) -> int:
    return max(0, 100 - (attempts * 5))
