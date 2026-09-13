def calculate_score(moves: int) -> int:
    return max(0, 500 - (moves * 10))
