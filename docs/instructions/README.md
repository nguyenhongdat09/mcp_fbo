# 📚 FastBusiness MCP Server - Documentation

## 🎯 AI Instructor Guide

**File duy nhất cần dùng:** [`INSTRUCTOR_GUIDE.md`](../INSTRUCTOR_GUIDE.md)

**Version:** 3.0 (Updated: 2024-10-31)

---

## 📖 Nội Dung INSTRUCTOR_GUIDE.md

File này chứa **TẤT CẢ** hướng dẫn cho AI assistant (Claude, Copilot, etc.) để làm việc đúng với FastBusiness XML:

### ✅ Có trong guide:

1. **SQL Generation Workflow** ⭐ NEW
   - Auto-detect field type from naming
   - Generate `exec fsd_addfields` SQL
   - Always ask user after generating XML field

2. **DataFormatString Auto-Detection** ⭐ NEW
   - Context-aware (View vs Input)
   - Auto-detect from field name patterns
   - Complete format mapping table

3. **FastBusiness API Rules** ⭐ CRITICAL
   - ES5 JavaScript only (no const, await, arrow functions)
   - Form API: `f.getItemValue()`, `f.setItemValue()`
   - Grid Detail: `g.get_element().parentForm`
   - Result Access: `result[index].Value` (by INDEX, not property)

4. **Complete Workflows**
   - Add new field with SQL
   - Add event handler (ES5 syntax)
   - Grid Detail calculations with parent form
   - Response handler with column mapping

5. **Common Mistakes & How to Avoid**
   - 5 critical mistakes with examples
   - ✅ Correct vs ❌ Wrong comparisons

6. **Field Type Detection**
   - Auto-detect SQL type from field name
   - Complete pattern matching table
   - Examples for all cases

---

## 🚀 Cách Sử Dụng

### Option 1: Claude Desktop / Cline (Recommended)

**Paste vào conversation:**

```
Please read and follow this FastBusiness development guide:

[Copy toàn bộ nội dung file docs/INSTRUCTOR_GUIDE.md]
```

Sau đó Claude/AI sẽ follow tất cả rules trong guide.

### Option 2: Add as MCP Resource (Advanced)

Edit `fastbusiness_mcp/server.py`:

```python
async def list_resources(self) -> list[types.Resource]:
    return [
        # ... existing resources ...

        types.Resource(
            uri="fastbusiness://docs/instructor",
            name="FastBusiness Development Instructor Guide v3.0",
            description="Complete guide for AI to generate correct FastBusiness code",
            mimeType="text/markdown",
        ),
    ]

async def read_resource(self, uri: str) -> str:
    # ... existing code ...

    elif uri == "fastbusiness://docs/instructor":
        guide_path = Path(__file__).parent.parent / "docs" / "INSTRUCTOR_GUIDE.md"
        if guide_path.exists():
            return guide_path.read_text(encoding="utf-8")
        return "Instructor guide not found"
```

Sau đó trong Claude Desktop:
```
Please read the instructor guide from resources and follow it.
```

### Option 3: VS Code Extension

Nếu dùng extension hỗ trợ context files, add:

```json
{
  "contextFiles": [
    "docs/INSTRUCTOR_GUIDE.md"
  ]
}
```

---

## 📋 Version History

### v3.0 (2024-10-31) - CURRENT ✅
- ✅ Added SQL generation workflow
- ✅ Added dataFormatString auto-detection
- ✅ Added FastBusiness API rules (ES5 JavaScript)
- ✅ Added field type detection patterns
- ✅ Added complete workflow examples
- ✅ Added common mistakes section
- ✅ 572 lines of comprehensive guide

### v2.0 (2024-10-31) - DEPRECATED ❌
- ~~LevelDB integration workflows~~
- **Replaced by v3.0**

### v1.0 (2024-10-30) - DEPRECATED ❌
- ~~Basic validation rules~~
- **Replaced by v3.0**

---

## ✅ Test Với AI

Sau khi paste guide vào Claude/AI, test với:

### Test 1: Field Generation with SQL
```
User: "Thêm tiền ngoại tệ vào form"

Expected:
✅ Generate field: tien_nt (with _nt suffix)
✅ Format: @foreignCurrencyAmountInputFormat
✅ Ask: "Bạn có muốn generate SQL không?"
✅ If yes: exec fsd_addfields 'd93', 'tien_nt', 'numeric(19,4)'
```

### Test 2: ES5 JavaScript
```
User: "Thêm xử lý nhập ngày lập chứng từ"

Expected:
✅ Use var (not const/let)
✅ Use f.setItemValue()
✅ Use function keyword (not arrow)
```

### Test 3: Grid Detail with Parent
```
User: "Tính tiền VND = tiền NT * tỷ giá (tỷ giá ở form cha)"

Expected:
✅ var f = g.get_element().parentForm
✅ g.$a = {tien_vnd: '[tien_vnd]:=[tien_nt]*[$ty_gia]'}
```

---

## 🔗 Related Documentation

- [INSTALL.md](../../INSTALL.md) - Installation guide
- [VSCODE_MCP_SETUP.md](../../VSCODE_MCP_SETUP.md) - VS Code MCP setup
- [README.md](../../README.md) - Project overview
- [TESTING.md](../TESTING.md) - Testing guide

---

## 💡 Tips

### For AI Assistant Users

1. **Always paste the full guide** at the start of conversation
2. **Remind AI** if it forgets rules (e.g., "Remember to use ES5 JavaScript")
3. **Check generated code** matches the patterns in guide

### For Developers

1. **Update guide** when FastBusiness API changes
2. **Add examples** for new patterns you discover
3. **Test with real AI** before updating

---

## ❓ FAQ

### Q: Tôi có nhiều file instructor, dùng file nào?

**A:** Chỉ dùng **`INSTRUCTOR_GUIDE.md`** (file này). Các file khác đã cũ và bị xóa.

### Q: File này có gì mới so với version cũ?

**A:** v3.0 có thêm:
- SQL generation workflow (tự động hỏi user)
- DataFormatString auto-detection
- FastBusiness API ES5 rules
- Field type detection patterns

### Q: Tôi cần update guide khi nào?

**A:** Update khi:
- FastBusiness API có thay đổi
- Phát hiện pattern mới
- AI thường gen code sai ở chỗ nào đó

### Q: Làm sao AI nhớ được tất cả rules?

**A:** Paste full guide vào conversation. AI sẽ reference guide khi generate code.

---

**📌 REMEMBER: Only use `docs/INSTRUCTOR_GUIDE.md` - It's the single source of truth!**
