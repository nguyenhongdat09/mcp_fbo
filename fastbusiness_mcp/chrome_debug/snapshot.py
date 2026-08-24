"""Snapshot các phần tử tương tác trên trang (loại bỏ raw HTML, gắn ref e0, e1...)."""

from __future__ import annotations

from typing import Any, Dict, List
from .constants import MAX_LABEL_CHARS_DEFAULT, MAX_SNAPSHOT_NODES_DEFAULT
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

SNAPSHOT_IN_PAGE_JS = """
(function(params) {
    const maxNodes = params.maxNodes || 120;
    const maxLabelChars = params.maxLabelChars || 120;
    const startRefIndex = params.startRefIndex || 0;
    const mode = params.mode || 'interactive';

    function isVisible(el) {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
            return false;
        }
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }

    function cleanText(txt) {
        if (!txt) return '';
        return txt.replace(/\\s+/g, ' ').trim().substring(0, maxLabelChars);
    }

    function getLabelFor(el) {
        // 1. aria-label hoặc title
        let label = el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('placeholder');
        if (label) return cleanText(label);

        // 2. <label for="...">
        if (el.id) {
            const lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl && lbl.innerText) return cleanText(lbl.innerText);
        }

        // 3. Parent label
        const parentLabel = el.closest('label');
        if (parentLabel && parentLabel.innerText) {
            return cleanText(parentLabel.innerText);
        }

        // 4. Element text (button, link, etc.)
        if (['BUTTON', 'A', 'SPAN'].includes(el.tagName)) {
            return cleanText(el.innerText || el.textContent);
        }

        // 5. Tìm label lân cận (cho ExtJS / FBO)
        if (el.parentElement) {
            const prev = el.previousElementSibling;
            if (prev && (prev.tagName === 'LABEL' || prev.classList.contains('label'))) {
                return cleanText(prev.innerText);
            }
        }

        return '';
    }

    let interactiveSelector = 'button, input, select, textarea, a[href], [role="button"], [role="checkbox"], [role="radio"], [role="tab"], [tabindex]:not([tabindex="-1"])';
    if (mode === 'fields_only') {
        interactiveSelector = 'input, select, textarea';
    }

    const all = Array.from(document.querySelectorAll(interactiveSelector));

    const results = [];
    let curRef = startRefIndex;

    for (let i = 0; i < all.length && results.length < maxNodes; i++) {
        const el = all[i];
        if (!isVisible(el)) continue;

        const tag = el.tagName.toLowerCase();
        if (tag === 'svg' || tag === 'path') continue;

        const ref = 'e' + curRef;
        curRef++;
        el.setAttribute('data-cdp-ref', ref);

        const name = el.getAttribute('name') || '';
        const id = el.id || '';
        const type = el.getAttribute('type') || (tag === 'textarea' ? 'textarea' : tag === 'select' ? 'select' : '');
        const role = el.getAttribute('role') || '';
        const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
        const label = getLabelFor(el);

        let value = '';
        if (tag === 'input' || tag === 'textarea' || tag === 'select') {
            value = el.value ? String(el.value).substring(0, 50) : '';
        }

        const item = {
            ref: ref,
            tag: tag,
            name: name,
            id: id,
            label: label,
            disabled: disabled
        };
        if (type) item.type = type;
        if (role) item.role = role;
        if (value) item.value = value;

        results.push(item);
    }

    return {
        elements: results,
        nextRefIndex: curRef
    };
})
"""


def build_page_snapshot(
    page: Any,
    max_nodes: int = MAX_SNAPSHOT_NODES_DEFAULT,
    max_label_chars: int = MAX_LABEL_CHARS_DEFAULT,
    mode: str = "interactive",
) -> Dict[str, Any]:
    """Quét tất cả các frames trên Page để thu thập elements tương tác."""
    frames_data: List[Dict[str, Any]] = []
    current_ref_idx = 0

    frames = page.frames
    for idx, frame in enumerate(frames):
        try:
            frame_url = frame.url or ""
            if frame_url.startswith("chrome-extension://"):
                continue

            res = frame.evaluate(
                SNAPSHOT_IN_PAGE_JS,
                {
                    "maxNodes": max_nodes,
                    "maxLabelChars": max_label_chars,
                    "startRefIndex": current_ref_idx,
                    "mode": mode,
                },
            )

            elements = res.get("elements", [])
            current_ref_idx = res.get("nextRefIndex", current_ref_idx + len(elements))

            if elements or idx == 0:
                frames_data.append({
                    "frame_index": idx,
                    "frame_url": frame_url,
                    "node_count": len(elements),
                    "elements": elements,
                })
        except Exception as e:
            logger.debug(f"Frame {idx} evaluate error: {e}")
            continue

    return {
        "tab_url": page.url or "",
        "tab_title": page.title() or "",
        "frames": frames_data,
    }
