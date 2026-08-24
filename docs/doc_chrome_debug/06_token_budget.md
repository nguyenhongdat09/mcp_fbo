# 06 — Token Budget Strategy

## 1. Vấn đề

Agent có thể lãng phí token nếu:

- Gọi `chrome_debug(type=2)` lặp lại không cần thiết
- `type=2` trả quá nhiều node hoặc network body dài
- Dump HTML / grid qua `type=4`

---

## 2. Nguyên tắc tiết kiệm

| # | Nguyên tắc |
|---|------------|
| 1 | **Một tool** — agent nhớ `type` 1–4, không liệt kê 6 tên tool |
| 2 | **Static trước** — field name từ XML → `type=3` không cần `type=2` |
| 3 | **Cap mọi output** — config yaml |
| 4 | **Rule agent** — tối đa **3** lần `chrome_debug` / lượt (mọi type) |

---

## 3. Budget theo `type`

| type | Output ước lượng | Mức token | Cách giảm |
|------|------------------|-----------|----------|
| **1** | ~10–40 dòng JSON | Rất thấp | Chỉ ping + tabs |
| **2** | ≤120 nodes + vài lỗi | TB thấp | `include_errors=false` (future); cap body |
| **3** | JSON ngắn | Rất thấp | Một lần fill+click |
| **4** | JSON capped | Thấp | `max_result_chars` |

So sánh tham chiếu (không dùng nữa):

| Cách cũ | Token |
|---------|-------|
| 6 tool riêng + gọi status rồi list_tabs | Cao hơn ~1 round-trip |
| **1 tool + type** | Ít schema MCP, ít lần discover tools |

---

## 4. `type=2` — snapshot

- `max_nodes` mặc định ~120
- `max_label_chars` ~80
- `mode=fields_only` (phase 3): chỉ field có `name`/`id` FBO → giảm ~40–60% node

---

## 5. Cấu hình giới hạn (`chrome_debug.yaml`)

```yaml
limits:
  max_snapshot_nodes: 120
  max_label_chars: 80
  max_console_lines: 50
  max_network_errors: 30
  max_response_chars: 2000
  max_js_result_chars: 4000
```

---

## 6. Rule agent (tóm tắt)

| Rule | Lý do |
|------|-------|
| `type=1` một lần đầu session (trừ khi tab đổi) | Tránh lặp tabs |
| User báo lỗi → `type=2` trước `type=3` | Lỗi + ref một lần |
| Biết `name` từ XML → skip `type=2` | Tiết kiệm snapshot |
| Grid → `type=4`, không `type=3` cell | Grid ảo |
| Tối đa 3 lần `chrome_debug` / lượt | Tránh loop |

---

## 7. Liên kết

- Tool API: [04_tool_api.md](04_tool_api.md)
- Workflow: [05_agent_workflow.md](05_agent_workflow.md)
