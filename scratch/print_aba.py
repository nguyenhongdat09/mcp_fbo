import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r"z:\FBO\VLOTUS\SP228\App_Data\Controllers\Filter\AccountBalanceAdjustment.f", "r", encoding="utf-8-sig", errors="replace") as f:
    text = f.read()

print("File size:", len(text))
print("--- FULL CONTENT ---")
print(text)
