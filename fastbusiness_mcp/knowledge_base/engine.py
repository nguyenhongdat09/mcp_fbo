"""Knowledge Engine - Core engine to load and query API knowledge base"""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class KnowledgeEngine:
    """Core engine for FastBusiness API Knowledge Base

    Loads and queries YAML-based API reference, context rules, and patterns.
    """

    def __init__(self, knowledge_base_dir: str = "knowledge_base"):
        """Initialize Knowledge Engine

        Args:
            knowledge_base_dir: Path to knowledge_base directory
        """
        self.kb_dir = Path(knowledge_base_dir)
        self.api_ref_dir = self.kb_dir / "api_reference"

        # Loaded knowledge
        self.context_rules: Dict = {}
        self.form_api: Dict = {}
        self.grid_api: Dict = {}
        self.patterns: Dict = {}

        # Load all knowledge
        self._load_knowledge()

        logger.info(f"Knowledge Engine initialized from {self.kb_dir}")

    def _load_knowledge(self):
        """Load all YAML knowledge files"""
        try:
            # Load context rules
            context_rules_path = self.api_ref_dir / "context_rules.yaml"
            if context_rules_path.exists():
                with open(context_rules_path, 'r', encoding='utf-8') as f:
                    self.context_rules = yaml.safe_load(f)
                logger.info(f"[OK] Loaded context_rules.yaml")

            # Load form API
            form_api_path = self.api_ref_dir / "form_api.yaml"
            if form_api_path.exists():
                with open(form_api_path, 'r', encoding='utf-8') as f:
                    self.form_api = yaml.safe_load(f)
                logger.info(f"[OK] Loaded form_api.yaml")

            # Load grid API
            grid_api_path = self.api_ref_dir / "grid_api.yaml"
            if grid_api_path.exists():
                with open(grid_api_path, 'r', encoding='utf-8') as f:
                    self.grid_api = yaml.safe_load(f)
                logger.info(f"[OK] Loaded grid_api.yaml")

            # Load common patterns
            patterns_path = self.api_ref_dir / "common_patterns.yaml"
            if patterns_path.exists():
                with open(patterns_path, 'r', encoding='utf-8') as f:
                    self.patterns = yaml.safe_load(f)
                logger.info(f"[OK] Loaded common_patterns.yaml")

        except Exception as e:
            logger.error(f"Failed to load knowledge: {e}")
            raise

    # ============================================
    # CONTEXT RULES QUERIES
    # ============================================

    def get_file_type_info(self, file_type: str) -> Optional[Dict]:
        """Get file type information

        Args:
            file_type: 'Dir', 'Grid', or 'Filter'

        Returns:
            File type info dict or None
        """
        return self.context_rules.get('context_detection', {}).get('file_types', {}).get(file_type)

    def get_grid_subtype_info(self, subtype: str) -> Optional[Dict]:
        """Get grid subtype information

        Args:
            subtype: 'GridDetail' or 'GridView'

        Returns:
            Grid subtype info dict or None
        """
        grid_info = self.get_file_type_info('Grid')
        if grid_info:
            return grid_info.get('sub_types', {}).get(subtype)
        return None

    def get_api_selection_rule(self, rule_id: str) -> Optional[Dict]:
        """Get API selection rule by ID

        Args:
            rule_id: Rule ID (e.g., 'grid_detail_must_get_parent')

        Returns:
            Rule dict or None
        """
        rules = self.context_rules.get('api_selection_rules', [])
        for rule in rules:
            if rule.get('rule_id') == rule_id:
                return rule
        return None

    def get_critical_rules_for_context(self, context: str) -> List[Dict]:
        """Get all critical rules for a context

        Args:
            context: Context name (e.g., 'GridDetail', 'Form')

        Returns:
            List of critical rules
        """
        rules = []
        all_rules = self.context_rules.get('api_selection_rules', [])

        for rule in all_rules:
            if rule.get('priority') == 'CRITICAL':
                # Check if rule applies to this context
                condition = rule.get('condition', {})
                if context in str(condition):
                    rules.append(rule)

        return rules

    def get_cheat_sheet(self, context_key: str) -> Optional[Dict]:
        """Get cheat sheet for a context

        Args:
            context_key: Context key (e.g., "I'm in Form script (Dir, not grid)")

        Returns:
            Cheat sheet dict or None
        """
        return self.context_rules.get('cheat_sheet', {}).get(context_key)

    # ============================================
    # FORM API QUERIES
    # ============================================

    def get_form_api_operation(self, category: str, operation: str) -> Optional[Dict]:
        """Get form API operation details

        Args:
            category: API category (e.g., 'value_operations', 'form_state')
            operation: Operation name (e.g., 'get_item_value', 'get_action')

        Returns:
            Operation details dict or None
        """
        form_api = self.form_api.get('form_api', {})
        return form_api.get(category, {}).get(operation)

    def get_form_common_pattern(self, pattern_name: str) -> Optional[Dict]:
        """Get form common pattern

        Args:
            pattern_name: Pattern name (e.g., 'active_form_new')

        Returns:
            Pattern dict or None
        """
        return self.form_api.get('form_api', {}).get('common_patterns', {}).get(pattern_name)

    def get_form_anti_pattern(self, pattern_name: str) -> Optional[Dict]:
        """Get form anti-pattern

        Args:
            pattern_name: Pattern name (e.g., 'direct_field_access')

        Returns:
            Anti-pattern dict or None
        """
        return self.form_api.get('form_api', {}).get('anti_patterns', {}).get(pattern_name)

    def search_form_api(self, keyword: str) -> List[Dict]:
        """Search form API by keyword

        Args:
            keyword: Search keyword

        Returns:
            List of matching API operations
        """
        results = []
        form_api = self.form_api.get('form_api', {})

        for category_name, category in form_api.items():
            if isinstance(category, dict):
                for op_name, op_details in category.items():
                    if isinstance(op_details, dict):
                        # Check if keyword matches
                        if (keyword.lower() in op_name.lower() or
                            keyword.lower() in str(op_details.get('description', '')).lower() or
                            keyword.lower() in str(op_details.get('syntax', '')).lower()):
                            results.append({
                                'category': category_name,
                                'operation': op_name,
                                'details': op_details
                            })

        return results

    # ============================================
    # GRID API QUERIES
    # ============================================

    def get_grid_api_operation(self, category: str, operation: str) -> Optional[Dict]:
        """Get grid API operation details

        Args:
            category: API category (e.g., 'cell_operations', 'grid_state')
            operation: Operation name (e.g., 'get_item_value')

        Returns:
            Operation details dict or None
        """
        grid_api = self.grid_api.get('grid_api', {})
        return grid_api.get(category, {}).get(operation)

    def get_grid_context_usage(self, context: str) -> Optional[Dict]:
        """Get grid context-specific usage

        Args:
            context: 'grid_detail' or 'grid_view'

        Returns:
            Context usage dict or None
        """
        return self.grid_api.get('grid_api', {}).get('context_usage', {}).get(context)

    def get_grid_anti_pattern(self, pattern_name: str) -> Optional[Dict]:
        """Get grid anti-pattern

        Args:
            pattern_name: Pattern name

        Returns:
            Anti-pattern dict or None
        """
        return self.grid_api.get('grid_api', {}).get('anti_patterns', {}).get(pattern_name)

    # ============================================
    # PATTERNS QUERIES
    # ============================================

    def get_pattern(self, pattern_name: str) -> Optional[Dict]:
        """Get code pattern by name

        Args:
            pattern_name: Pattern name (e.g., 'form_init_new', 'grid_detail_init')

        Returns:
            Pattern dict or None
        """
        return self.patterns.get('patterns', {}).get(pattern_name)

    def get_patterns_for_context(self, context: str) -> List[Dict]:
        """Get all patterns for a context

        Args:
            context: Context name (e.g., 'Form (Dir)', 'Grid Detail')

        Returns:
            List of patterns
        """
        results = []
        patterns = self.patterns.get('patterns', {})

        for pattern_name, pattern in patterns.items():
            if pattern.get('context') == context:
                pattern['name_key'] = pattern_name
                results.append(pattern)

        return results

    def get_snippet(self, snippet_name: str) -> Optional[Dict]:
        """Get code snippet by name

        Args:
            snippet_name: Snippet name (e.g., 'get_parent_form_from_grid')

        Returns:
            Snippet dict or None
        """
        return self.patterns.get('snippets', {}).get(snippet_name)

    def get_all_critical_snippets(self) -> List[Dict]:
        """Get all critical code snippets

        Returns:
            List of critical snippets
        """
        results = []
        snippets = self.patterns.get('snippets', {})

        for snippet_name, snippet in snippets.items():
            if snippet.get('critical'):
                snippet['name'] = snippet_name
                results.append(snippet)

        return results

    # ============================================
    # HELPER METHODS
    # ============================================

    def get_api_for_context(self, context: str) -> str:
        """Determine which API to use for a context

        Args:
            context: Context name

        Returns:
            'form_api', 'grid_api', or 'both'
        """
        context_lower = context.lower()

        if 'grid detail' in context_lower or 'griddetail' in context_lower:
            return 'both'  # Grid Detail uses both g.xxx and f.xxx
        elif 'grid view' in context_lower or 'gridview' in context_lower:
            return 'grid_api'  # Grid View uses only g.xxx
        elif 'form' in context_lower or 'dir' in context_lower:
            return 'form_api'  # Form uses only f.xxx
        else:
            return 'form_api'  # Default to form API

    def format_api_help(self, api_operation: Dict) -> str:
        """Format API operation as help text

        Args:
            api_operation: API operation dict

        Returns:
            Formatted help text
        """
        if not api_operation:
            return "API operation not found"

        help_text = []

        # Syntax
        if 'syntax' in api_operation:
            help_text.append(f"**Syntax:** `{api_operation['syntax']}`")

        # Description
        if 'description' in api_operation:
            help_text.append(f"\n**Description:** {api_operation['description']}")

        # Returns
        if 'returns' in api_operation:
            help_text.append(f"\n**Returns:** `{api_operation['returns']}`")

        # Use when
        if 'use_when' in api_operation:
            use_when = api_operation['use_when']
            if isinstance(use_when, list):
                help_text.append("\n**Use when:**")
                for item in use_when:
                    help_text.append(f"  - {item}")
            else:
                help_text.append(f"\n**Use when:** {use_when}")

        # Examples
        if 'examples' in api_operation:
            help_text.append("\n**Examples:**")
            examples = api_operation['examples']
            if isinstance(examples, dict):
                for ex_name, ex_code in examples.items():
                    help_text.append(f"\n*{ex_name}:*")
                    help_text.append(f"```javascript\n{ex_code}\n```")
            elif isinstance(examples, list):
                for ex in examples:
                    if isinstance(ex, dict):
                        if 'description' in ex:
                            help_text.append(f"\n*{ex['description']}:*")
                        if 'code' in ex:
                            help_text.append(f"```javascript\n{ex['code']}\n```")
                    else:
                        help_text.append(f"```javascript\n{ex}\n```")
            else:
                help_text.append(f"```javascript\n{examples}\n```")

        # Important notes
        if 'important' in api_operation:
            help_text.append(f"\n[WARNING]  **Important:** {api_operation['important']}")

        # Critical notes
        if 'critical' in api_operation:
            help_text.append(f"\n🔴 **CRITICAL:** {api_operation['critical']}")

        # Anti-patterns
        if 'anti_patterns' in api_operation:
            help_text.append("\n**[ERROR] Anti-patterns (DON'T do this):**")
            for anti in api_operation['anti_patterns']:
                if isinstance(anti, dict):
                    help_text.append(f"\n*Wrong:* `{anti.get('wrong')}`")
                    help_text.append(f"*Correct:* `{anti.get('correct')}`")
                else:
                    help_text.append(f"  - {anti}")

        return '\n'.join(help_text)
