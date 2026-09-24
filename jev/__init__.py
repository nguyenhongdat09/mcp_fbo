"""Jev (TypeSafe System One) client — package độc lập, tái dùng.

Usage:
    from jev import load_jev_config, ask_jev
    cfg = load_jev_config()          # None -> feature locked
    res = ask_jev(cfg, state, questions)  # {"ok":..., "answers": {...}}
"""
from .config import load_jev_config, jev_available
from .client import post_systemone
from .models import JevAnswer


def ask_jev(cfg: dict, state, questions: dict) -> dict:
    """Alias ngắn gọn cho post_systemone."""
    return post_systemone(cfg, state, questions)


__all__ = ["load_jev_config", "jev_available", "ask_jev",
           "post_systemone", "JevAnswer"]
