/* ============================================================
   CHỨNG TỪ {{x}} — {{title_v}}  (variant: CÓ duyệt, KHÔNG ngoại tệ)
   Khối 1: SYS (chạy trên db hệ thống)
   Khối 2: APP (chạy trên db dữ liệu)

   !!! QUAN TRỌNG — schema khác nhau giữa phiên bản FBO:
   - Trước khi F5: query_database query_type=0 từng bảng đích lấy
     danh sách cột THẬT; bỏ cột db đích không có khỏi mọi INSERT.
   - INSERT luôn liệt kê cột tường minh — KHÔNG insert into t values(…).
   - Tốt nhất: lấy row mẫu từ chứng từ CÓ DUYỆT gần nhất trong CÙNG
     project (clone_data / query_database theo ma_ct mẫu) rồi đổi mã.
   ============================================================ */
USE [{{DB_SYS}}]
GO

/* ---------- MENU ---------- */
-- TODO(menu): đổi {{menu_dir}}/{{menu_list}}/{{menu_parent}} + caption.
-- Cấu trúc cột wcommand khác nhau giữa phiên bản — check schema trước.
if not exists(select 1 from wcommand where id = '{{menu_dir}}')
  insert into wcommand(id, parent, caption, caption2, command /*TODO(cột còn lại)*/)
  values('{{menu_dir}}', '{{menu_parent}}', N'{{title_v}}', N'{{title_e}}', 'zc{{xt}}d.aspx' /*TODO*/)

if not exists(select 1 from wcommand where id = '{{menu_list}}')
  insert into wcommand(id, parent, caption, caption2, command /*TODO*/)
  values('{{menu_list}}', '{{menu_parent}}', N'{{title_v}}', N'{{title_e}}', 'zcd{{xt}}d.aspx' /*TODO*/)

/* ---------- Đăng ký voucher (SYS) ----------
   Checklist bảng SYS theo tool clone CT: voucherinfo, sysvouchertype,
   freecolumns, freelistcolumns, freefunctions, kbtruongngay,
   arrangementcolumns, functionfilters, columns, sysfields, sysfilterdeclares.
   Bản cũ có thể THIẾU vài bảng → check trước:
   -- select name from sysobjects where xtype='U' and name in
   --  ('voucherinfo','sysvouchertype','freecolumns','freelistcolumns',
   --   'freefunctions','kbtruongngay','arrangementcolumns','functionfilters',
   --   'columns','sysfields','sysfilterdeclares') order by name
   Mỗi insert bọc IF OBJECT_ID — thiếu bảng thì block tự bỏ qua.
   Mẫu mạnh nhất: SELECT row của chứng từ mẫu {{mau_ctrl}} rồi INSERT đổi
   ma_ct/controller/bảng. */
if OBJECT_ID('voucherinfo','U') is not null
  insert into voucherinfo(ma_ct, controller /*TODO(cột theo schema mẫu)*/)
  select '{{x}}', '{{x}}Tran' /*TODO*/ where not exists(select 1 from voucherinfo where ma_ct = '{{x}}')

if OBJECT_ID('sysvouchertype','U') is not null
  insert into sysvouchertype(/*TODO*/) select '{{x}}Field', '{{x}}View' /*TODO*/
  where not exists(select 1 from sysvouchertype where /*TODO*/)

/* Cột/hàm tự do — clone rows controller='{mau}%' đổi tên sang {X}* */
if OBJECT_ID('freecolumns','U') is not null
  insert into freecolumns(/*TODO*/) select /*TODO*/ from freecolumns where controller like '{{mau_ctrl}}%'
if OBJECT_ID('freelistcolumns','U') is not null
  insert into freelistcolumns(/*TODO*/) select /*TODO*/ from freelistcolumns where controller like '{{mau_ctrl}}%'
if OBJECT_ID('freefunctions','U') is not null
  insert into freefunctions(/*TODO*/) select /*TODO*/ from freefunctions where controller like '{{mau_ctrl}}%'
if OBJECT_ID('kbtruongngay','U') is not null
  insert into kbtruongngay(/*TODO*/) select /*TODO*/ from kbtruongngay where controller like '{{mau_ctrl}}%'
if OBJECT_ID('arrangementcolumns','U') is not null
  insert into arrangementcolumns(/*TODO*/) select /*TODO*/ from arrangementcolumns where controller like '{{mau_ctrl}}%'
if OBJECT_ID('functionfilters','U') is not null
  insert into functionfilters(/*TODO*/) select /*TODO*/ from functionfilters where controller like '{{mau_ctrl}}%'
if OBJECT_ID('columns','U') is not null
  insert into columns(/*TODO*/) select /*TODO*/ from columns where controller like '{{mau_ctrl}}%'
