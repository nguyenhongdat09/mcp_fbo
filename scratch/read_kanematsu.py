import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r"z:\FBO\KANEMATSU2\SP228\App_Data\Controllers\Dir\AccountBalanceAdjustment.xml", "r", encoding="utf-8-sig", errors="ignore") as f:
    text = f.read()

print("Dir XML length:", len(text))
print("--- FIRST 500 CHARS OF Dir/AccountBalanceAdjustment.xml ---")
print(text[:500])

with open(r"z:\FBO\KANEMATSU2\SP228\App_Data\Controllers\Grid\AccountBalanceAdjustment.xml", "r", encoding="utf-8-sig", errors="ignore") as f:
    grid_text = f.read()

print("\nGrid XML length:", len(grid_text))
print("--- FIRST 500 CHARS OF Grid/AccountBalanceAdjustment.xml ---")
print(grid_text[:500])
