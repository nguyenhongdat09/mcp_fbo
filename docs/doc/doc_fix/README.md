# doc_fix — Ghi chép fix / review cho Gemini

| File | Nội dung |
|------|----------|
| [FIX-clone_things-dual-app-sys.md](./FIX-clone_things-dual-app-sys.md) | Dual lookup App+Sys + noise filter cho `clone_things` — prompt review |
| [FIX-clone_things-use-sys-section-misplace.md](./FIX-clone_things-use-sys-section-misplace.md) | Object sys (`syscheckfields`) bị append dưới `USE [..._A]` thay vì `[..._S]` — Gemini fix |
| [FIX-clone_things-exclude-infra-deps-silent.md](./FIX-clone_things-exclude-infra-deps-silent.md) | Dependency `FastBusiness$*` (vd `GetLayoutConfig`) bị exclude im lặng khi seed XML — Gemini fix |
| [FIX-clone_things-encrypted-and-sql-bom.md](./FIX-clone_things-encrypted-and-sql-bom.md) | Object encrypt → `encrypt_proc` (không not_found); BOM `\ufeff` lạ trong `.sql` sau USE/GO — Gemini fix |
| [FIX-compare_things-live-findings.md](./FIX-compare_things-live-findings.md) | `compare_things` bugs live (CRLF flag, seed, missing_both, …) — Gemini fix; XML flat xem file `13` riêng |
| [FIX-compare-things-summary-token-budget.md](./FIX-compare-things-summary-token-budget.md) | (cũ, superseded) siết token — xem FIX-compare_things-diff-only-no-preview.md |
| [FIX-compare_things-diff-only-no-preview.md](./FIX-compare_things-diff-only-no-preview.md) | Chỉ báo điểm khác (ranges/signals/schema); CẤM preview/dump; source=clone-from, target=đang sửa — Gemini fix |
| [FIX-compare_things-all-extensions-except-f.md](./FIX-compare_things-all-extensions-except-f.md) | So mọi đuôi file (`.ent`, `.txt`, …); **cấm `.f`** — Gemini fix |
| [FIX-compare_things-signals-pk-message.md](./FIX-compare_things-signals-pk-message.md) | Signals SQL 2 phía; PK chỉ khác order không `different`; message file khớp `meta_diff` — Gemini fix (live 2026-09-11) |
| [FIX-compare_things-sql-refs-noise.md](./FIX-compare_things-sql-refs-noise.md) | Làm sạch refs SQL: bỏ false `datetime2`; heuristic view; `refs_match_body_diff` đúng điều kiện — Gemini fix |

Spec gốc feature: [`../clone_things/`](../clone_things/), [`../compare_things/`](../compare_things/).  
Bổ sung XML flat (file mới, không sửa 01–12): [`../compare_things/13_xml_view_original_or_flat.md`](../compare_things/13_xml_view_original_or_flat.md).
