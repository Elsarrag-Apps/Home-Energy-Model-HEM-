from pathlib import Path
p=Path('ui/utils/full_case_builder.py')
t=p.read_text(encoding='utf-8')
needle='''    hem_input.pop("_ui_metadata", None)\n\n    save_json(output_json_path, hem_input)\n'''
patch='''    iv = hem_input.get("InfiltrationVentilation", {})\n    if isinstance(iv, dict):\n        mv = iv.get("MechanicalVentilation", {})\n        if isinstance(mv, dict):\n            for item in mv.values():\n                if isinstance(item, dict):\n                    item.pop("type", None)\n\n    hem_input.pop("_ui_metadata", None)\n\n    save_json(output_json_path, hem_input)\n'''
if 'item.pop("type", None)' not in t:
    t=t.replace(needle,patch,1)
p.write_text(t,encoding='utf-8')
print('patched builder')
