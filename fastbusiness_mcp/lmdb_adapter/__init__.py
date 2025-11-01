"""LMDB Adapter for FastBusiness Field Definitions

This package provides LMDB-based field storage with smart pattern matching
and template-based field generation.
"""

from .lmdb_manager import LMDBManager
from .pattern_matcher import FieldPatternMatcher
from .xml_parser import FastBusinessXMLParser

__all__ = ['LMDBManager', 'FieldPatternMatcher', 'FastBusinessXMLParser']
