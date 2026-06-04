"""Inserta la empresa DISTRICHIA SAS y el usuario admin inicial."""
from __future__ import annotations

import secrets

import bcrypt

from core.db import Admin, Empresa, get_session, init_db


def seed_inicial() -> str | None:
    """Crea empresa y admin si no existen.

    Devuelve la contraseña inicial generada para el admin (solo la primera
    vez), o None si ya existía.
    """
    init_db()
    pwd_generada = None
    with get_session() as s:
        if not s.query(Empresa).first():
            s.add(Empresa())
        else:
            # Migrar SMMLV si aún tiene el valor viejo
            emp = s.query(Empresa).first()
            if emp.smmlv < 1750000 or emp.auxilio_transporte < 249000:
                emp.smmlv = 1750905.0
                emp.auxilio_transporte = 249095.0
        if not s.query(Admin).first():
            pwd_generada = secrets.token_urlsafe(10)
            h = bcrypt.hashpw(pwd_generada.encode(), bcrypt.gensalt()).decode()
            s.add(Admin(usuario="admin", password_hash=h))
        s.commit()
    return pwd_generada


if __name__ == "__main__":
    p = seed_inicial()
    if p:
        print(f"Admin creado. Usuario: admin | Contraseña: {p}")
    else:
        print("Seed: ya existía. Nada que crear.")
