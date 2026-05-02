"""Print first/last few lines of the S=[...] array in app.html for inspection."""
from pathlib import Path

p = Path(r"D:\KLAUD\Claude_KI\mansa\frontend\app.html")
lines = p.read_text(encoding="utf-8").splitlines()

# Find the S declaration line
start = None
for i, line in enumerate(lines):
    if line.startswith("const S=["):
        start = i
        break

# Find matching closing line — heuristic: look for "];\n" within next 200 lines
end = None
for i in range(start, min(start + 300, len(lines))):
    if lines[i].rstrip() == "];":
        end = i
        break

print(f"S array: lines {start + 1} to {end + 1 if end else '?'} ({(end - start) if end else '?'} lines)")
print()
print("FIRST 5 LINES:")
for j in range(start, min(start + 5, len(lines))):
    print(f"  {j + 1}: {lines[j][:200]}")
print()
print("LINES 1610-1612 (sample tickers):")
for j in range(1609, 1613):
    print(f"  {j + 1}: {lines[j][:300]}")