if OBJECT_ID('sysfields','U') is not null
  insert into sysfields(/*TODO*/) select /*TODO*/ from sysfields where controller like '{{mau_ctrl}}%'
/* ---------- Filter declares (list + filter + approval) ---------- */
-- bảng phải m{{xt}}$%Partition của CT MỚI — KHÔNG để của mẫu
if OBJECT_ID('sysfilterdeclares','U') is not null
begin
  insert into sysfilterdeclares(/*TODO*/) values('{{x}}Tran', 'm{{xt}}$%Partition', /*TODO*/)
  insert into sysfilterdeclares(/*TODO*/) values('{{x}}Approval', 'm{{xt}}$%Partition', /*TODO*/)
end

/* ---------- Phân quyền duyệt (CHỈ nếu project có bảng này) ----------
if OBJECT_ID('sysrelativeright','U') is not null
  insert into sysrelativeright(/*TODO*/) select /*TODO*/ from sysrelativeright
    where controller = '{{mau_apv_ctrl}}'   -- đổi controller + kiểu duyệt
*/
GO

USE [{{DB_APP}}]
GO

/* ---------- Đăng ký chứng từ (APP) ----------
   Checklist bảng APP theo tool clone CT: dmct, dmct0, dmct4, dmct5, dmct9,
   dmxlct, dmttct, dmmagd, dmloaict, dmcttransfer, (dmctduyet nếu duyệt),
   sysgendata, systransfer. Check trước:
   -- select name from sysobjects where xtype='U' and name in
   --  ('dmct','dmct0','dmct4','dmct5','dmct9','dmxlct','dmttct','dmmagd',
   --   'dmloaict','dmcttransfer','dmctduyet','sysgendata','systransfer',
   --   'fsdConfigTable') order by name */
insert into dmct(ma_ct, ten_ct, ten_ct2 /*TODO*/)
  select '{{x}}', N'{{title_v}}', N'{{title_e}}' /*TODO*/ where not exists(select 1 from dmct where ma_ct = '{{x}}')
if OBJECT_ID('dmct0','U') is not null insert into dmct0(/*TODO*/) /*TODO theo dmct0 mẫu*/
if OBJECT_ID('dmct4','U') is not null insert into dmct4(/*TODO*/) /*TODO*/
if OBJECT_ID('dmct5','U') is not null insert into dmct5(/*TODO*/) /*TODO — bản cũ có thể không có*/
if OBJECT_ID('dmct9','U') is not null insert into dmct9(/*TODO*/) /*TODO*/
if OBJECT_ID('dmxlct','U') is not null insert into dmxlct(/*TODO*/) /*TODO xử lý chứng từ*/

/* ---------- Trạng thái (CÓ duyệt) ---------- */
insert into dmttct(ma_ct, ma_tt, ten_tt, ten_tt2 /*TODO*/)
  select '{{x}}', '0', N'0. Lập chứng từ', '0. No Action' /*TODO*/
insert into dmttct(ma_ct, ma_tt, ten_tt, ten_tt2 /*TODO*/)
  select '{{x}}', '1', N'1. Chờ duyệt', '1. Open' /*TODO*/
insert into dmttct(ma_ct, ma_tt, ten_tt, ten_tt2 /*TODO*/)
  select '{{x}}', '2', N'2. Đã duyệt', '2. Approved' /*TODO*/
insert into dmttct(ma_ct, ma_tt, ten_tt, ten_tt2 /*TODO*/)
  select '{{x}}', '5', N'5. Đóng', '5. Close' /*TODO*/
insert into dmttct(ma_ct, ma_tt, ten_tt, ten_tt2 /*TODO*/)
  select '{{x}}', '9', N'9. Đang duyệt', '9. Pending' /*TODO*/
-- TODO(status 3/4): thêm trạng thái nghiệp vụ nếu cần + sửa status items trong Dir

/* ---------- Mã giao dịch ---------- */
if OBJECT_ID('dmmagd','U') is not null
  insert into dmmagd(ma_ct, ma_gd, ten_gd, ten_gd2, loai_ct /*TODO*/)
  select '{{x}}', '1', N'{{ten_gd1_v}}', N'{{ten_gd1_e}}', '' /*TODO*/

if OBJECT_ID('dmloaict','U') is not null insert into dmloaict(/*TODO*/) /*TODO*/
if OBJECT_ID('dmcttransfer','U') is not null insert into dmcttransfer(/*TODO*/) /*TODO*/

