from fastbusiness_mcp.stdio_safe import ensure_stdio_safe_print

ensure_stdio_safe_print()

from .utils.logger import setup_logger
from .mcp_app import server, load_config, get_config, set_config

logger = setup_logger(__name__)


class FastBusinessMCPServer:
    """FastBusiness MCP Server wrapper (tương thích ngược)."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.server = server
        logger.info("FastBusiness MCP Server (MCPServer + Pydantic v2) initialized")

    def run(self) -> None:
        """Chạy MCP server trên stdio transport."""
        logger.info("Starting FastBusiness MCP Server (MCPServer stdio)...")
        self.server.run()


def main():
    """Entry point for the MCP server."""
    from fastbusiness_mcp.license import verify_and_enforce_license

    verify_and_enforce_license()
    logger.info("License verified successfully.")
    
    server_app = FastBusinessMCPServer()
    server_app.run()


if __name__ == "__main__":
    main()
