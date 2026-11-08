"""Crea un usuario administrador.

Uso:
    python -m app.create_admin admin@tienda.com "Nombre Admin"
La contraseña se pide por consola para que no quede en el historial.
"""

import getpass
import sys

from pydantic import ValidationError

from app.db.session import SessionLocal
from app.models.user import UserRole
from app.schemas.user import UserCreate
from app.services.user_service import create_user


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 1

    email, full_name = sys.argv[1], sys.argv[2]
    password = getpass.getpass("Contraseña (mínimo 8 caracteres): ")
    if password != getpass.getpass("Repite la contraseña: "):
        print("Las contraseñas no coinciden.")
        return 1

    try:
        payload = UserCreate(email=email, full_name=full_name, password=password)
    except ValidationError as exc:
        print(f"Datos inválidos:\n{exc}")
        return 1

    db = SessionLocal()
    try:
        user = create_user(db, payload, role=UserRole.ADMIN)
    except ValueError as exc:
        print(exc)
        return 1
    finally:
        db.close()

    print(f"Administrador creado: {user.email} (id {user.id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
