from pathlib import Path

path = Path("ui/pages/10_Run_HEM_Results.py")
text = path.read_text(encoding="utf-8")

text = text.replace(
    'names = ["immersion", "IES", "instant electric shower"]',
    'names = ["immersion", "IES", "instant electric shower", "hw cylinder", "heat pump 1"]',
)

path.write_text(text, encoding="utf-8")
print("Added common generated DHW names to Run page DHW parser defaults.")