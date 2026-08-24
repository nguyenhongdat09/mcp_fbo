"""Probe dirExtender._fields — tìm Lookup/AutoComplete và field bắt buộc."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"
MR = "ctl00_FastBusiness_MainReport"

PROBE_FIELDS_JS = """
() => {
  var f = $find('ctl00_FastBusiness_MainReport_dirExtender');
  if (!f || !f._fields) return { error: 'no dirExtender fields' };

  function inspectField(field) {
    var keys = Object.keys(field);
    var out = {
      Name: field.Name,
      HeaderText: field.HeaderText || field.Label || '',
      Type: field.Type,
      AllowNulls: field.AllowNulls,
      ReadOnly: field.ReadOnly,
      Hidden: field.Hidden,
      Visible: field.Visible,
    };
    // Thu thập mọi property có thể chỉ lookup/autocomplete
    ['Style', 'style', 'ControlType', 'controlType', 'ItemStyle', 'itemStyle',
     'Controller', 'controller', 'Reference', 'reference', 'Key', 'key',
     'Information', 'information', 'Check', 'check', 'Lookup', 'lookup',
     'AutoComplete', 'autoComplete', 'IsLookup', 'isLookup', 'FieldType', 'fieldType',
     'DataFormatString', 'AliasName'].forEach(function(k) {
      if (field[k] !== undefined && field[k] !== null && field[k] !== '') out[k] = field[k];
    });
    // Heuristic label
    var styleStr = JSON.stringify(out).toLowerCase();
    if (styleStr.indexOf('lookup') >= 0) out._hint = 'lookup';
    else if (styleStr.indexOf('autocomplete') >= 0) out._hint = 'autocomplete';
    else if (field.Type === 'String' && !field.AllowNulls && field.Name !== 'ma_vt' && field.Name !== 'ten_vt') out._hint = 'maybe_lookup';
    return out;
  }

  var required = [];
  var lookup_like = [];
  f._fields.forEach(function(field) {
    var info = inspectField(field);
    if (field.AllowNulls === false) required.push(info);
    var s = JSON.stringify(info).toLowerCase();
    if (s.indexOf('lookup') >= 0 || s.indexOf('autocomplete') >= 0 || s.indexOf('controller') >= 0
        || ['dvt','loai_vt','tk_vt','tk_gv','tk_dt','ma_thue','nh_vt1'].indexOf(field.Name) >= 0) {
      lookup_like.push(info);
    }
  });

  return {
    total: f._fields.length,
    required_count: required.length,
    required: required.slice(0, 20),
    lookup_like: lookup_like,
    sample_field_all_keys: f._fields[0] ? Object.keys(f._fields[0]) : []
  };
}
"""

def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance(); s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
    p.goto(URL, timeout=90000)
    time.sleep(8)
    p.evaluate(f"""() => {{ $find('{MR}').executeCommand({{ commandName: 'New', commandArgument: '0' }}); }}""")
    time.sleep(3)
    result = p.evaluate(PROBE_FIELDS_JS)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    p.close()

if __name__ == "__main__":
    main()
