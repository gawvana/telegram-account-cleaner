from typing import List, Dict

class GameService:
    def __init__(self):
        # In-memory score DB: dict[user_id, dict[game_id, score]]
        self.scores: Dict[int, Dict[str, int]] = {}
        
    def get_available_games(self) -> List[Dict]:
        return [
            {"id": "reaction", "name": "Reaction Time"},
            {"id": "memory", "name": "Memory Match"},
            {"id": "typing", "name": "Typing Speed"},
            {"id": "guess", "name": "Guess Number"},
            {"id": "tictactoe", "name": "Tic Tac Toe"},
            {"id": "2048", "name": "2048"}
        ]
        
    def submit_score(self, user_id: int, game_id: str, score: int):
        if user_id not in self.scores:
            self.scores[user_id] = {}
        current = self.scores[user_id].get(game_id, 0)
        if score > current:
            self.scores[user_id][game_id] = score
            
    def get_high_scores(self, user_id: int) -> Dict[str, int]:
        return self.scores.get(user_id, {})

game_service = GameService()
