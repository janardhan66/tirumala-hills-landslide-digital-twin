from pathlib import Path

app_path = Path("dashboard/app.py")
with open(app_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

split_idx = None
for i, line in enumerate(lines):
    if 'st.markdown("## 🔬 Deep Dive Analytical Research Lab")' in line:
        split_idx = i
        break

if split_idx:
    new_lines = lines[:split_idx - 1]
    new_lines.append('st.markdown("---")\n')
    new_lines.append('with st.expander("🔬 Deep Dive Analytical Research Lab and Diagnostic Tools (Manual U-Net HDF5 Inference)", expanded=False):\n')
    for line in lines[split_idx:]:
        new_lines.append("    " + line if line.strip() else line)

    with open(app_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"Successfully wrapped legacy research lab into expander at line {split_idx}")
else:
    print("Split index not found")
