import json

with open("rag_pipeline.ipynb", "r", encoding="utf-8") as f:
    nb = json.load(f)

print("Executing rag_pipeline.ipynb cells in sequence...")
global_scope = {}

for idx, cell in enumerate(nb["cells"]):
    if cell["cell_type"] == "code":
        code = "".join(cell["source"])
        print(f"\n--- Running Cell {idx+1} ---")
        exec(code, global_scope)

print("\n[OK] All notebook code cells executed successfully!")
