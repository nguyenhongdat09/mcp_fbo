import os
import re
from typing import List, Dict, Any

from find_entity_by_xml.entity_resolver import resolve_fbo_xml_entities, read_file_content


# --- Tokenizer ---

class XmlSegmentTokenizer:
    @staticmethod
    def tokenize(xml_text: str) -> List[Dict[str, Any]]:
        segments = []
        i = 0
        length = len(xml_text)
        
        while i < length:
            # 1. XML Declaration / PI
            if xml_text.startswith('<?', i):
                start = i
                end = xml_text.find('?>', i + 2)
                if end == -1:
                    end = length
                else:
                    end += 2
                content = xml_text[start:end]
                seg_type = 'XML_DECL' if content.startswith('<?xml') else 'PROCESSING_INSTRUCTION'
                segments.append({'type': seg_type, 'content': content, 'start': start, 'end': end})
                i = end
                continue
                
            # 2. COMMENT
            if xml_text.startswith('<!--', i):
                start = i
                end = xml_text.find('-->', i + 4)
                if end == -1:
                    end = length
                else:
                    end += 3
                content = xml_text[start:end]
                segments.append({'type': 'COMMENT', 'content': content, 'start': start, 'end': end})
                i = end
                continue
                
            # 3. CDATA
            if xml_text.startswith('<![CDATA[', i):
                start = i
                end = xml_text.find(']]>', i + 9)
                if end == -1:
                    end = length
                else:
                    end += 3
                content = xml_text[start:end]
                segments.append({'type': 'CDATA', 'content': content, 'start': start, 'end': end})
                i = end
                continue
                
            # 4. DOCTYPE
            if xml_text.startswith('<!DOCTYPE', i):
                start = i
                index = i + 9
                in_brackets = False
                in_quote = False
                quote_char = ''
                while index < length:
                    char = xml_text[index]
                    if in_quote:
                        if char == quote_char and xml_text[index - 1] != '\\':
                            in_quote = False
                    else:
                        if char in ('"', "'"):
                            in_quote = True
                            quote_char = char
                        elif char == '[':
                            in_brackets = True
                        elif char == ']' and in_brackets:
                            in_brackets = False
                        elif char == '>' and not in_brackets:
                            break
                    index += 1
                end = min(index + 1, length)
                content = xml_text[start:end]
                segments.append({'type': 'DOCTYPE', 'content': content, 'start': start, 'end': end})
                i = end
                continue
                
            # 5. ENTITY REFERENCE
            if xml_text[i] == '&':
                match = re.match(r'^&([\w.]+);', xml_text[i:])
                if match:
                    entity_name = match.group(1)
                    is_predefined = entity_name in ('amp', 'lt', 'gt', 'quot', 'apos')
                    is_numeric = entity_name.startswith('#')
                    if not is_predefined and not is_numeric:
                        start = i
                        end = i + len(match.group(0))
                        content = match.group(0)
                        segments.append({'type': 'ENTITY_REF', 'content': content, 'start': start, 'end': end, 'entity_name': entity_name})
                        i = end
                        continue
                        
            # 6. TEXT
            start = i
            next_special = length
            
            for j in range(i, length):
                if (xml_text.startswith('<?', j) or
                    xml_text.startswith('<!--', j) or
                    xml_text.startswith('<![CDATA[', j) or
                    xml_text.startswith('<!DOCTYPE', j)):
                    next_special = j
                    break
                    
                if xml_text[j] == '&':
                    match = re.match(r'^&([\w.]+);', xml_text[j:])
                    if match:
                        entity_name = match.group(1)
                        is_predefined = entity_name in ('amp', 'lt', 'gt', 'quot', 'apos')
                        is_numeric = entity_name.startswith('#')
                        if not is_predefined and not is_numeric:
                            next_special = j
                            break
                            
            if next_special == start:
                next_special = start + 1
                
            content = xml_text[start:next_special]
            segments.append({'type': 'TEXT', 'content': content, 'start': start, 'end': next_special})
            i = next_special
            
        return segments


# --- Merger ---