/* ---------- DUYỆT — kiểu duyệt {{apv_type}} phải MỚI (015xx), KHÔNG trùng mẫu ----------
   Bộ bảng duyệt theo PHÂN HỆ: GN chung = gn* (chứng từ phổ biến),
   PU mua hàng = không prefix, SO bán hàng = so*. Template này dùng GN:
   - gndmloaiduyet : loại duyệt 015xx (tên kiểu, notify_group)
   - gndmttcttg    : trạng thái từng cấp trong kiểu duyệt
   - gndmquyenct   : quyền theo cấp duyệt
   - gndmkieuduyet : khai kiểu duyệt (flag chiều nếu có)
   - gnctkieuduyet : chi tiết giá trị kiểu duyệt (theo APVCheckCategory)
   - dmctduyet     : đăng ký CT này dùng kiểu duyệt nào (KHÔNG prefix)
   Xem skill fbo-approval-category-dimension nếu cần thêm chiều
   xác định kiểu duyệt (yn trên gndmloaiduyet + gnctkieuduyet). */
-- dmctduyet: chứng từ này dùng kiểu duyệt nào (bảng đăng ký chung, không prefix)
if OBJECT_ID('dmctduyet','U') is not null
  insert into dmctduyet(/*TODO*/) select '{{x}}', '{{apv_type}}' /*TODO theo schema*/
-- clone row từ kiểu duyệt mẫu (01511...) đổi mã + tên:
-- insert into gndmloaiduyet(loai_duyet, ten_duyet, ten_duyet2, notify_group /*TODO*/)
--   values('{{apv_type}}', N'{{title_v}} chờ duyệt', N'{{title_e}}' /*TODO*/)
-- insert into gndmttcttg(/*TODO*/)    /*TODO — trạng thái cấp, clone từ kiểu mẫu*/
-- insert into gndmquyenct(/*TODO*/)   /*TODO — quyền theo cấp, clone từ kiểu mẫu*/
-- insert into gndmkieuduyet(/*TODO*/) values('{{apv_type}}', N'{{title_v}}' /*TODO*/)
-- insert into gnctkieuduyet(/*TODO*/) /*TODO — giá trị theo APVCheckCategory*/

/* ---------- sysgendata + systransfer ----------
   sysgendata: đăng ký cột gen cho TỪNG bảng vật lý — clone rows của mẫu
   theo basetable (d{mau}$000000, i{mau}$000000, + detail phụ vd
   d{mau}km$/d{mau}ndt$/d{mau}ser$ nếu mẫu có), đổi sang d{{xt}}$000000… */
if OBJECT_ID('sysgendata','U') is not null
begin
  insert into sysgendata(basetable /*TODO*/) select /*TODO*/ from sysgendata where basetable like 'd{{mau_tbl}}$%'  /*TODO đổi d→d{{xt}}*/
  insert into sysgendata(basetable /*TODO*/) select /*TODO*/ from sysgendata where basetable like 'i{{mau_tbl}}$%'  /*TODO đổi i→i{{xt}}*/
end
-- systransfer: FlowMulti lấy dữ liệu — file = master partition của CT mới
if OBJECT_ID('systransfer','U') is not null
  insert into systransfer(file /*TODO*/) select /*TODO*/ from systransfer where file = 'm{{mau_tbl}}$%Partition'  /*TODO đổi m→m{{xt}}*/

/* ---------- Config nhóm grid (nếu grid dùng fsdConfigTable) ----------
insert into fsdConfigTable(group_name /*TODO*/) values('{{x}}Detail' /*TODO*/)
*/

/* ---------- Bảng dữ liệu ----------
   CREATE TABLE: clone schema bảng mẫu (query_database type=0), đổi tên
   + thêm cột nghiệp vụ. KHÔNG có cặp _nt (variant không ngoại tệ).
   m{{xt}}$ cần cột duyệt: kieu_duyet, u_status (+ ly_do…) — clone m{mau}$
   của chứng từ CÓ DUYỆT để lấy đủ cột APV. */
create table m{{xt}}$ (
  stt_rec varchar(13) not null,
  ma_ct char(3) not null,
  so_ct char(12) not null,
  ngay_lct smalldatetime null,
  ngay_ct smalldatetime null,
  ma_dvcs char(10) null,
  ma_nt char(10) null,          -- variant không NT: luôn ''
  ty_gia numeric(19,4) null,    -- variant không NT: luôn 1
  status char(1) null,
  kieu_duyet varchar(32) null,  -- BẮT BUỘC: kiểu duyệt của phiếu
  u_status char(10) null,       -- BẮT BUỘC: người duyệt hiện tại
  ly_do nvarchar(256) null,     -- lý do (hủy/bỏ duyệt…) — nếu mẫu có
  ma_gd char(10) null,
  loai_ct char(10) null,
  ma_kh char(20) null,
  ong_ba nvarchar(128) null,
  dien_giai nvarchar(256) null,
  ma_nvbh char(20) null,
  t_so_luong numeric(19,4) null,
  t_tien numeric(19,4) null,
  /*TODO(cột nghiệp vụ master)*/
  datetime0 smalldatetime null,
  datetime2 smalldatetime null,
  user_id0 varchar(20) null,
  user_id2 varchar(20) null,
  constraint pk_m{{xt}}$ primary key (stt_rec)
)

