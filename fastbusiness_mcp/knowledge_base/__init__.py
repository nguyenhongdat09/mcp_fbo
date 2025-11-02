"""FastBusiness Knowledge Base System

This package provides AI-powered code assistance for FastBusiness XML development.
It includes:
- API reference (Form, Grid) loaded from YAML
- Context detection (Dir, Grid Detail, Grid View)
- Code generation from patterns and templates
"""

from .engine import KnowledgeEngine
from .context_detector import ContextDetector
from .code_generator import CodeGenerator

__all__ = [
    'KnowledgeEngine',
    'ContextDetector',
    'CodeGenerator',
]