class TextBlockMerger:
    PART_GAP = ''
    CDATA_INNER_LEADING = ''
    
    @staticmethod
    def merge_text_block(text_inner: str, file_path: str, general_entities: Dict[str, Any], options: Dict[str, Any] = None) -> Dict[str, Any]:
        if options is None:
            options = {}
        max_depth = options.get('max_depth', 20)
        
        warnings = []
        text_inner = text_inner.replace('\r\n', '\n')
        sub_segments = XmlSegmentTokenizer.tokenize(text_inner)
        parts = []
        
        def expand_entity(ent_name: str, depth: int, expanding_stack: List[str], current_file: str):
            if depth > max_depth:
                warnings.append({'code': 'DEPTH_LIMIT_EXCEEDED', 'message': f"Max depth exceeded for &{ent_name};"})
                return {'text': f"&{ent_name};", 'missing': True}
                
            if ent_name in expanding_stack:
                warnings.append({'code': 'CIRCULAR_ENTITY', 'message': f"Circular entity: &{ent_name};"})
                return {'text': f"&{ent_name};", 'missing': True}
                
            ent_decl = general_entities.get(ent_name)
            if not ent_decl:
                warnings.append({'code': 'MISSING_ENTITY', 'message': f"Missing entity: &{ent_name};"})
                return {'text': f"&{ent_name};", 'missing': True}
                
            raw_content = ""
            ent_file = ent_decl.get('sourceFile', current_file)
            
            if ent_decl.get('systemUrl'):
                if os.path.exists(ent_file):
                    raw_content = read_file_content(ent_file)
                    if raw_content is None:
                        raw_content = f"/* Lỗi đọc file SYSTEM: {ent_file} */"
                    else:
                        raw_content = raw_content.replace('\r\n', '\n')
                else:
                    raw_content = f"/* Không tìm thấy file SYSTEM: {ent_file} */"
            else:
                raw_content = (ent_decl.get('value') or "").replace('\r\n', '\n')
                
            next_stack = expanding_stack + [ent_name]
            sub_expanded = expand_text(raw_content, depth + 1, next_stack, ent_file)
            
            return {
                'text': sub_expanded['text'],
                'source_file': ent_file,
            }
            
        def expand_text(text: str, depth: int, expanding_stack: List[str], current_file: str):
            segs = XmlSegmentTokenizer.tokenize(text)
            result_text = ""
            
            for seg in segs:
                if seg['type'] == 'ENTITY_REF':
                    res = expand_entity(seg['entity_name'], depth, expanding_stack, current_file)
                    result_text += res['text']
                elif seg['type'] == 'CDATA':
                    inner = seg['content'][9:-3]
                    inner_res = expand_text(inner, depth, expanding_stack, current_file)
                    result_text += inner_res['text']
                else:
                    result_text += seg['content']
                    
            return {'text': result_text}

        for seg in sub_segments:
            if seg['type'] == 'CDATA':
                inner = seg['content'][9:-3]
                parts.append({'type': 'native', 'text': inner})
            elif seg['type'] == 'ENTITY_REF':
                res = expand_entity(seg['entity_name'], 0, [], file_path)
                if res.get('missing'):
                    parts.append({'type': 'entity', 'text': f"&{seg['entity_name']};", 'missing': True})
                else:
                    parts.append({'type': 'entity', 'text': res['text'], 'missing': False})
            elif seg['type'] == 'TEXT':
                parts.append({'type': 'native', 'text': seg['content']})
                
        merged_text = ""
        for part in parts:
            if merged_text:
                merged_text += TextBlockMerger.PART_GAP
            merged_text += part['text']
            
        if merged_text:
            merged_text = TextBlockMerger.CDATA_INNER_LEADING + merged_text
            
        return {
            'merged_text': merged_text,
            'segments': parts,
            'warnings': warnings
        }


# --- Expander ---

