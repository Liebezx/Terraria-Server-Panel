import os
import sys
import io
import zipfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

SALT_SIZE = 16
NONCE_SIZE = 12
ITERATIONS = 200_000

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))

def pack_and_encrypt(source_paths: list[tuple[Path, str]], output_vault: Path, passphrase: str) -> int:
    """Zips source_paths into memory and encrypts with AES-256-GCM."""
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for file_path, arcname in source_paths:
            if file_path.is_file():
                zf.write(file_path, arcname)
    raw_data = mem_zip.getvalue()

    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, raw_data, None)

    output_vault = Path(output_vault)
    output_vault.parent.mkdir(parents=True, exist_ok=True)
    with output_vault.open("wb") as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)

    return len(raw_data)

def decrypt_and_unpack(vault_path: Path, output_dir: Path, passphrase: str) -> list[str]:
    """Decrypts AES-256-GCM vault and restores files into output_dir."""
    vault_path = Path(vault_path)
    if not vault_path.is_file():
        raise FileNotFoundError(f"Файл хранилища не найден: {vault_path}")

    with vault_path.open("rb") as f:
        salt = f.read(SALT_SIZE)
        nonce = f.read(NONCE_SIZE)
        ciphertext = f.read()

    if len(salt) != SALT_SIZE or len(nonce) != NONCE_SIZE or not ciphertext:
        raise ValueError("Повреждённый файл хранилища.")

    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    raw_data = aesgcm.decrypt(nonce, ciphertext, None)

    restored = []
    mem_zip = io.BytesIO(raw_data)
    with zipfile.ZipFile(mem_zip, "r") as zf:
        for info in zf.infolist():
            target = output_dir / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as dst:
                dst.write(src.read())
            restored.append(info.filename)

    return restored
