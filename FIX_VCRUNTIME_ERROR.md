# Fix: PyInstaller VCRUNTIME140.dll Decompression Error

## Vấn Đề

Lỗi khi chạy .exe trên máy khác:
```
[PYI-7600:ERROR] Failed to extract VCRUNTIME140.dll: decompression resulted in return code -1!
[PYI-7600:ERROR] Failed to extract entry: VCRUNTIME140.dll.
```

## Nguyên Nhân

- UPX compression (trong PyInstaller) nén VCRUNTIME140.dll bị lỗi
- Máy target thiếu Visual C++ Runtime
- Antivirus block file extraction

---

## ✅ Giải Pháp 1: Rebuild với UPX Disabled (Recommended)

**Đã fix trong commit này!** File `fastbusiness_mcp.spec` đã tắt UPX.

### Rebuild .exe:

```bash
cd E:\mcp_fbo

# Clean old build
rmdir /s /q build dist
del /q *.spec

# Rebuild với spec mới
pyinstaller fastbusiness_mcp.spec --clean

# Test .exe
dist\fastbusiness_mcp.exe
```

**Lưu ý**: File .exe sẽ lớn hơn (do không nén) nhưng chạy stable hơn.

---

## ✅ Giải Pháp 2: Cài Visual C++ Runtime trên máy target

Nếu máy khác thiếu Visual C++ Runtime:

### Download và cài:
1. **Microsoft Visual C++ Redistributable 2015-2022** (x64)
2. Link: https://aka.ms/vs/17/release/vc_redist.x64.exe
3. Cài đặt và restart máy

Sau đó chạy lại .exe.

---

## ✅ Giải Pháp 3: Đóng gói thành folder (onedir)

Thay vì 1 file .exe, đóng thành folder (stable hơn):

### Tạo spec mới cho onedir:

```bash
pyinstaller run_server.py ^
  --name fastbusiness_mcp ^
  --onedir ^
  --console ^
  --add-data "knowledge_base;knowledge_base" ^
  --add-data "data;data" ^
  --add-data "config.yaml;." ^
  --hidden-import mcp ^
  --hidden-import mcp.server ^
  --hidden-import mcp.server.stdio ^
  --hidden-import yaml ^
  --hidden-import lmdb ^
  --clean
```

Kết quả:
```
dist/
  fastbusiness_mcp/
    fastbusiness_mcp.exe    ← Chạy file này
    _internal/              ← Các DLL và dependencies
      VCRUNTIME140.dll
      python39.dll
      ...
```

**Ưu điểm**:
- Không compress DLL → Không bị lỗi decompression
- Startup nhanh hơn (không cần extract)
- Dễ debug

**Nhược điểm**:
- Nhiều file hơn (nhưng có thể zip lại)

---

## ✅ Giải Pháp 4: Check Antivirus

Một số antivirus block PyInstaller extraction:

1. Tắt tạm antivirus/Windows Defender
2. Chạy .exe
3. Nếu work → Add exception cho .exe trong antivirus

---

## So Sánh Các Cách

| Giải pháp | Ưu điểm | Nhược điểm | Recommended |
|-----------|---------|------------|-------------|
| **Disable UPX** | Đơn giản, 1 file .exe | File lớn hơn (~20MB) | ⭐⭐⭐⭐⭐ |
| **Cài VC++ Runtime** | .exe nhỏ | Cần cài thêm software | ⭐⭐⭐ |
| **Onedir** | Stable nhất | Nhiều file | ⭐⭐⭐⭐ |
| **Disable Antivirus** | Quick test | Không an toàn | ⭐⭐ |

---

## Build Commands Summary

### Option 1: Onefile (1 file .exe) - UPX disabled
```bash
pyinstaller fastbusiness_mcp.spec --clean
```
→ `dist/fastbusiness_mcp.exe` (20-30 MB)

### Option 2: Onedir (folder)
```bash
# Modify .spec: Change EXE() parameters to use COLLECT()
# Or use command above
```
→ `dist/fastbusiness_mcp/` folder

---

## Verify Build

Sau khi rebuild:

```bash
# Test trên máy build
dist\fastbusiness_mcp.exe

# Copy sang máy khác
# Test
fastbusiness_mcp.exe

# Nếu vẫn lỗi → Check Windows Event Viewer:
eventvwr.msc
→ Windows Logs → Application
→ Tìm lỗi liên quan PyInstaller
```

---

## Notes

- **UPX compression** giảm size file nhưng dễ lỗi với runtime DLLs
- **Onefile** tiện nhưng chậm hơn onedir (do phải extract)
- **Onedir** stable nhất cho production
- Always test .exe trên **clean Windows VM** trước khi deploy

---

## Current Fix

✅ **File `fastbusiness_mcp.spec` đã disable UPX**
✅ **Rebuild với `pyinstaller fastbusiness_mcp.spec --clean`**
✅ **Test trên máy khác**

Nếu vẫn lỗi → Dùng Giải pháp 2 hoặc 3.
