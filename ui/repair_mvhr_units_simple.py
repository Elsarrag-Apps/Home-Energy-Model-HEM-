from pathlib import Path

p = Path("ui/utils/full_case_builder.py")
t = p.read_text(encoding="utf-8")

# Remove broken conversion remnants and use HEM-native m3/h directly.
t = t.replace("design_flow_l_s = float(mech.get("design_flow_l_s", mech.get("design_outdoor_air_flow_rate", 0.0)) or 0.0)\\n                design_flow = design_flow_l_s * 3.6", "design_flow = float(mech.get("design_flow_m3_h", mech.get("design_flow_l_s", mech.get("design_outdoor_air_flow_rate", 0.0))) or 0.0)")

t = t.replace("design_flow_l_s = float(saved_mech.get("design_flow_l_s", 0.0) or 0.0)\\n    design_flow = design_flow_l_s * 3.6", "design_flow = float(saved_mech.get("design_flow_m3_h", saved_mech.get("design_flow_l_s", 0.0)) or 0.0)")

# Fix cases where a real newline was inserted but indentation broke.
t = t.replace("design_flow_l_s = float(mech.get("design_flow_l_s", mech.get("design_outdoor_air_flow_rate", 0.0)) or 0.0)\n                design_flow = design_flow_l_s * 3.6", "design_flow = float(mech.get("design_flow_m3_h", mech.get("design_flow_l_s", mech.get("design_outdoor_air_flow_rate", 0.0))) or 0.0)")

t = t.replace("design_flow_l_s = float(saved_mech.get("design_flow_l_s", 0.0) or 0.0)\n    design_flow = design_flow_l_s * 3.6", "design_flow = float(saved_mech.get("design_flow_m3_h", saved_mech.get("design_flow_l_s", 0.0)) or 0.0)")

p.write_text(t, encoding="utf-8")
print("Repaired MVHR flow units to HEM-native m3/h")
