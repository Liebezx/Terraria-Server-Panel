import os
import sys
import getpass
from pathlib import Path

# Add script dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from crypto_vault import decrypt_and_unpack

def main():
    root = Path(__file__).resolve().parent.parent.parent
    panel_dir = root / "Panel"
    vault = panel_dir / "dev_vault.bin"

    print("========================================================")
    print("      РАЗБЛОКИРОВКА ИСХОДНОГО КОДА (РЕЖИМ РАЗРАБОТЧИКА)  ")
    print("========================================================")
    print()

    if not vault.is_file():
        # Check root
        vault = root / "dev_vault.bin"
        if not vault.is_file():
            print("[ОШИБКА] Файл зашифрованного хранилища dev_vault.bin не найден.")
            input("\nНажмите Enter для выхода...")
            return

    key = ""
    if len(sys.argv) > 1:
        key = sys.argv[1].strip()
    else:
        key = input("Введите ваш секретный мастер-ключ: ").strip()

    if not key:
        print("[ОШИБКА] Ключ не может быть пустым.")
        input("\nНажмите Enter для выхода...")
        return

    try:
        print("\nРасшифровка и восстановление исходного кода...")
        restored = decrypt_and_unpack(vault, panel_dir, key)
        print("\n[УСПЕХ] Исходный код успешно восстановлен и расшифрован!")
        print(f"Восстановлено файлов: {len(restored)}")
        for r in restored:
            print(f"  • {r}")
        print("\nТеперь вы можете редактировать файлы и тестировать изменения.")
    except Exception as e:
        print(f"\n[ОШИБКА] Неверный ключ или повреждённое хранилище ({e}).")
        print("Доступ к исходному коду отклонён.")

    input("\nНажмите Enter для продолжения...")

if __name__ == "__main__":
    main()
