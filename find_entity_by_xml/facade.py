import os
import re
from typing import List, Dict, Any, Optional

from find_entity_by_xml.entity_resolver import resolve_fbo_xml_entities, read_file_content, get_entities_for_file
from find_entity_by_xml.entity_expander import XmlEntityExpander

def read_file_content_safe(path: str) -> Optional[str]:
    """Read file content safely."""
    return read_file_content(path)

def resolve_entities(xml_path: str, force_reload: bool = False) -> Dict[str, Any]:
    """Resolve and return all entities and parameter entities for an XML file.
    Uses in-process RAM cache to avoid re-parsing."""
    raw_content = read_file_content(xml_path)
    if not raw_content:
        return {'system_entities': [], 'param_entities': []}
    
    general, param, _file_mtimes = get_entities_for_file(xml_path, force_reload=force_reload)
    return {
        'system_entities': general,
        'param_entities': param
    }

def list_entities(xml_path: str) -> List[Dict[str, Any]]:
    """Return a list of all general entities for a file."""
    res = resolve_entities(xml_path)
    entities_list = []
    for name, ent in res['system_entities'].items():
        ent_copy = ent.copy()
        ent_copy['name'] = name
        entities_list.append(ent_copy)
    return entities_list

def get_entity(xml_path: str, name: str) -> Optional[Dict[str, Any]]:
    """Get a specific entity by name."""
    entities = list_entities(xml_path)
    for ent in entities:
        if ent['name'] == name:
            return ent
    return None

def expand_entity_refs(text: str, xml_path: str, max_depth: int = 20) -> str:
    """Expand entity references in a given text snippet."""
    if not text or "&" not in text:
        return text
        
    res = XmlEntityExpander.expand_xml_entities(xml_path, text, {'max_depth': max_depth})
    return res.get('flat_text', text)

def flat_xml(xml_path: str) -> str:
    """Return the flat XML content with all entities expanded."""
    raw_content = read_file_content(xml_path)
    if not raw_content:
        return ""
        
    res = XmlEntityExpander.expand_xml_entities(xml_path, raw_content)
    return res.get('flat_text', "")

def extract_expanded_blocks(xml_path: str) -> Dict[str, Any]:
    """
    Extract SQL and JS blocks from the flat XML.
    Returns: { sql_blocks, js_blocks, system_entities }
    """
    raw_content = read_file_content(xml_path)
    if not raw_content:
        return {'sql_blocks': [], 'js_blocks': [], 'system_entities': [], 'param_entities': [], 'flat_text': ""}
        
    res = XmlEntityExpander.expand_xml_entities(xml_path, raw_content)
    flat_text = res.get('flat_text', "")
    
    system_entities = []
    if 'system_entities' in res:
        for name, ent in res['system_entities'].items():
            ent_copy = ent.copy()
            ent_copy['name'] = name
            system_entities.append(ent_copy)
            
    param_entities = []
    if 'param_entities' in res:
        for name, ent in res['param_entities'].items():
            ent_copy = ent.copy()
            ent_copy['name'] = name
            param_entities.append(ent_copy)
            
    sql_blocks = []
    js_blocks = []
    
    def extract_blocks_for_tags(text: str, tags: List[str]) -> List[Dict[str, Any]]:
        blocks = []
        for tag in tags:
            # Find <tag ...>...</tag>
            pattern = r'<' + tag + r'\b[^>]*>(.*?)</' + tag + r'>'
            for match in re.finditer(pattern, text, flags=re.DOTALL | re.IGNORECASE):
                inner_content = match.group(1)
                
                # In flat XML, CDATA are escaped `]]]]><![CDATA[>`.
                # We unescape them to get pure text.
                # Actually, flat_text already has <text><![CDATA[ ... ]]></text>
                cdata_match = re.search(r'<text>\s*<!\[CDATA\[(.*?)\]\]>\s*</text>', inner_content, flags=re.DOTALL)
                if cdata_match:
                    content = cdata_match.group(1).replace(']]]]><![CDATA[>', ']]>').strip()
                else:
                    cdata_match_2 = re.search(r'<!\[CDATA\[(.*?)\]\]>', inner_content, flags=re.DOTALL)
                    if cdata_match_2:
                        content = cdata_match_2.group(1).replace(']]]]><![CDATA[>', ']]>').strip()
                    else:
                        # Strip other XML tags (e.g., if there's no CDATA block but plain text)
                        content = re.sub(r'<[^>]+>', '', inner_content).strip()
                    
                if content:
                    blocks.append({
                        "content": content,
                        "line": text[:match.start()].count('\n') + 1,
                        "tag": tag
                    })
        return blocks
        
    sql_blocks = extract_blocks_for_tags(flat_text, ["query", "command", "action"])
    js_blocks = extract_blocks_for_tags(flat_text, ["clientScript", "script"])
    
    # If no JS blocks were found using standard tags, try extracting from raw XML as fallback
    if not js_blocks:
        js_blocks = _extract_js_blocks_from_raw(flat_text)
        
    return {
        'sql_blocks': sql_blocks,
        'js_blocks': js_blocks,
        'system_entities': system_entities,
        'param_entities': param_entities,
        'flat_text': flat_text
    }

def _extract_js_blocks_from_raw(raw_content: str) -> List[Dict[str, Any]]:
    js_blocks = []
    
    # Example fallback regex for inline scripts (similar to xml_parser's fallback)
    onchange_pattern = r'onchange\s*=\s*["\']([^"\']+)["\']'
    for m in re.finditer(onchange_pattern, raw_content, flags=re.IGNORECASE):
        content = m.group(1).strip()
        if content:
            js_blocks.append({
                "content": content,
                "line": raw_content[:m.start()].count('\n') + 1,
                "tag": "onchange"
            })
            
    return js_blocks
