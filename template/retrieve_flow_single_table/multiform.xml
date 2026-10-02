<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE dir [
  <!ENTITY Identity "{{identity}}MultiForm">
  <!ENTITY ParentController "{{parent_controller}}">
  <!ENTITY GridController "{{identity}}MultiGrid">
  <!ENTITY Tag "">
  <!ENTITY % FlowMultiVoucher SYSTEM "..\Include\FlowMultiVoucher.ent">
  %FlowMultiVoucher;
  <!ENTITY FlowMultiGeneralTable "{{src_master_table}}">
  <!ENTITY OtherCopyField "{{other_copy_field}}">
]>
<dir xmlns="urn:schemas-fast-com:data-dir">
  <title v="{{title_multiform_v}}" e="{{title_multiform_e}}"></title>
  <fields>
    &FlowMultiFormField;
  </fields>
  <views>
    &FlowMultiFormView;
  </views>
  <commands>
    <command event="Showing">
      <text>
        <![CDATA[
select 'show$]]>&Identity;<![CDATA[$(this);' as message
return
]]>
      </text>
    </command>

    <command event="Loading">
      <text>
        <![CDATA[
select 'active$]]>&Identity;<![CDATA[$(this);' as message
return
]]>
      </text>
    </command>
    <command event="Closing">
      <text>
        <![CDATA[
select 'close$]]>&Identity;<![CDATA[$(this);' as message
return
]]>
      </text>
    </command>
  </commands>
  <script>
    <text><![CDATA[
function show$]]>&Identity;<![CDATA[$(f) {
  var z = f.grid, h = z.get_element().parentForm, queryFilterString = '', c = String.fromCharCode(253);
  queryFilterString = h.getItemValue('{{dest_parent_unit_field}}');
  queryFilterString += c + z._filter$Fields[0];
  var d = h.getItemValue('{{dest_parent_date_field}}').z;
  queryFilterString += c + d.getFullYear() + ('0' + (d.getMonth() + 1)).slice(-2) + ('0' + d.getDate()).slice(-2);
  queryFilterString += c + z._stt_rec_ct;
  show$FlowMulti$Form(f, queryFilterString, ']]>&Identity;<![CDATA[DataGridPanel', ']]>&ParentController;<![CDATA[', ']]>&GridController;<![CDATA[', ']]>&OtherCopyField;<![CDATA[');
}
function active$]]>&Identity;<![CDATA[$(f) {
  f.add_onResponseComplete(on]]>&Identity;<![CDATA[Form$ResponseComplete);
  active$FlowMulti$Form(f);
}
function close$]]>&Identity;<![CDATA[$(f) {
  close$FlowMulti$Form(f);
  try { f.remove_onResponseComplete(on]]>&Identity;<![CDATA[Form$ResponseComplete); } catch (ex) {}
}
function on]]>&Identity;<![CDATA[Form$ResponseComplete(sender, e) {
  var f = e.object, context = e.type.Context, result = e.type.Result;
  switch (context) {
    case 'Checking':
      var g = getGrid$FlowMulti$(f);
      var c = String.fromCharCode(255),
        k1 = g._getColumnOrder('stt_rec') - 1,
        k2 = g._getColumnOrder('stt_rec0') - 1;
      f._$k = '';
      for (var i = 0; i < g._$k.length; i++) {
        f._$k += (f._$k != '' ? ',' : '') + g._$k[i][k1] + c + g._$k[i][k2];
      }
      if (f._$k == '') f.grid._formScript = 'show$FlowMulti$RetrieveGrid(this)';
      else {
        f._checked = false;
        f.request('GetOtherField', 'GetOtherField', [
          ['k', 'Infinite', f._$k]
        ]);
      }
      break;
    case 'GetOtherField':
      var g = getGrid$FlowMulti$(f), a = [];
      for (var i = 0; i < result.length; i++) {
        a[i] = g._$k[i].concat(result[i].slice(2));
      }
      on]]>&Identity;<![CDATA[$TransferData(f, g, a);
      break;
    default:
      break;
  }
}
function on]]>&Identity;<![CDATA[$TransferData(f, g, a) {
  var z = f.grid, w = z.get_element().parentForm,
    f1 = '{{f1}}', f2 = '{{f2}}';
  var first = true;
{{multiform_transfer_js}}
  z._focusWhenTabChanged();
  f.cancelDialog();
}
]]></text>
  </script>
  <response>
    <action id="GetOtherField">
      <text>
        &FlowMultiTagRowRequest;<![CDATA[
select top 0 tr.id, cast(b.nhieu_dvt as tinyint) as nhieu_dvt, a.he_so, rtrim(a.ma_vt) as ma_vt, rtrim(a.dvt) as dvt, a.ngay_ct, b.lo_yn
    ]]>&FlowMultiUserDefinedFieldsQuery;<![CDATA[
  into #d from #tagRow tr cross join {{src_detail_table}} a cross join dmvt b
insert into #d
select tr.id, b.nhieu_dvt, a.he_so, rtrim(a.ma_vt), rtrim(a.dvt), a.ngay_ct, b.lo_yn
    ]]>&FlowMultiUserDefinedFieldsQuery;<![CDATA[
  from #tagRow tr
    join {{src_detail_table}} a on tr.stt_rec = a.stt_rec and tr.stt_rec0 = a.stt_rec0
    left join dmvt b on a.ma_vt = b.ma_vt

select '' as array$, id, ]]>&OtherCopyField;<![CDATA[ from #d a  ]]>&FlowMultiOrderBy;<![CDATA[
return
]]>
      </text>
    </action>
  </response>
</dir>
