import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crypto_vault import pack_and_encrypt

KEY = "Liebe#MasterKey!2026$Terraria7777"

def main():
    root = Path(__file__).resolve().parent.parent.parent
    panel_dir = root / "Panel"
    vault = panel_dir / "dev_vault.bin"

    sources = []
    # Panel sources
    pyw = panel_dir / "TerrariaPanel.pyw"
    if pyw.is_file():
        sources.append((pyw, "TerrariaPanel.pyw"))
    
    ui_dir = panel_dir / "ui"
    if ui_dir.is_dir():
        for f in ui_dir.rglob("*"):
            if f.is_file():
                sources.append((f, "ui/" + f.relative_to(ui_dir).as_posix()))

    # Scripts
    scripts_dir = panel_dir / "scripts"
    if scripts_dir.is_dir():
        for f in scripts_dir.rglob("*"):
            if f.is_file() and f.name not in ("dev_vault.bin", "pack_vault.py"):
                sources.append((f, "scripts/" + f.relative_to(scripts_dir).as_posix()))

    packed = pack_and_encrypt(sources, vault, KEY)
    print(f"Packed {len(sources)} source files ({packed} bytes) into encrypted vault: {vault}")

if __name__ == "__main__":
    main()
