import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

base = r"e:\CustomizeExtension\fbo-autocomplete"

def show_snippets(rel_path, keywords):
    full_path = os.path.join(base, rel_path)
    if not os.path.exists(full_path): return
    with open(full_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    print(f"=== {rel_path} ===")
    for i, line in enumerate(lines):
        if any(k.lower() in line.lower() for k in keywords):
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            for j in range(start, end):
                print(f"  L{j+1}: {lines[j].rstrip()}")
            print("  ---")

show_snippets(r"src\TreeFile\ContextMenuActions\registerCommands.js", ["convertxml"])
show_snippets(r"src\TreeFile\ContextMenu.js", ["convertxml", "file_f"])
