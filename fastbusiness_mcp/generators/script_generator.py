"""JavaScript script generator."""

from ..core.constants import FileType


class ScriptGenerator:
    """Generates JavaScript scripts for FastBusiness XML."""

    def generate_form_init(self) -> str:
        """Generate form initialization function."""
        return """function init$Form$(f) {
  // Form initialization
  f.add_onResponseComplete(on$Form$ResponseComplete);
}

function active$Form$(f) {
  // Form activated
}"""

    def generate_response_handler(
        self, context_name: str, column_mapping: list[tuple[int, str]]
    ) -> str:
        """
        Generate response complete handler.

        Args:
            context_name: Action context name
            column_mapping: List of (index, column_name) tuples

        Returns:
            JavaScript response handler
        """
        mapping_comments = "\n".join(
            [f"    // result[{idx}].Value -> {name}" for idx, name in column_mapping]
        )

        return f"""function on$Form$ResponseComplete(sender, e) {{
  var f = e.object;
  var context = e.type.Context;
  var result = e.type.Result;

  switch(context) {{
    case '{context_name}':
      if (result.length > 0) {{
{mapping_comments}
        // Use column values here
      }}
      break;
  }}
}}"""

    def generate_grid_detail_init(self) -> str:
        """Generate grid detail initialization."""
        return """function load$GridVoucherDetail$(g) {
  var f = g.get_element().parentForm;

  // Calculation expressions
  g.$a = {
    tien: '[tien]:=[so_luong]*[gia]',
    gia_vnd: '[gia_vnd]:=[gia_nt]*[$ty_gia]',  // $ = parent
    t_tien: ['t_tien', 'tien']  // Aggregate
  };

  // Request parameters (include parent fields)
  g.$h = ['ngay_ct', 'ty_gia', 'stt_rec'];

  g.add_itemValueChanged(onChange$GridVoucherDetail$);
}

function onChange$GridVoucherDetail$(sender, e) {
  var o = e.get_object();
  var g = o.grid;

  switch(o.field.Name) {
    case 'so_luong':
    case 'gia':
      g.validExpression(o, [g.$a.tien], [g.$a.t_tien]);
      break;
  }
}"""

    def generate_command_handler(self, command_name: str, file_type: FileType) -> str:
        """
        Generate command execution handler.

        Args:
            command_name: Command name
            file_type: File type (DIR or GRID)

        Returns:
            JavaScript command handler
        """
        if file_type == FileType.DIR:
            return f"""function on$Form$ExecuteCommand(sender, e) {{
  var action = e.type.Action;
  var f = sender;

  switch(action) {{
    case '{command_name}':
      // Handle command
      break;
  }}
}}"""
        elif file_type == FileType.GRID_DETAIL:
            return f"""function on$GridDetail$ExecuteCommand(sender, e) {{
  var action = e.type.Action;
  var value = e.type.Value;
  var g = sender;
  var f = g.get_element().parentForm;

  switch(action) {{
    case '{command_name}':
      if (f._action == 'View') break;
      if (!f.validFields('required_field')) break;
      // Handle command
      break;
  }}
}}"""
        else:
            return f"""function on$Grid$ExecuteCommand(sender, e) {{
  var action = e.type.Action;
  var g = sender;

  switch(action) {{
    case '{command_name}':
      // Handle command
      break;
  }}
}}"""
