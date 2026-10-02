<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE lookup [
  <!ENTITY FilterInitialize SYSTEM "..\Include\FilterInitialize.xml">
  <!ENTITY % Control.Filter SYSTEM "..\Include\Filter.Lookup.ent">
  %Control.Filter;
  <!ENTITY Controller "'{{identity}}Lookup'">
  <!ENTITY % CheckRelative SYSTEM "..\Include\CheckRelative.ent">
  %CheckRelative;
  <!ENTITY CheckRelativeParameter "'{{identity}}Lookup', 'Lookup', '{{parent_controller}}'">
  <!ENTITY CheckRelativeQuery "set @$primeFilter = '1 = 0'">
]>
<lookup table="{{src_master_table}}" code="so_ct" name="stt_rec" order="ngay_ct, so_ct, stt_rec" xmlns="urn:schemas-fast-com:data-lookup">
  <header v="{{title_lookup_v}}" e="{{title_lookup_e}}"></header>
  <fields>
    <field name="so_ct" align="right" allowFilter="true" allowSorting="&GridLookupAllowSorting;">
      <header v="Số đơn hàng" e="Order No."></header>
      <query>&InsertCommandFilter;</query>
    </field>
    <field name="stt_rec">
      <header v="" e=""></header>
    </field>
    <field name="ngay_ct" type="DateTime" dataFormatString="dd/MM/yyyy" allowFilter="true" allowSorting="&GridLookupAllowSorting;">
      <header v="Ngày đơn hàng" e="Order Date"></header>
      <query>&InsertCommandFilter;</query>
    </field>
    <field name="t_tien_nt2" type="Decimal" dataFormatString="### ### ### ### ### ###.00" allowFilter="true" allowSorting="&GridLookupAllowSorting;">
      <header v="Tiền hàng" e="Amount"></header>
      <query>&InsertCommandFilter;</query>
    </field>
    <field name="ma_nt" allowFilter="true" allowSorting="&GridLookupAllowSorting;">
      <header v="Mã nt" e="Currency Code"></header>
      <query>&InsertCommandFilter;</query>
    </field>
    <field name="status" allowFilter="true" allowSorting="&GridLookupAllowSorting;">
      <header v="Trạng thái" e="Status"></header>
      <query>&InsertCommandFilter;</query>
    </field>
    <field name="u0%l" allowFilter="true" allowSorting="&GridLookupAllowSorting;">
      <header v="Tên trạng thái" e="Status Name"></header>
      <query>&InsertCommandFilter;</query>
    </field>
  </fields>
  <queries>
    <query event="Declare">
      <text>&DeclareCommandFilter;</text>
    </query>
    <query event="Finding">
      <text>
        <![CDATA[
declare @unit varchar(128), @custID varchar(32)
select @unit = case when @ma_dvcs = '' then @@unit else @ma_dvcs end
select @custID = case when @ma_kh = '' then '' else '%#20$' + rtrim(@ma_kh) + '#%' end
]]>&FilterInitialize;<![CDATA[
]]>&CheckRelativeProcess;<![CDATA[
select @$primeJoin += ''

exec FastBusiness$App$Voucher$Finding '{{src_ma_ct}}', '{{src_inquiry_table}}', '{{src_master_table}}', '{{src_inquiry_table}}',
  'ngay_ct', '''''', '{0}', '',
  @@refresh, @@pageIndex, @@pageCount, @@lastPage, @@lastCount, @@firstItem, @@lastItem,
  @custID, '', 'stt_rec',
  '{{lookup_output_fields}}',
  '{{lookup_select_fields}}',
  '{{lookup_from_clause}}',
  'so_ct', 1, @@userID, 1,
  @ngay_ct1, @ngay_ct2, '', '', '{{finding_status_arg}}', '0', @unit, 0, 1,
  default, default, default, default, default, @$primeJoin, @$primeFilter,
  '{{lookup_detail_table}}', '{{lookup_detail_alias}}', '{{lookup_detail_remain_expr}}'
]]>
      </text>
    </query>
  </queries>
</lookup>
