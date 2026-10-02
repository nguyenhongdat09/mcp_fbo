<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE grid [
  <!ENTITY % GridInitialize SYSTEM "..\Include\Grid.ent">
  %GridInitialize;
  <!ENTITY FilterInitialize SYSTEM "..\Include\FilterInitialize.xml">
  <!ENTITY FilterQuery SYSTEM "..\Include\FilterQuery.xml">
  <!ENTITY % Control.Filter SYSTEM "..\Include\Filter.Voucher.ent">
  %Control.Filter;
  <!ENTITY Controller "'{{identity}}FlowMultiGrid'">
  <!ENTITY Identity "{{identity}}MultiGrid">
  <!ENTITY Table "{{src_ext}}">
  <!ENTITY Tag "2">
  <!ENTITY % FlowMultiVoucher SYSTEM "..\Include\FlowMultiVoucher.ent">
  %FlowMultiVoucher;
  <!ENTITY % CheckRelative SYSTEM "..\Include\CheckRelative.ent">
  %CheckRelative;
  <!ENTITY CheckRelativeParameter "'{{identity}}MultiGrid', 'Grid', '{{parent_controller}}'">
  <!ENTITY CheckRelativeQuery "
  select top 0 @@fieldExternal from d{{src_ext}}$000000 a, m{{src_ext}}$000000 m, dmvt b
  return">
]>
<grid order="ngay_ct, so_ct, stt_rec, line_nbr" type="Inquiry" xmlns="urn:schemas-fast-com:data-grid">
  <title v="{{title_multigrid_v}}" e="{{title_multigrid_e}}"></title>
  <subTitle v="{{subtitle_multigrid_v}}" e="{{subtitle_multigrid_e}}"></subTitle>

  <fields>
    <field name="ngay_ct" type="DateTime" dataFormatString="dd/MM/yyyy" width="100" allowFilter="&GridQueryAllowFilter;" allowSorting="&GridQueryAllowSorting;" aliasName="m" readOnly="true">
      <header v="Ngày ct" e="Voucher Date"></header>
      <query>&InsertCommandFilter;</query>
    </field>
    <field name="so_ct" width="100" allowFilter="&GridQueryAllowFilter;" allowSorting="&GridQueryAllowSorting;" aliasName="m" readOnly="true">
      <header v="Số ct" e="Voucher Number"></header>
      <items style="HyperLink" action="show$FlowMulti$RetrieveGrid(this)"/>
      <query>&InsertCommandFilter;</query>
    </field>
    <field name="ma_vt" width="100" allowFilter="&GridQueryAllowFilter;" allowSorting="&GridQueryAllowSorting;" aliasName="a" readOnly="true">
      <header v="Mã hàng" e="Item Code"></header>
      <query>&InsertCommandFilter;</query>
    </field>
    <field name="ten_vt%l" width="200" allowFilter="&GridQueryAllowFilter;" allowSorting="&GridQueryAllowSorting;" aliasName="b" readOnly="true">
      <header v="Tên hàng" e="Item Name"></header>
      <query>&InsertCommandFilter;</query>
    </field>
    <field name="chon" type="Boolean" external="true" width="40" align="center" allowFilter="false" allowSorting="false" defaultValue="false">
      <header v="&FlowMultiGridTagHeader;" e="&FlowMultiGridTagHeader;"></header>
      <items style="CheckBox"/>
      <clientScript><![CDATA[onClick$FlowMulti$GridQuery$]]>&Identity;<![CDATA[Calculate(this);]]></clientScript>
    </field>
    <field name="so_luong0" type="Decimal" dataFormatString="&GridNumberQuantity;" external="true" width="100" clientDefault="0">
      <header v="Số lượng" e="Quantity"></header>
      <clientScript><![CDATA[onChange$FlowMulti$GridQuery$]]>&Identity;<![CDATA[InvoiceQuantity(this);]]></clientScript>
    </field>
    <field name="so_luong" type="Decimal" dataFormatString="&GridNumberQuantity;" width="100" allowFilter="&GridQueryAllowFilter;" allowSorting="&GridQueryAllowSorting;" aliasName="a" readOnly="true">
      <header v="Số lượng đơn hàng" e="Order Quantity"></header>
      <query>&InsertCommandFilter;</query>
    </field>
    <field name="{{src_taken_col}}" type="Decimal" dataFormatString="&GridNumberQuantity;" width="100" allowFilter="&GridQueryAllowFilter;" allowSorting="&GridQueryAllowSorting;" aliasName="a" readOnly="true">
      <header v="{{src_taken_header_v}}" e="{{src_taken_header_e}}"></header>
      <query>&InsertCommandFilter;</query>
    </field>
    <field name="dvt" width="50" allowFilter="&GridQueryAllowFilter;" allowSorting="&GridQueryAllowSorting;" aliasName="a" readOnly="true">
      <header v="Đvt" e="UOM"></header>
      <items style="AutoComplete" controller="UOM" reference="dvt" key="status = '1'" check="1 = 1" information="dvt#"/>
      <handle key="[nhieu_dvt] = 1"/>
      <query>&InsertCommandFilter;</query>
    </field>{{multigrid_ma_nt_field}}

    <field name="stt_rec" width="0" aliasName="m" hidden="true">
      <header v="" e=""></header>
    </field>
    <field name="stt_rec0" width="0" aliasName="a" hidden="true">
      <header v="" e=""></header>
    </field>
    <field name="line_nbr" type="Int32" width="0" aliasName="a" hidden="true">
      <header v="" e=""></header>
    </field>
    <field name="ma_ct" width="0" aliasName="m" hidden="true">
      <header v="" e=""></header>
    </field>
    <field name="ma_kh" width="0" aliasName="m" hidden="true">
      <header v="" e=""></header>
    </field>
  </fields>

  <views>
    <view id="Grid">
      <field name="ngay_ct"/>
      <field name="so_ct"/>
      <field name="ma_vt"/>
      <field name="ten_vt%l"/>
      <field name="chon"/>
      <field name="so_luong0"/>
      <field name="so_luong"/>
      <field name="{{src_taken_col}}"/>
      <field name="dvt"/>{{multigrid_ma_nt_view}}
      <field name="stt_rec"/>
      <field name="stt_rec0"/>
      <field name="line_nbr"/>
      <field name="ma_ct"/>
      <field name="ma_kh"/>
    </view>
  </views>

  <commands>
    &FlowMultiGridCommand;
  </commands>

  <queries>
    <query event="Declare">
      <text>&DeclareCommandFilter;</text>
    </query>
    <query event="Finding">
      <text>
        <![CDATA[
]]>&CheckRelativeProcess;<![CDATA[
declare @fields nvarchar(512), @keyMaster nvarchar(1024), @c char(1), @d smalldatetime, @idnumber varchar(32)
select @c = char(253), @keyMaster = ''
select @ma_dvcs = replace(rtrim(left(@queryString, charindex(@c, @queryString) - 1)), '''', '')
select @queryString = substring(@queryString, charindex(@c, @queryString) + 1, len(@queryString))
select @ngay_ct1 = left(@queryString, charindex(@c, @queryString) - 1)
select @queryString = substring(@queryString, charindex(@c, @queryString) + 1, len(@queryString))
select @ngay_ct2 = left(@queryString, charindex(@c, @queryString) - 1)
select @idnumber = substring(@queryString, charindex(@c, @queryString) + 1, len(@queryString))

if @ma_kh <> '' select @keyMaster = '%#20$' + rtrim(@ma_kh) + '#%'

select @queryFormClause = 'm]]>&Table;<![CDATA[$%Partition m with(nolock) join d]]>&Table;<![CDATA[$%Partition a with(nolock) on m.stt_rec = a.stt_rec left join dmvt b with(nolock) on a.ma_vt = b.ma_vt'
select @queryWhereClause = 'm.ma_dvcs = ''' + replace(rtrim(@ma_dvcs), '''', '''''') + '''{{multigrid_status_clause}} and a.{{src_taken_col}} < a.{{src_qty_col}}{{multigrid_filter_extra_sql}}'
if @keyMaster <> '' select @queryWhereClause = @queryWhereClause + ' and m$ like N''' + replace(@keyMaster, '''', '''''') + ''''
if @idnumber <> '' select @queryWhereClause = @queryWhereClause + ' and m.stt_rec = ''' + replace(@idnumber, '''', '''''') + ''''
]]>&FilterInitialize;&FilterQuery;<![CDATA[
]]>&FlowMultiGridFinding;<![CDATA[
return
]]>
      </text>
    </query>
  </queries>

  <script>
    <text>
      &FlowMultiGridScript;<![CDATA[
function init$FlowMulti$GridQuery$]]>&Identity;<![CDATA[(g) {
  g._alterTitle = [null, [['%d1', g._filter$Fields[0], true], ['%d2', g._filter$Fields[1], true]]];
}
function load$FlowMulti$GridQuery$]]>&Identity;<![CDATA[(g) {
  g.add_onResponseComplete(on$FlowMulti$GridQuery$]]>&Identity;<![CDATA[$ResponseComplete);
  g.add_onExecuteCommand(on$FlowMulti$GridQuery$ExecuteCommand);
  if (!g._$t) {
    g._$t = [];
    g._$k = [];
    g._$f = [];
    g._$i = [];
    g._$s = [];
  }
}
function dispose$FlowMulti$GridQuery$]]>&Identity;<![CDATA[(g) {
  try {
    g.remove_onResponseComplete(on$FlowMulti$GridQuery$]]>&Identity;<![CDATA[$ResponseComplete);
  } catch (ex) {}
  try {
    g.remove_onExecuteCommand(on$FlowMulti$GridQuery$ExecuteCommand);
  } catch (ex) {}
}
function on$FlowMulti$GridQuery$ExecuteCommand(sender, e) {
  var action = e.type.Action;
  switch (action) {
    case 'Save':
      var g = sender, f = g.get_element().parentForm;
      var c = String.fromCharCode(255), k1 = g._getColumnOrder('stt_rec') - 1, k2 = g._getColumnOrder('stt_rec0') - 1;
      f._$k = '';
      for (var i = 0; i < g._$k.length; i++) {
        f._$k += (f._$k != '' ? ',' : '') + g._$k[i][k1] + c + g._$k[i][k2];
      }
      if (f._$k == '') f.grid._formScript = 'show$FlowMulti$RetrieveGrid(this)';
      break;
    default:
      break;
  }
}
function scatter$FlowMulti$GridQuery$]]>&Identity;<![CDATA[(g) {
  for (var i = 0; i < g._$k.length; i++) {
    var r = g._findRow(['stt_rec', 'stt_rec0'], [g._$k[i][0], g._$k[i][1]]);
    if (r > 0) {
      g._setItemValue(r, g._getColumnOrder('chon'), true);
      g._setItemValue(r, g._getColumnOrder('so_luong0'), g._$t[i]);
    }
  }
}
function on$FlowMulti$GridQuery$]]>&Identity;<![CDATA[$ResponseComplete(sender, e) {
  var g = e.object, context = e.type.Context, result = e.type.Result;
  switch (context) {
    case 'Gather':
      scatter$FlowMulti$GridQuery$]]>&Identity;<![CDATA[(g);
      break;
    default:
      break;
  }
}
function toggle$FlowMulti$GridQuery$]]>&Identity;<![CDATA[(g, o) {
  for (var i = 1; i <= g._rowCount; i++) {
    var r = i;
    g._setItemValue(r, g._getColumnOrder('chon'), o.checked);
    g._setItemValue(r, g._getColumnOrder('so_luong0'), o.checked ? g._getItemValue(r, g._getColumnOrder('so_luong')) - g._getItemValue(r, g._getColumnOrder('{{src_taken_col}}')) : 0);
    onClick$FlowMulti$GridQuery$]]>&Identity;<![CDATA[Calculate(g._getItem(r, g._getColumnOrder('chon')).control);
  }
}
function onClick$FlowMulti$GridQuery$]]>&Identity;<![CDATA[Calculate(o) {
  var g = o.parentSysGrid, r = o.parentNode.parentNode.rowIndex;
  var k = g._getItemValue(r, g._getColumnOrder('stt_rec')), k0 = g._getItemValue(r, g._getColumnOrder('stt_rec0'));
  var v = g._getItemValue(r, g._getColumnOrder('so_luong0'));
  if (o.checked) {
    if (v == 0) {
      v = g._getItemValue(r, g._getColumnOrder('so_luong')) - g._getItemValue(r, g._getColumnOrder('{{src_taken_col}}'));
      g._setItemValue(r, g._getColumnOrder('so_luong0'), v);
    }
    addTagRow$FlowMulti$(g, k, k0, v);
  } else {
    g._setItemValue(r, g._getColumnOrder('so_luong0'), 0);
    removeTagRow$FlowMulti$(g, k, k0);
  }
}
function onChange$FlowMulti$GridQuery$]]>&Identity;<![CDATA[InvoiceQuantity(o) {
  var g = o.parentSysGrid, r = o.parentNode.parentNode.rowIndex;
  var k = g._getItemValue(r, g._getColumnOrder('stt_rec')), k0 = g._getItemValue(r, g._getColumnOrder('stt_rec0'));
  var v = g._getItemValue(r, g._getColumnOrder('so_luong0')), o0 = g._getItemValue(r, g._getColumnOrder('so_luong')), o1 = g._getItemValue(r, g._getColumnOrder('{{src_taken_col}}'));
  if (v < 0) {
    g._setItemValue(r, g._getColumnOrder('so_luong0'), 0);
    g._setItemValue(r, g._getColumnOrder('chon'), false);
    removeTagRow$FlowMulti$(g, k, k0);
  } else {
    if (v > (o0 - o1)) {
      v = o0 - o1;
      g._setItemValue(r, g._getColumnOrder('so_luong0'), v);
    }
    g._setItemValue(r, g._getColumnOrder('chon'), true);
    addTagRow$FlowMulti$(g, k, k0, v);
  }
}
]]>
    </text>
  </script>

  &FlowMultiGridToolbar;
</grid>