class XmlEntityExpander:
    CDATA_BLOCK_OPEN = '<text><![CDATA[\n'
    CDATA_BLOCK_CLOSE = '\n]]></text>'
    
    @staticmethod
    def escape_cdata_content(content: str) -> str:
        return content.replace(']]>', ']]]]><![CDATA[>')

    @staticmethod
    def expand_xml_entities(file_path: str, source_text: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        if options is None:
            options = {}
        max_depth = options.get('max_depth', 20)
        
        source_text = source_text.replace('\r\n', '\n')
        general_entities, param_ents, _, _ = resolve_fbo_xml_entities(file_path)
        
        entities_dict = {
            name: {
                'value': ent.get('value'),
                'systemUrl': ent.get('systemUrl') or ent.get('external_file'),
                'sourceFile': ent.get('sourceFile') or ent.get('declared_in_file') or file_path
            }
            for name, ent in general_entities.items()
        }
        
        flat_text = ""
        warnings = []
        
        def expand_outside_text(text: str, depth: int = 0, expanding_stack: List[str] = None):
            if expanding_stack is None:
                expanding_stack = []
                
            if depth > max_depth:
                return {'text': text}
                
            segs = XmlSegmentTokenizer.tokenize(text)
            result = ""
            
            for seg in segs:
                if seg['type'] == 'ENTITY_REF':
                    ent_name = seg['entity_name']
                    if ent_name in expanding_stack:
                        result += seg['content']
                        continue
                        
                    ent_decl = entities_dict.get(ent_name)
                    raw_content = ""
                    is_missing = False
                    
                    if not ent_decl:
                        is_missing = True
                        raw_content = seg['content']
                    else:
                        if ent_decl.get('systemUrl'):
                            ent_source = ent_decl.get('sourceFile')
                            if os.path.exists(ent_source):
                                raw_content = read_file_content(ent_source)
                                if raw_content is None:
                                    raw_content = f"<!-- Lỗi đọc file SYSTEM: {ent_source} -->"
                                    is_missing = True
                                else:
                                    raw_content = raw_content.replace('\r\n', '\n')
                            else:
                                raw_content = f"<!-- Không tìm thấy file SYSTEM: {ent_source} -->"
                                is_missing = True
                        else:
                            raw_content = (ent_decl.get('value') or "").replace('\r\n', '\n')
                            
                    if not is_missing:
                        next_stack = expanding_stack + [ent_name]
                        res = expand_outside_text(raw_content, depth + 1, next_stack)
                        result += res['text']
                    else:
                        result += raw_content
                else:
                    result += seg['content']
                    
            return {'text': result}
            
        def append_expanded_outside_text(text: str):
            nonlocal flat_text
            res = expand_outside_text(text)
            flat_text += res['text']
            
        has_text_tag = '<text>' in source_text and '</text>' in source_text
        
        if not has_text_tag:
            append_expanded_outside_text(source_text)
            warnings.append({'code': 'NO_TEXT_BLOCK', 'message': 'No <text> block found for CDATA merge.'})
        else:
            i = 0
            length = len(source_text)
            while i < length:
                text_start = source_text.find('<text>', i)
                if text_start == -1:
                    append_expanded_outside_text(source_text[i:])
                    break
                    
                append_expanded_outside_text(source_text[i:text_start])
                
                text_end = source_text.find('</text>', text_start + 6)
                if text_end == -1:
                    append_expanded_outside_text(source_text[text_start:])
                    break
                    
                text_inner = source_text[text_start + 6:text_end]
                
                merged_model = TextBlockMerger.merge_text_block(text_inner, file_path, entities_dict, {'max_depth': max_depth})
                raw_merged = merged_model['merged_text']
                escaped_merged = XmlEntityExpander.escape_cdata_content(raw_merged)
                
                flat_text += XmlEntityExpander.CDATA_BLOCK_OPEN
                flat_text += escaped_merged
                flat_text += XmlEntityExpander.CDATA_BLOCK_CLOSE
                
                if merged_model.get('warnings'):
                    warnings.extend(merged_model['warnings'])
                    
                i = text_end + 7
                
        return {
            'flat_text': flat_text,
            'warnings': warnings,
            'system_entities': entities_dict,
            'param_entities': param_ents
        }