create table d{{xt}}$ (
  stt_rec varchar(13) not null,
  stt_rec0 varchar(13) not null,
  line_nbr int null,
  ma_ct char(3) null,
  so_ct char(12) null,
  ngay_ct smalldatetime null,
  ma_vt char(20) null,
  dvt nvarchar(20) null,
  he_so numeric(19,4) null,
  ma_kho char(20) null,
  so_luong numeric(19,4) null,
  tien numeric(19,4) null,
  ghi_chu nvarchar(256) null,
  /*TODO(cột nghiệp vụ detail)*/
  constraint pk_d{{xt}}$ primary key (stt_rec, stt_rec0)
)

create table c{{xt}}$ (/*TODO schema prime/partition — clone c{mau}$*/)
create table i{{xt}}$ (/*TODO schema inquiry — clone i{mau}$*/)
create table m{{xt}}log$ (/*TODO schema log — clone m{mau}log$, bỏ nếu không dùng log*/)
create table a{{xt}}$ (/*TODO schema lịch sử duyệt — clone a{mau}$, BẮT BUỘC cho APVHisTable*/)

/* ---------- Đăng ký phân kỳ MỌI bảng (thiếu → $partition$ không resolve) ---------- */
exec Dynamic$AddTable 'm{{xt}}$'
exec Dynamic$AddTable 'd{{xt}}$'
exec Dynamic$AddTable 'c{{xt}}$'
exec Dynamic$AddTable 'i{{xt}}$'
exec Dynamic$AddTable 'a{{xt}}$'
-- exec Dynamic$AddTable 'm{{xt}}log$'

/* ---------- Proc ---------- */
create proc zc_{{x}}Post
  @ma_ct char(3), @stt_rec varchar(13)
as
begin
  -- TODO(nghiệp vụ post sổ riêng của {{x}})
  return
end
go

create proc rs_Print{{x}}Tran
  @language char(1), @key varchar(128), @detail varchar(64), @ma_ct char(3), @bilingual tinyint
as
begin
  -- TODO(truy vấn detail m{{xt}}$ + d{{xt}}$ trả mẫu in — theo rs_Print{Mau}Tran)
  return
end
go

create proc rs_CreateNotify{{x}}Tran
  @stt_rec varchar(13), @master varchar(64), @detail varchar(64), @content varchar(128), @userID varchar(20), @sysDB varchar(64)
as
begin
  -- TODO(nội dung notify — theo rs_CreateNotify{Mau}Tran; bỏ nếu không dùng PostNotify)
  return
end
go

/* ---------- APV post/unpost hooks ----------
   Options/Message.xml: APPEND action '{x}Approval' clone từ action mẫu —
   đổi @voucherType = '{{apv_type}}' trong query checking. Proc dùng chung
   theo PHÂN HỆ (GN bỏ prefix — KHÔNG có PU$/SO$):
   - GN (template này): FastBusiness$APV$PostAuthorize / UnPostAuthorize
   - PU mua hàng: FastBusiness$APV$PU$PostAuthorize / $PU$UnPostAuthorize
   - SO bán hàng: FastBusiness$APV$SO$PostAuthorize / $SO$UnPostAuthorize

   Nghiệp vụ riêng sau duyệt → ALTER 2 proc dùng chung của đúng phân hệ,
   APPEND nhánh mới (paste_sql lấy source trước):
   -- alter proc FastBusiness$APV$PostAuthorize …
   --   if @voucherCode = '{{x}}' and @action = '1' and @status = '2'
   --     exec zc_{{x}}Post …          -- vd khóa sảnh, sinh CT con
   -- alter proc FastBusiness$APV$UnPostAuthorize …
   --   if @voucherCode = '{{x}}'
   --     delete bang_khoa where stt_rec = @idNumber
   GIỮ NGUYÊN nhánh cũ đang chạy — nhánh mới đứng cạnh, không sửa logic cũ.
*/

/* ---------- Kiểm ----------
   - query_database type=3 PARSEONLY toàn file (bỏ qua false positive 1059)
   - PARSEONLY chỉ check cú pháp — KHÔNG chứng minh bảng/cột tồn tại
*/
