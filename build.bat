call E:\mcp_fbo\venv\Scripts\activate.bat

pyinstaller run_server.py ^
  --name fastbusiness_mcp ^
  --onedir ^
  --console ^
  --add-data "knowledge_base;knowledge_base" ^
  --add-data "data;data" ^
  --add-data "config.yaml;." ^
  --clean

pause
