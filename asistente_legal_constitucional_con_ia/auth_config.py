"""Configuración de autenticación local para la app.

Provee una importación única de reflex_local_auth como `lauth`, con un shim
de compatibilidad para `rx.cached_var` si no existe en la versión actual de Reflex.
También establece las rutas de login/registro que usará la app.
"""

from __future__ import annotations

import reflex as rx

# Shim de compatibilidad: algunas versiones de `reflex_local_auth` usan `rx.cached_var`.
if not hasattr(rx, "cached_var"):  # type: ignore[attr-defined]
    rx.cached_var = rx.var  # type: ignore[attr-defined]

# Shim adicional: algunas versiones de reflex_local_auth usan la sintaxis compuesta
# rx.input.root(...). En Reflex <= 0.8.x, rx.input suele ser un componente simple
# (TextField) y no expone atributos .root / .label / etc. Para mantener compatibilidad
# sin romper si más adelante se actualiza Reflex (y sí existen esos atributos), sólo
# añadimos los que falten delegando al propio rx.input.
try:  # Protección defensiva para ambientes limitados
    if not hasattr(rx.input, "root"):
        def _input_root(*children, **props):  # type: ignore
            return rx.input(*children, **props)  # delega
        rx.input.root = _input_root  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    pass

# Import del paquete de auth local, expuesto como `lauth` para el resto de la app.
import reflex_local_auth as lauth  # type: ignore

# Opcional: declarar rutas de login/registro que usaremos en la app.
try:  # Mantener resiliencia si la API no existe en esta versión
    lauth.set_login_route("/login")  # type: ignore[attr-defined]
    lauth.set_register_route("/register")  # type: ignore[attr-defined]
except Exception:
    pass

__all__ = ["lauth"]