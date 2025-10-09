# asistente_legal_constitucional_con_ia/components/layout.py
"""Layout principal de la aplicación, ahora totalmente responsivo y sin rx.drawer."""
import reflex as rx
from ..auth_config import lauth

from ..states.app_state import AppState
from ..states.chat_state import ChatState
from .sidebar import sidebar


def main_layout(content: rx.Component, use_container: bool = True) -> rx.Component:
    """El layout principal que envuelve todas las páginas, con lógica responsiva correcta."""

    content_wrapper = rx.container if use_container else rx.box

    return rx.box(
        # --- MENÚ HAMBURGUESA (SÓLO MÓVIL/TABLET PEQUEÑA) ---
        rx.box(
            rx.hstack(
                rx.icon(tag="menu", size=32, on_click=AppState.toggle_drawer, cursor="pointer", color="var(--blue-9)"),
                # ✅ AÑADIR: Botón/acciones de usuario (auth local) en móvil
                rx.cond(
                    lauth.LocalAuthState.is_authenticated,  # type: ignore[attr-defined]
                    rx.hstack(
                        rx.avatar(
                            fallback=lauth.LocalAuthState.authenticated_user.username[0].upper(),  # type: ignore[attr-defined]
                            size="2",
                        ),
                        rx.vstack(
                            rx.text("Conectado", size="1", color="gray"),
                            rx.text(
                                lauth.LocalAuthState.authenticated_user.username,  # type: ignore[attr-defined]
                                size="2", 
                                weight="bold"
                            ),
                            spacing="0",
                            align="start",
                        ),
                        rx.button("Salir", size="2", variant="soft", on_click=ChatState.logout_and_cleanup),
                        spacing="3",
                    ),
                    rx.hstack(
                        rx.link(rx.button("Login", size="2"), href="/login"),
                        rx.link(rx.button("Registro", size="2", variant="outline"), href="/register"),
                    ),
                ),
                justify="between",
                align="center",
                width="100%",
            ),
            display=["block", "block", "none", "none"],  # Muestra en base y sm, oculta en md y lg
            position="fixed",
            top="1rem",
            left="1rem",
            right="1rem",  # ✅ CAMBIO: para que ocupe todo el ancho
            z_index=1001,  # z-index muy alto para estar por encima de todo
            background="transparent",  # ✅ CAMBIO: fondo transparente para que se vea el gradient
            padding="0.5rem",  # ✅ AÑADIR: padding
            border_bottom="1px solid rgba(255, 255, 255, 0.3)",  # ✅ CAMBIO: borde más sutil
        ),
        # --- "DRAWER" MÓVIL (Implementado con rx.box) ---
        # 1. Overlay (fondo oscuro)
        rx.box(
            on_click=AppState.toggle_drawer,
            display=rx.cond(AppState.show_drawer, "block", "none"),
            position="fixed",
            top="0",
            left="0",
            width="100vw",
            height="100vh",
            bg="rgba(0, 0, 0, 0.5)",
            z_index=999,
        ),
        # 2. Contenido del Sidebar móvil
        rx.box(
            sidebar(is_in_drawer=True),  # Reutilizamos el sidebar aquí
            display=["block", "block", "none", "none"],  # Solo existe en vistas móviles
            position="fixed",
            top="0",
            left=rx.cond(AppState.show_drawer, "0px", "-300px"),  # Desliza desde la izquierda
            width="300px",
            height="100vh",
            padding="1em",
            bg="var(--gray-1)",
            border_right="1px solid var(--gray-4)",
            transition="left 0.3s ease-in-out",  # Animación suave
            z_index=1000,
        ),
        # --- ESTRUCTURA PRINCIPAL (SIDEBAR DE ESCRITORIO + CONTENIDO) ---
        rx.hstack(
            # SIDEBAR DE ESCRITORIO (OCULTO EN MÓVIL/TABLET)
            rx.box(
                sidebar(),  # Reutilizamos el sidebar
                display=["none", "none", "block", "block"],  # Oculto en móvil, visible en escritorio
                width="350px",
                min_width="350px",
                height="100vh",
                position="sticky",
                top="0",
                border_right="1px solid var(--gray-4)",
                padding="1em",
                overflow_y="auto",
                overflow_x="hidden",
            ),
            # CONTENEDOR DEL CONTENIDO DE LA PÁGINA
            rx.vstack(
                # ✅ AÑADIR: Header con usuario para escritorio (auth local)
                rx.hstack(
                    rx.spacer(),
                    rx.cond(
                        lauth.LocalAuthState.is_authenticated,  # type: ignore[attr-defined]
                        rx.hstack(
                            rx.avatar(
                                fallback=lauth.LocalAuthState.authenticated_user.username[0].upper(),  # type: ignore[attr-defined]
                                size="2",
                            ),
                            rx.vstack(
                                rx.text("Conectado", size="1", color="gray"),
                                rx.text(
                                    lauth.LocalAuthState.authenticated_user.username,  # type: ignore[attr-defined]
                                    size="2", 
                                    weight="bold"
                                ),
                                spacing="0",
                                align="start",
                            ),
                            rx.button("Salir", size="2", variant="soft", on_click=ChatState.logout_and_cleanup),
                            spacing="3",
                        ),
                        rx.hstack(
                            rx.link(rx.button("Login", size="2"), href="/login"),
                            rx.link(rx.button("Registro", size="2", variant="outline"), href="/register"),
                        ),
                    ),
                    justify="end",
                    align="center",
                    padding="1rem",
                    border_bottom="1px solid rgba(255, 255, 255, 0.3)",
                    width="100%",
                    background="transparent",
                    display=["none", "none", "flex", "flex"],  # Solo en escritorio
                ),
                # Contenido principal
                content_wrapper(
                    content,
                    # Aumenta padding-top en escritorio para no solapar el header
                    padding_top=["4rem", "4rem", "4rem", "4rem"],
                    padding_x=["1em", "1em", "2em", "2em"],
                    flex_grow=1,
                    max_height="100vh",
                    overflow_y="auto",
                    width="100%",
                    max_width="none",
                    # Reservar el canal de la barra de scroll en el borde de fin (derecha) para no sesgar el centrado
                    style={"scrollbar_gutter": "stable"},
                ),
                spacing="0",
                height="100vh",
                width="100%",
            ),
            align="start",
            height="100vh",
            width="100%",
            overflow="hidden",
        ),
        height="100vh",
        width="100%",
        background="linear-gradient(135deg, #c9d1f5 0%, #d7c8e8 100%)",
    )
