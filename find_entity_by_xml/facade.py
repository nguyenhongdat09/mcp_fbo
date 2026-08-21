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
    Extract SQL and JS blocks from the flat XML by delegating to xml_controller_summary.
    Returns: { sql_blocks, js_blocks, system_entities, param_entities, flat_text }
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
            
    from xml_controller_summary.extract import (
        extract_controller_blocks,
        extract_cdata_from_inner,
        CLIENT_SCRIPT_RE,
    )
    extracted = extract_controller_blocks(flat_text)
    
    js_blocks = []
    seen_js = set()
    for jc in extracted.js_chunks:
        if jc.content:
            key = (jc.content.strip(), jc.line)
            seen_js.add(key)
            js_blocks.append({
                "content": jc.content,
                "line": jc.line,
                "tag": jc.source,
            })

    # R1: Restore <clientScript> on facade (for FBOGraph parser) without polluting summary_xml ANTLR
    for m in CLIENT_SCRIPT_RE.finditer(flat_text):
        inner = m.group(1)
        content = extract_cdata_from_inner(inner)
        if content:
            line = flat_text[:m.start()].count('\n') + 1
            key = (content.strip(), line)
            if key not in seen_js:
                seen_js.add(key)
                js_blocks.append({
                    "content": content,
                    "line": line,
                    "tag": "clientScript",
                })
            
    sql_blocks = []
    for sc in extracted.sql_chunks:
        if sc.content:
            tag = sc.kind
            if sc.event:
                tag = f"command:{sc.event}"
            elif sc.id:
                tag = f"action:{sc.id}"
            sql_blocks.append({
                "content": sc.content,
                "line": sc.line,
                "tag": tag,
            })
            
    return {
        'sql_blocks': sql_blocks,
        'js_blocks': js_blocks,
        'system_entities': system_entities,
        'param_entities': param_entities,
        'flat_text': flat_text
    }


