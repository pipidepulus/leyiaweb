"""Barra de navegación principal que incluye un panel contextual inteligente."""

import reflex as rx

from ..states.app_state import AppState
from ..states.chat_state import ChatState
from .asistente_sidebar import asistente_sidebar


class SidebarState(rx.State):
    """Estado para controlar la visibilidad de los componentes de la barra lateral."""

    @rx.var
    def is_on_asistente_page(self) -> bool:
        """Comprueba si la ruta actual es la página del asistente."""
        # RouterData.page is deprecated in Reflex >=0.8.1; prefer router.url
        current_path = getattr(self.router, "url", None)
        if current_path is None:
            # fallback for older versions
            return self.router.page.path == "/asistente"
        return current_path.path == "/asistente"


def sidebar(is_in_drawer: bool = False) -> rx.Component:
    """La barra de navegación principal de la aplicación."""
    link_click_handler = AppState.toggle_drawer if is_in_drawer else None
    return rx.vstack(
        # --- SECCIÓN SUPERIOR ---
        rx.vstack(
            rx.hstack(
                rx.image(src="/balanza.png", height="2em"),
                rx.heading("Asistente Legal", size="6", color="blue", weight="bold"),
                width="100%",
            ),
            rx.divider(),
            rx.link(
                "Nuevo Análisis",
                href="/",
                style={"width": "100%", "color": "blue", "font-weight": "bold"},
                on_click=[handler for handler in [link_click_handler, ChatState.limpiar_chat] if handler is not None],
            ),
            rx.vstack(
                # Enlaces principales - ahora disponibles sin autenticación
                rx.link("🤖 Asistente Constitucional", href="/asistente", width="100%", style={"color": "blue", "font-weight": "bold"}, on_click=link_click_handler),
                rx.link("📋 Explorar Proyectos de Ley", href="/proyectos", width="100%", style={"color": "blue", "font-weight": "bold"}, on_click=link_click_handler),
                rx.link("📚 Biblioteca de Prompts", href="/prompts", width="100%", style={"color": "blue", "font-weight": "bold"}, on_click=link_click_handler),
                rx.divider(margin_y="1rem"),
                rx.text("Herramientas Avanzadas", size="2", weight="bold", color="gray"),
                rx.link("📝 Mis Notebooks", href="/notebooks", width="100%", style={"color": "green", "font-weight": "bold"}, on_click=link_click_handler),
                rx.link("🎤 Transcripción de Audio", href="/transcription", width="100%", style={"color": "green", "font-weight": "bold"}, on_click=link_click_handler),
                spacing="5",
                width="100%",
                align_items="start",
            ),
            spacing="5",
            width="100%",
            align_items="start",
        ),
        # --- PANEL CONTEXTUAL ---
        rx.cond(
            SidebarState.is_on_asistente_page,
            asistente_sidebar(),
            rx.fragment(),
        ),
        rx.spacer(),
        # --- ESTILOS DEL CONTENEDOR PRINCIPAL ---
        spacing="5",
        height="100%",
        width="100%",
        align_items="stretch",
    )
