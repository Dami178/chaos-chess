"""
Chaos Chess Engine — manages game state, validates moves,
applies dynamic rules, and enforces rule-change limits.
"""

from __future__ import annotations

import chess
from typing import Any


DEFAULT_RULES: dict[str, Any] = {
    "allow_castling": True,
    "allow_en_passant": True,
    "allow_promotion": True,
    "promotion_piece": "queen",   # queen | rook | bishop | knight
    "pawn_double_move": True,
    "capture_only": False,        # if True, only capturing moves are legal
    "inverse_colors": False,      # if True, White plays Black's pieces and vice-versa
    "extra_description": "",      # Free-form rule description shown in UI
}


class ChaosChessEngine:
    """Central game object that couples a chess.Board with mutable rules."""

    def __init__(self) -> None:
        self.board: chess.Board = chess.Board()
        self.rules: dict[str, Any] = dict(DEFAULT_RULES)
        self.max_rule_changes: int = 3
        self.current_rule_changes: int = 0
        self.move_history: list[str] = []   # SAN notation
        self.game_over: bool = False
        self.result: str | None = None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def start_game(self, max_rule_changes: int = 3) -> None:
        """Reset everything and start a fresh game."""
        self.board = chess.Board()
        self.rules = dict(DEFAULT_RULES)
        self.max_rule_changes = max(1, int(max_rule_changes))
        self.current_rule_changes = 0
        self.move_history = []
        self.game_over = False
        self.result = None

    # ------------------------------------------------------------------
    # Move logic
    # ------------------------------------------------------------------

    def legal_moves_uci(self) -> list[str]:
        """Return a list of legal UCI move strings under the current rules."""
        legal = list(self.board.legal_moves)

        if self.rules.get("capture_only"):
            legal = [m for m in legal if self.board.is_capture(m)]

        if not self.rules.get("allow_castling", True):
            legal = [m for m in legal if not self.board.is_castling(m)]

        if not self.rules.get("allow_en_passant", True):
            legal = [m for m in legal if not self.board.is_en_passant(m)]

        return [m.uci() for m in legal]

    def validate_move(self, uci: str) -> tuple[bool, str]:
        """
        Check whether *uci* is valid under current rules.
        Returns (ok, error_message).
        """
        if self.game_over:
            return False, "Game is already over."

        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return False, f"Malformed UCI string: {uci!r}"

        legal = self.legal_moves_uci()
        if uci not in legal:
            return False, f"Move {uci} is not legal under current rules."

        return True, ""

    def apply_move(self, uci: str) -> dict[str, Any]:
        """
        Apply *uci* to the board.  Assumes validate_move already passed.
        Returns a status dict.
        """
        move = chess.Move.from_uci(uci)

        # Override promotion piece if rule differs from default queen
        if move.promotion is None and self.board.piece_type_at(move.from_square) == chess.PAWN:
            promo_rank = 7 if self.board.turn == chess.WHITE else 0
            if chess.square_rank(move.to_square) == promo_rank and self.rules.get("allow_promotion", True):
                piece_map = {
                    "queen": chess.QUEEN,
                    "rook": chess.ROOK,
                    "bishop": chess.BISHOP,
                    "knight": chess.KNIGHT,
                }
                promo_name = self.rules.get("promotion_piece", "queen")
                move = chess.Move(move.from_square, move.to_square, promotion=piece_map.get(promo_name, chess.QUEEN))

        san = self.board.san(move)
        self.board.push(move)
        self.move_history.append(san)

        return self._build_status()

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def can_change_rules(self) -> bool:
        return self.current_rule_changes < self.max_rule_changes

    def rules_remaining(self) -> int:
        return self.max_rule_changes - self.current_rule_changes

    def update_rules(self, new_rules: dict[str, Any]) -> tuple[bool, str]:
        """
        Merge *new_rules* into current rules and increment the change counter.
        Returns (success, message).
        """
        if not self.can_change_rules():
            return False, "Rule-change limit reached."

        # Sanitise and apply
        allowed_keys = set(DEFAULT_RULES.keys())
        filtered = {k: v for k, v in new_rules.items() if k in allowed_keys}
        self.rules.update(filtered)
        self.current_rule_changes += 1

        remaining = self.rules_remaining()
        return True, f"Rules updated. {remaining} change(s) remaining."

    # ------------------------------------------------------------------
    # Game-over detection
    # ------------------------------------------------------------------

    def _check_game_over(self) -> None:
        if self.board.is_checkmate():
            winner = "Black" if self.board.turn == chess.WHITE else "White"
            self.game_over = True
            self.result = f"Checkmate! {winner} wins."
        elif self.board.is_stalemate():
            self.game_over = True
            self.result = "Stalemate! Draw."
        elif self.board.is_insufficient_material():
            self.game_over = True
            self.result = "Insufficient material! Draw."
        elif self.board.is_seventyfive_moves():
            self.game_over = True
            self.result = "75-move rule! Draw."
        elif self.board.is_fivefold_repetition():
            self.game_over = True
            self.result = "Fivefold repetition! Draw."

    # ------------------------------------------------------------------
    # State snapshot
    # ------------------------------------------------------------------

    def _build_status(self) -> dict[str, Any]:
        self._check_game_over()
        return {
            "fen": self.board.fen(),
            "turn": "white" if self.board.turn == chess.WHITE else "black",
            "legal_moves": self.legal_moves_uci(),
            "rules": self.rules,
            "rule_changes_used": self.current_rule_changes,
            "rule_changes_remaining": self.rules_remaining(),
            "move_history": self.move_history,
            "game_over": self.game_over,
            "result": self.result,
            "is_check": self.board.is_check(),
        }

    def get_status(self) -> dict[str, Any]:
        return self._build_status()
