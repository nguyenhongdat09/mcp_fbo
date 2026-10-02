<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE dir [
  <!ENTITY XMLFlowFilterViews SYSTEM "..\Include\XML\FlowFilterViews.txt">
  <!ENTITY XMLFlowFilterCommand SYSTEM "..\Include\XML\FlowFilterCommand.txt">
  <!ENTITY XMLFlowFilterCheck SYSTEM "..\Include\XML\FlowFilterCheck.txt">
  <!ENTITY ScriptFlowFilterCss SYSTEM "..\Include\Javascript\FlowFilterCss.txt">
  <!ENTITY ScriptFlowFilterFunction SYSTEM "..\Include\Javascript\FlowFilterFunction.txt">

  <!ENTITY Identity "{{identity}}">
  <!ENTITY c11 "{{title_filter_date_v}}">
  <!ENTITY c12 "{{title_filter_date_e}}">
  <!ENTITY c21 "{{title_filter_so_v}}">
  <!ENTITY c22 "{{title_filter_so_e}}">
  <!ENTITY ext "{{src_ext}}">

  <!ENTITY % FlowMultiVoucher SYSTEM "..\Include\FlowMultiVoucher.ent">
  %FlowMultiVoucher;
  <!ENTITY % CheckRelative SYSTEM "..\Include\CheckRelative.ent">
  %CheckRelative;
  <!ENTITY CheckRelativeParameter "'{{identity}}Filter', 'Filter', '{{parent_controller}}'">
  <!ENTITY CheckRelativeQuery "
    select 'so_ct' as field, @$none as message
    return">
]>
<dir table="m{{src_ext}}$000000" code="stt_rec" order="ngay_ct, so_ct" id="{{src_ma_ct}}" xmlns="urn:schemas-fast-com:data-dir">
  <title v="{{title_filter_v}}" e="{{title_filter_e}}"></title>

  <fields>
    <field name="ngay_ct1" type="DateTime" dataFormatString="@datetimeFormat" align="left" allowNulls="false" aliasName="fromDate" defaultValue="new Date()">
      <header v="&c11;" e="&c12;"></header>
    </field>
    <field name="so_ct" align="right" maxLength="-100" filterSource="voucherNumber" allowNulls="false">
      <header v="&c21;" e="&c22;"></header>
      <items style="AutoComplete" controller="&Identity;Lookup" reference="stt_rec_ct"/>
    </field>
    <field name="stt_rec_ct" readOnly="true" defaultValue="''" hidden="true">
      <header v="" e=""></header>
    </field>
    <field name="ngay_ct2" type="DateTime" dataFormatString="@datetimeFormat" align="left" readOnly="true" hidden="true">
      <header v="" e=""></header>
    </field>
    <field name="ma_dvcs" readOnly="true" defaultValue="''" hidden="true">
      <header v="" e=""></header>
    </field>
    <field name="ma_kh" readOnly="true" defaultValue="''" hidden="true">
      <header v="" e=""></header>
    </field>
  </fields>

  <views>
    <view id="Dir" height="88">
      <item value="120, 30, 70, 100, 230"/>
      <item value="1101: [ngay_ct1].Label, [ngay_ct1], [ngay_ct2]"/>
      <item value="110111: [so_ct].Label, [so_ct], [stt_rec_ct], [ma_dvcs], [ma_kh]"/>
    </view>
  </views>

  <commands>
    &XMLFlowFilterCommand;

    <command event="Inserting">
      <text>
        <![CDATA[
declare @fields nvarchar(512), @keyMaster nvarchar(1024), @keyFlow nvarchar(4000), @$none nvarchar(512)
select @keyMaster = '%#20$' + rtrim(@ma_kh) + '#%', @fields = '{{filter_retrieve_fields}}'
if @ma_kh = ''
  select @keyMaster = ''
select @keyFlow = '{{filter_key_flow}}', @$none = case when @@language = 'v' then N'{{filter_none_message_v}}' else N'{{filter_none_message_e}}' end
  ]]>&CheckRelativeProcess;<![CDATA[]]><!--&XMLFlowFilterCheck;-->
        <![CDATA[
IF @so_ct = ''
  goto NoneSoct
declare @vcID varchar(32), @vcNumber varchar(32), @vcFields nvarchar(512), @retrieveID char(13), @i int, @l int, @c smalldatetime, @d smalldatetime, @t varchar(128), @s nvarchar(4000), @unit varchar(128)
select @vcNumber = ltrim(rtrim(@so_ct)), @unit = @@unit
select @i = len(@vcNumber), @l = character_maximum_length from information_schema.columns where table_name = '@@table' and column_name = 'so_ct'
select @vcNumber = space(@l - @i) + @vcNumber, @c = @ngay_ct1

if @stt_rec_ct <> '' begin
  select @retrieveID = @stt_rec_ct
  goto Retrieve
end else begin
  select top 0 stt_rec into #t from i]]>&ext;<![CDATA[$000000
  while (month(@c) + year(@c)*12) <= (month(@ngay_ct2) + year(@ngay_ct2)*12) begin
    select @t = 'i]]>&ext;<![CDATA[$' + convert(char(6), @c, 112), @c = dateadd(month, 1, @c)
    if exists(select 1 from information_schema.tables where table_name = @t) begin
      set @s = 'insert into #t select top 1 stt_rec from ' + rtrim(@t)
      set @s = @s + char(13) + 'where ngay_ct between ''' + convert(char(8), @ngay_ct1, 112) + ''' and ''' + convert(char(8), @ngay_ct2, 112) + ''''
      set @s = @s + char(13) + 'and so_ct = ''' + replace(@vcNumber, '''', '''''') + ''' and ma_dvcs = ''' + replace(@unit, '''', '''''') + ''''
      if @keyFlow <> '' set @s = @s + ' and (' + @keyFlow + ')'
      if @keyMaster <> '' set @s = @s + char(13) + 'and m$ like N''' + replace(@keyMaster, '''', '''''') + ''''
       set @s = @s + char(13) + 'order by stt_rec'
      exec sp_executesql @s
    end
    if exists(select 1 from #t where (isnull(stt_rec, '') <> '')) begin
	    select @retrieveID = stt_rec from #t
	    drop table #t
      goto Retrieve
    end
  end
  drop table #t
  select 'so_ct' as field, @$none as message
  return
end

Retrieve:
select @vcID = @retrieveID, @d = ngay_ct from c]]>&ext;<![CDATA[$000000 where stt_rec = @retrieveID
select cast('' as nvarchar(512)) as fields into #r from m]]>&ext;<![CDATA[$000000
select @t = 'm]]>&ext;<![CDATA[$'+ convert(varchar(6), (select ngay_ct from c]]>&ext;<![CDATA[$000000 where stt_rec = @retrieveID), 112)
if exists(select 1 from information_schema.tables where table_name = @t) begin
  select @s = 'insert into #r select ' + @fields + ' as fields from ' + rtrim(@t) + ' where stt_rec = ''' + replace(@retrieveID, '''', '') + ''''
  exec sp_executesql @s
end
select @vcFields = fields from #r
drop table #r
NoneSoct:
select @ngay_ct1 = isnull(@d, @ngay_ct1)
select @vcID = isnull(@vcID, @stt_rec_ct)
select '' as field, '' as message, 'on$]]>&Identity;<![CDATA[Filter$Retrieve$QueryComplete(this, '''', '''', '''', '''', '']]>&Identity;<![CDATA[MultiForm'', [''' + convert(char(8), @ngay_ct1, 112) + '''], '''+@vcID+''');' as script
]]>
      </text>
    </command>

    <command event="Checking">
      <text>
        <![CDATA[
var f = this;
]]>
      </text>
    </command>
  </commands>

  <script>
    <text>
      &ScriptFlowFilterFunction;<![CDATA[
function init$]]>&Identity;<![CDATA[Filter$(f) {
  f.getItem('so_ct')._idle = 9;
}
function active$]]>&Identity;<![CDATA[Filter$(f) {
  f._looking = f.getItem('so_ct')._looking;
  f.add_onResponseComplete(on$]]>&Identity;<![CDATA[Filter$ResponseComplete);
  f._tabContainer.add_activeTabChanged(on$]]>&Identity;<![CDATA[Filter$ActiveTabChanged);
  f._tabContainer._loaded = true;
  var g = f.grid, w = g.get_element().parentForm;
  var d = w.getItemValue('{{dest_parent_date_field}}'), u = w.getItemValue('{{dest_parent_unit_field}}'), c = w.getItemValue('ma_kh');
  f.setItemValues('ngay_ct2, ma_kh, ma_dvcs', [d, c, u]);
}
function close$]]>&Identity;<![CDATA[Filter$(f) {
  try {
    f.remove_onResponseComplete(on$]]>&Identity;<![CDATA[Filter$ResponseComplete);
  } catch (ex) {}
  try {
    f._tabContainer.remove_activeTabChanged(on$]]>&Identity;<![CDATA[Filter$ActiveTabChanged);
  } catch (ex) {}
}
function on$]]>&Identity;<![CDATA[Filter$ResponseComplete(sender, e) {
  var f = e.object, context = e.type.Context, result = e.type.Result;
  switch (context) {
    case 'Checking':
      break;
    default:
      break;
  }
}
function on$]]>&Identity;<![CDATA[Filter$ActiveTabChanged(sender, e) {
  var f = sender.get_element().parentForm;
}
function on$]]>&Identity;<![CDATA[Filter$Retrieve$QueryComplete(f, c, d, k, e, h, v, r) {
  var g = f.grid;
  if (c != '') {
    g._voucher$Retrieve$Date = d;
    g._voucher$Retrieve$Key = k;
    g._voucher$Retrieve$Ext = e;
  } else {
    g._filter$Fields = v;
    g._stt_rec_ct = r;
  }
  set$]]>&Identity;<![CDATA[Filter$FormScript(g, h);
}
function set$]]>&Identity;<![CDATA[Filter$FormScript(g, h) {
  var a = [
    'show$]]>&Identity;<![CDATA[Filter$QueryComplete(this, \'' + (h ? h : '') + '\')'
  ];
  g._formScript = a.join(';');
}
function show$]]>&Identity;<![CDATA[Filter$QueryComplete(g, h) {
  if (h != '') {
    g.showForm(h);
  } else {
    g.showForm(']]>&Identity;<![CDATA[MultiForm');
  }
}
]]>
    </text>
  </script>

  &ScriptFlowFilterCss;
</dir>
