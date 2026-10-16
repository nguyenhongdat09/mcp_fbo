<%@ Page AutoEventWireup="false" MasterPageFile="~/Main/MasterPage.master" Inherits="FastBusiness.ReportExtender.UI.Page" v="{{title_v}}" e="{{title_e}}"%>

<asp:Content ID="headContent" ContentPlaceHolderID="head" runat="server"></asp:Content>
<asp:Content ID="mainContent" ContentPlaceHolderID="FastBusiness" runat="server">
    <div>
        <asp:Panel ID="panelReport" runat="server"/>
    </div>
    <!-- ReadOnly="true": mọi cột grid readonly (chỉ xem, sửa qua form).
         FilterMode="true": F5 hiện Filter trước -> bấm nút Filter mới vào Grid.
         Báo cáo = true; danh mục/chứng từ = false. -->
    <FastBusiness:ReportExtender ID="MainReport" runat="server" TargetControlID="panelReport" ReadOnly="true" FilterMode="true" Controller="{{controller}}" />
</asp:Content>
