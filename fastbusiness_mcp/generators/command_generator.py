"""SQL command generator."""

from ..core.constants import EventType


class CommandGenerator:
    """Generates SQL commands for FastBusiness XML."""

    def generate_inserting_command(
        self, table_prefix: str, has_detail: bool = False
    ) -> str:
        """
        Generate Inserting command with partition support.

        Args:
            table_prefix: Table prefix (e.g., "m91")
            has_detail: Whether this voucher has detail table

        Returns:
            SQL command
        """
        sql = """-- Validation
if exists(select 1 from @@master where so_ct = @so_ct) begin
  select 'so_ct' as field, N'Số chứng từ đã tồn tại' as message
  return
end

-- Get identity
select @stt_rec = dbo.FastBusiness$GetIdentity(@@id)

-- Insert master
insert into @@master
values (@stt_rec, @ngay_ct, @so_ct, ...)

"""
        if has_detail:
            sql += """-- Insert detail
insert into @@prime$partition$current
select * from @{detail_table}
"""

        return sql

    def generate_updating_command(self, has_detail: bool = False) -> str:
        """Generate Updating command with cross-month handling."""
        sql = """-- Check if date changed (cross-month)
#IF $ngay_ct.NewValue <> $ngay_ct.OldValue #THEN
  delete @@prime$partition$previous where stt_rec = @stt_rec
#END

-- Update master
update @@master
set ngay_ct = @ngay_ct, so_ct = @so_ct, ...
where stt_rec = @stt_rec

"""
        if has_detail:
            sql += """-- Update detail
delete @@prime$partition$current where stt_rec = @stt_rec
insert into @@prime$partition$current
select * from @{detail_table}
"""

        return sql

    def generate_deleting_command(self, has_detail: bool = False) -> str:
        """Generate Deleting command."""
        sql = """-- Check authorization
if @@admin <> 1 begin
  select '$NotAuthorized' as message
  return
end

"""
        if has_detail:
            sql += """-- Delete detail
delete @@prime$partition$current where stt_rec = @stt_rec

"""

        sql += """-- Delete master
delete @@master where stt_rec = @stt_rec
"""

        return sql

    def generate_loading_command(self) -> str:
        """Generate Loading command for form."""
        return """-- Execute JavaScript after loading
select 'active$Form$(this);' as message
return
"""

    def generate_processing_command(self, sp_name: str) -> str:
        """
        Generate Processing command for reports.

        Args:
            sp_name: Stored procedure name

        Returns:
            SQL command
        """
        return f"""-- Execute report
exec {sp_name}
  @ngay_tu, @ngay_den,
  @param1, @param2,
  @@language, @@userID, @@admin
"""

    def generate_action(self, action_id: str, query: str) -> str:
        """
        Generate response action.

        Args:
            action_id: Action identifier
            query: SQL query

        Returns:
            Action XML with SQL
        """
        return f"""<action id="{action_id}">
  <text><![CDATA[
{query}
return
  ]]></text>
</action>"""
