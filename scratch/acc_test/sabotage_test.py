"""Sabotage test: clone zcbc2700tt -> mutate -> check_legacy phải bắt đúng lỗi."""
import io, re, shutil, sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")

from acceptance_xml.entity_contents import get_entity_contents
from acceptance_xml.check_legacy import check_legacy
from fastbusiness_mcp.utils.file_utils import decode_bytes

SRC = Path(r"\\172.168.5.14\CustomerPro\FBI\CHUBB\SP2264\App_Data\Controllers\Filter\zcbc2700tt.xml")
WORK = Path(r"E:\PythonProject\mcp_fbo\scratch\acc_test\App_Data\Controllers\Filter")
ORIG = SRC.read_bytes()


def run_case(name, mutate):
    """mutate: hàm sửa text. Trả (name, diags)."""
    dst = WORK / f"zc_case_{name}.xml"
    text = ORIG.decode("utf-8-sig")
    text = mutate(text)
    dst.write_bytes(text.encode("utf-8-sig"))
    ents = get_entity_contents(str(dst))
    diags = check_legacy(str(dst), text, ents)
    return name, diags


def show(name, diags, expect_substr=None):
    hit = "?"
    if expect_substr:
        hit = "PASS" if any(expect_substr in d["message"] for d in diags) else "FAIL"
    print(f"--- {name} [{hit}] diags={len(diags)}")
    for d in diags:
        print(f"    L{d['line']:<4} {d['severity']:<8} {d['message'][:130]}")


# Case 1: numeric field thiếu <items style="Numeric">
def m_numeric(t):
    t = t.replace(
        '</field>\n\t</fields>',
        '</field>\n\t\t<field name="so_tien" type="Decimal"></field>\n\t</fields>',
        1,
    )
    # đưa so_tien lên view luôn để chỉ còn đúng 1 lỗi numeric
    t = t.replace('value="11000-: [ma_bp].Label, [ma_bp]"',
                  'value="11100-: [ma_bp].Label, [ma_bp], [so_tien]"')
    return t

show(*run_case("numeric", m_numeric), expect_substr="numeric")


# Case 2: field trên view chưa khai báo trong <fields>
def m_undeclared(t):
    return t.replace('value="11000-: [ma_bp].Label, [ma_bp]"',
                     'value="11100-: [ma_bp].Label, [ma_bp], [ma_kh_ma]"')

show(*run_case("undeclared", m_undeclared), expect_substr="chưa khai báo ở Fields")


# Case 3: thừa phần tử — pattern 3 cột '1' nhưng chỉ 2 field
def m_count(t):
    return t.replace('value="11000-: [ma_bp].Label, [ma_bp]"',
                     'value="11100-: [ma_bp].Label, [ma_bp]"')

show(*run_case("count", m_count), expect_substr="thừa")


# Case 4: pattern dài vượt master cols (master 6 cột)
def m_pattern_len(t):
    return t.replace('value="1101--: [tu_ngay].Description, [tu_ngay], [den_ngay]"',
                     'value="1101----: [tu_ngay].Description, [tu_ngay], [den_ngay]"')

show(*run_case("pattern_len", m_pattern_len), expect_substr="vượt số cột master")


# Case 5: field khai báo nhưng không xuống view (full mode)
def m_not_on_view(t):
    return t.replace(
        '</field>\n\t</fields>',
        '</field>\n\t\t<field name="unused_fld"><header v="x" e="x"/></field>\n\t</fields>',
        1,
    )

show(*run_case("not_on_view", m_not_on_view), expect_substr="xuống thẻ view")


# Case 6: anchor vượt số cột master
def m_anchor(t):
    return t.replace('<view id="Dir">', '<view id="Dir" anchor="9">')

show(*run_case("anchor", m_anchor), expect_substr='anchor="9"')


# Case 7: categoryIndex không khớp category nào
def m_catidx(t):
    return t.replace('<field name="ma_dvcs">',
                     '<field name="ma_dvcs" categoryIndex="5">', 1)

show(*run_case("catidx", m_catidx), expect_substr='categoryIndex="5"')


# Case 8: isPrimaryKey mà không có code="..."
def m_pk(t):
    return t.replace('<field name="ma_dvcs">',
                     '<field name="ma_dvcs" isPrimaryKey="true">', 1)

show(*run_case("pk", m_pk), expect_substr='code="..."')


# Case 9: xóa toàn bộ <fields> — view vẫn tham chiếu field
def m_nofields(t):
    return re.sub(r"<fields>[\s\S]*?</fields>", "<fields></fields>", t, count=1)

show(*run_case("nofields", m_nofields))
