import os
import sys
import json
import random
import string
import hashlib
import machineid  # pip install py-machineid

from fastbusiness_mcp.config_paths import get_exe_dir

# key.json ngang cấp config.yaml: project root (dev) hoặc thư mục chứa .exe (frozen)
BASE_DIR = str(get_exe_dir())
KEY_FILE = os.path.join(BASE_DIR, "key.json")

def int32(x):
    """Giả lập kiểu signed 32-bit integer của Javascript"""
    x = x & 0xFFFFFFFF
    if x > 0x7FFFFFFF:
        x -= 0x100000000
    return x

def generate_license_key(extension_key: str) -> str:
    """Thuật toán mã hoá giống hệt JS trong file License.html"""
    secret = 'FBO-SECRET-2025'
    inp = extension_key + secret
    
    hash_val = 5381
    for char in inp:
        hash_val = ((hash_val << 5) + hash_val) + ord(char)
        hash_val = int32(hash_val)
        
    result = ''
    for round_idx in range(6):
        char_code = ord(inp[round_idx % len(inp)])
        hash_val = ((hash_val << 5) + hash_val) + round_idx + char_code
        hash_val = int32(hash_val)
        
        abs_hash = abs(hash_val)
        hex_str = format(abs_hash, 'X').zfill(4)
        result += hex_str
        
    hash_part = result[:24]
    checksum = sum(ord(c) for c in extension_key) % 100
    return f'FBO-{hash_part}-{checksum:02d}'

def get_machine_id_hash():
    """Lấy 8 ký tự mã băm từ ID phần cứng"""
    try:
        m_id = machineid.id()
        return hashlib.sha256(m_id.encode('utf-8')).hexdigest()[:8]
    except Exception:
        return "UNKNOWN0"

def generate_random_key():
    """Sinh key 16 ký tự: 8 ký tự đầu (Machine Hash) + 8 ký tự Random"""
    machine_hash = get_machine_id_hash()
    chars = string.ascii_letters + string.digits
    random_part = ''.join(random.choice(chars) for _ in range(8))
    return machine_hash + random_part

def load_or_create_keys():
    """Đọc file key.json, tạo mới hoặc reset nếu copy sang máy khác"""
    if os.path.exists(KEY_FILE):
        try:
            with open(KEY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            key_mcp = data.get("key_mcp", "")
            machine_hash = get_machine_id_hash()
            
            # Kiểm tra: nếu 8 ký tự đầu khác nhau => User copy file sang máy khác!
            if not key_mcp or not key_mcp.startswith(machine_hash):
                data["key_mcp"] = generate_random_key()
                data["key_license"] = ""
                with open(KEY_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
            return data
            
        except Exception:
            pass # Lỗi đọc file, bỏ qua để tạo mới

    # Tạo file mới với template
    data = {
        "key_mcp": generate_random_key(),
        "key_license": ""
    }
    with open(KEY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        
    return data

def verify_and_enforce_license():
    """Hàm chặn khởi động nếu License sai"""
    keys = load_or_create_keys()
    key_mcp = keys.get("key_mcp", "")
    user_license = keys.get("key_license", "")

    expected_license = generate_license_key(key_mcp)

    if user_license != expected_license:
        print("==================================================", file=sys.stderr)
        print("❌ FBO MCP SERVER - INVALID LICENSE", file=sys.stderr)
        print(f"🔑 Machine Key (key_mcp) của bạn: {key_mcp}", file=sys.stderr)
        print(f"Vui lòng gửi mã này cho Admin để lấy License Key.", file=sys.stderr)
        print(f"Sau đó dán License Key vào mục 'key_license' trong file:\n{KEY_FILE}", file=sys.stderr)
        print("==================================================", file=sys.stderr)
        sys.exit(1)
