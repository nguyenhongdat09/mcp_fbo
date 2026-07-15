# FastBusiness MCP Server - AI Instructions

**Project:** FastBusiness XML Controller Configuration & SQL Server Integration  
**Language:** XML, T-SQL, ES5 JavaScript

## Overview

MCP cung cấp:
- `query_database` — chạy SQL, resolve connection từ `file_path`
- `get_xml_entities` — đọc entity / vị trí khai báo trong XML

## Critical Constraints

1. **Partition** — ALWAYS dùng `$partition$current`, `$partition$previous`, `@@prime$partition$current`. NEVER hardcode tháng (`m66$202411`).
2. **Partitioned table** — giữ `$` trong SQL: XML `d91$000000` → `exec fsd_addfields 'd91$', ...`
3. Non-partitioned (`dmvt`, `dmkh`) — không thêm `$`.

## Context từ path

- `\Dir\` → DIR  
- `\Filter\` → FILTER  
- `\Grid\` → GRID  

## Modules nội bộ

- `find_connect_by_path/` — Web.config → connection string  
- `queryDatabase/` — SQL Server execute  
- `find_entity_by_xml/` — parse entity XML (lxml)
