"""Code Assistant Tool - MCP integration for Knowledge Base System"""

import logging
from typing import Dict, List, Optional
from pathlib import Path

from ..knowledge_base.engine import KnowledgeEngine
from ..knowledge_base.context_detector import ContextDetector
from ..knowledge_base.code_generator import CodeGenerator

logger = logging.getLogger(__name__)


class CodeAssistantTool:
    """MCP Tool wrapper for Knowledge Base System

    Provides AI-powered code assistance for FastBusiness XML development:
    - Context detection from XML files
    - API reference and help
    - Code generation from patterns
    - Pattern search
    """

    def __init__(self, knowledge_base_dir: str = "knowledge_base"):
        """Initialize Code Assistant

        Args:
            knowledge_base_dir: Path to knowledge base directory
        """
        self.knowledge_engine = KnowledgeEngine(knowledge_base_dir)
        self.context_detector = ContextDetector()
        self.code_generator = CodeGenerator(self.knowledge_engine)

    def detect_context(self, file_path: str = None, xml_content: str = None) -> Dict:
        """Detect context from XML file or content

        Args:
            file_path: Path to XML file (recommended)
            xml_content: XML content string (fallback)

        Returns:
            Dict with context information and recommendations
        """
        try:
            if file_path:
                context = self.context_detector.detect_from_file(file_path)
            elif xml_content:
                context = self.context_detector.detect_from_content(xml_content)
            else:
                return {
                    'success': False,
                    'error': 'Either file_path or xml_content required'
                }

            # Add formatted summary
            context['summary'] = self.context_detector.get_context_summary(context)

            return context

        except Exception as e:
            logger.error(f"Error detecting context: {e}")
            return {
                'success': False,
                'error': f'Error detecting context: {str(e)}'
            }

    def get_api_help(
        self,
        api_type: str,
        operation: str = None,
        category: str = None
    ) -> Dict:
        """Get API reference help

        Args:
            api_type: 'form' or 'grid'
            operation: Specific operation name (optional)
            category: API category (optional)

        Returns:
            Dict with API help information
        """
        try:
            if api_type == 'form':
                if operation and category:
                    api_op = self.knowledge_engine.get_form_api_operation(category, operation)
                    if api_op:
                        return {
                            'success': True,
                            'api_type': 'form',
                            'category': category,
                            'operation': operation,
                            'details': api_op,
                            'formatted': self.knowledge_engine.format_api_help(api_op)
                        }
                    else:
                        return {
                            'success': False,
                            'error': f'Operation not found: {category}.{operation}'
                        }
                else:
                    # Return all form API
                    return {
                        'success': True,
                        'api_type': 'form',
                        'api': self.knowledge_engine.form_api
                    }

            elif api_type == 'grid':
                if operation and category:
                    api_op = self.knowledge_engine.get_grid_api_operation(category, operation)
                    if api_op:
                        return {
                            'success': True,
                            'api_type': 'grid',
                            'category': category,
                            'operation': operation,
                            'details': api_op,
                            'formatted': self.knowledge_engine.format_api_help(api_op)
                        }
                    else:
                        return {
                            'success': False,
                            'error': f'Operation not found: {category}.{operation}'
                        }
                else:
                    # Return all grid API
                    return {
                        'success': True,
                        'api_type': 'grid',
                        'api': self.knowledge_engine.grid_api
                    }

            else:
                return {
                    'success': False,
                    'error': f'Invalid api_type: {api_type}. Use "form" or "grid"'
                }

        except Exception as e:
            logger.error(f"Error getting API help: {e}")
            return {
                'success': False,
                'error': f'Error getting API help: {str(e)}'
            }

    def generate_code(
        self,
        pattern_name: str,
        variables: Dict[str, str] = None,
        file_path: str = None,
        xml_content: str = None
    ) -> Dict:
        """Generate code from pattern

        Args:
            pattern_name: Pattern name (e.g., 'form_init_new')
            variables: Dict of variable substitutions
            file_path: Current file path for context detection (optional)
            xml_content: XML content for context detection (optional)

        Returns:
            Dict with generated code and metadata
        """
        try:
            # Detect context if file provided
            context = None
            if file_path or xml_content:
                context_result = self.detect_context(file_path, xml_content)
                if context_result.get('success'):
                    context = context_result

            # Generate code
            result = self.code_generator.generate_from_pattern(
                pattern_name,
                variables,
                context
            )

            return result

        except Exception as e:
            logger.error(f"Error generating code: {e}")
            return {
                'success': False,
                'error': f'Error generating code: {str(e)}'
            }

    def generate_code_from_snippet(
        self,
        snippet_name: str,
        variables: Dict[str, str] = None
    ) -> Dict:
        """Generate code from snippet

        Args:
            snippet_name: Snippet name (e.g., 'get_parent_form_from_grid')
            variables: Dict of variable substitutions

        Returns:
            Dict with generated code
        """
        try:
            result = self.code_generator.generate_from_snippet(
                snippet_name,
                variables
            )

            return result

        except Exception as e:
            logger.error(f"Error generating code from snippet: {e}")
            return {
                'success': False,
                'error': f'Error generating code from snippet: {str(e)}'
            }

    def generate_function_skeleton(
        self,
        function_type: str,
        function_name: str,
        file_path: str = None,
        xml_content: str = None
    ) -> Dict:
        """Generate function skeleton

        Args:
            function_type: Function type (e.g., 'active_form', 'onchange_field')
            function_name: Function name (e.g., 'active$Form$')
            file_path: Current file path for context detection
            xml_content: XML content for context detection (fallback)

        Returns:
            Dict with generated function skeleton
        """
        try:
            # Detect context
            context_result = self.detect_context(file_path, xml_content)
            if not context_result.get('success'):
                return {
                    'success': False,
                    'error': 'Failed to detect context. Context required for function generation.'
                }

            context = context_result

            # Generate skeleton
            result = self.code_generator.generate_function_skeleton(
                function_type,
                function_name,
                context
            )

            return result

        except Exception as e:
            logger.error(f"Error generating function skeleton: {e}")
            return {
                'success': False,
                'error': f'Error generating function skeleton: {str(e)}'
            }

    def search_patterns(
        self,
        query: str = None,
        file_path: str = None,
        xml_content: str = None,
        context_filter: str = None
    ) -> Dict:
        """Search for patterns

        Args:
            query: Search query string (optional)
            file_path: Current file path for context-aware search (optional)
            xml_content: XML content for context detection (optional)
            context_filter: Context filter ('Dir', 'Grid Detail', 'Grid View') (optional)

        Returns:
            Dict with matching patterns
        """
        try:
            # Detect context if file provided
            if file_path or xml_content:
                context_result = self.detect_context(file_path, xml_content)
                if context_result.get('success'):
                    # Get patterns for this context
                    patterns = self.code_generator.get_context_appropriate_patterns(context_result)
                    return {
                        'success': True,
                        'patterns': patterns,
                        'context': context_result.get('file_type'),
                        'grid_subtype': context_result.get('grid_subtype')
                    }

            # If no context, get all patterns
            all_patterns = self.knowledge_engine.patterns.get('patterns', {})

            # Filter by context if specified
            if context_filter:
                filtered_patterns = []
                for name, pattern in all_patterns.items():
                    pattern_context = pattern.get('context', '')
                    if context_filter in pattern_context:
                        filtered_patterns.append({
                            'name': name,
                            'description': pattern.get('description', ''),
                            'context': pattern_context,
                            'location': pattern.get('location', '')
                        })
                return {
                    'success': True,
                    'patterns': filtered_patterns,
                    'filter': context_filter
                }

            # Search by query if specified
            if query:
                matching_patterns = []
                query_lower = query.lower()
                for name, pattern in all_patterns.items():
                    if (query_lower in name.lower() or
                        query_lower in pattern.get('description', '').lower() or
                        query_lower in pattern.get('context', '').lower()):
                        matching_patterns.append({
                            'name': name,
                            'description': pattern.get('description', ''),
                            'context': pattern.get('context', ''),
                            'location': pattern.get('location', '')
                        })
                return {
                    'success': True,
                    'patterns': matching_patterns,
                    'query': query
                }

            # Return all patterns
            pattern_list = []
            for name, pattern in all_patterns.items():
                pattern_list.append({
                    'name': name,
                    'description': pattern.get('description', ''),
                    'context': pattern.get('context', ''),
                    'location': pattern.get('location', '')
                })

            return {
                'success': True,
                'patterns': pattern_list
            }

        except Exception as e:
            logger.error(f"Error searching patterns: {e}")
            return {
                'success': False,
                'error': f'Error searching patterns: {str(e)}'
            }

    def get_critical_rules(self, file_path: str = None, xml_content: str = None) -> Dict:
        """Get critical rules for current context

        Args:
            file_path: Current file path
            xml_content: XML content (fallback)

        Returns:
            Dict with critical rules
        """
        try:
            # Detect context
            context_result = self.detect_context(file_path, xml_content)
            if not context_result.get('success'):
                return {
                    'success': False,
                    'error': 'Failed to detect context'
                }

            # Get critical rules
            critical_rules = context_result.get('critical_rules', [])
            rule_details = []

            for rule_id in critical_rules:
                rule = self.knowledge_engine.get_api_selection_rule(rule_id)
                if rule:
                    rule_details.append(rule)

            return {
                'success': True,
                'file_type': context_result.get('file_type'),
                'grid_subtype': context_result.get('grid_subtype'),
                'critical_rules': critical_rules,
                'rule_details': rule_details,
                'recommendations': context_result.get('recommendations', [])
            }

        except Exception as e:
            logger.error(f"Error getting critical rules: {e}")
            return {
                'success': False,
                'error': f'Error getting critical rules: {str(e)}'
            }

    def get_all_snippets(self, critical_only: bool = False) -> Dict:
        """Get all available code snippets

        Args:
            critical_only: Return only critical snippets

        Returns:
            Dict with snippets
        """
        try:
            if critical_only:
                snippets = self.knowledge_engine.get_all_critical_snippets()
            else:
                snippets = self.knowledge_engine.patterns.get('snippets', {})

            snippet_list = []
            for name, snippet in snippets.items():
                snippet_list.append({
                    'name': name,
                    'code': snippet.get('code', ''),
                    'description': snippet.get('description', ''),
                    'critical': snippet.get('critical', False)
                })

            return {
                'success': True,
                'snippets': snippet_list,
                'critical_only': critical_only
            }

        except Exception as e:
            logger.error(f"Error getting snippets: {e}")
            return {
                'success': False,
                'error': f'Error getting snippets: {str(e)}'
            }
