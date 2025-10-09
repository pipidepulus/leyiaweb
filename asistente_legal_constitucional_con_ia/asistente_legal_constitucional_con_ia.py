# ruta: asistente_legal_constitucional_con_ia/asistente_legal_constitucional_con_ia.py
"""
Archivo principal de la aplicación.
"""
import os
import reflex as rx
from .auth_config import lauth
from dotenv import load_dotenv

from asistente_legal_constitucional_con_ia.states.chat_state import ChatState

from .components.layout import main_layout
from .pages.asistente_page import asistente_page
from .pages.notebooks_page import notebook_viewer_page, notebooks_page
from .pages.prompts_page import prompts_page
from .pages.proyectos_page import ProyectosState, proyectos_page
from .pages.transcription_page import transcription_page
from .pages.auth_pages import custom_login_page, custom_register_page
from .auth_config import lauth

# from asistente_legal_constitucional_con_ia.models.database import Notebook, AudioTranscription (Bajo OJO)

# --- Carga de variables de entorno ---
load_dotenv()

# ### CAMBIO 1: Importa tus páginas ###

# 1. Primero, crea la instancia de la aplicación Reflex.
app = rx.App(
    theme=rx.theme(
        appearance="light",
        has_background=True,
        radius="large",
        accent_color="blue",
    ),
    stylesheets=[
        "/global.css",  # La ruta es relativa a assets y debe iniciar con /
    ],
)

# ✅ AÑADIR: Función para crear layout SIN sidebar (usuarios no autenticados)


def public_layout(content: rx.Component) -> rx.Component:
    """Layout público sin sidebar para usuarios no autenticados."""
    return rx.vstack(
        rx.box(content, flex="1", width="100%", padding="2rem", overflow_y="auto"),
        width="100%",
        height="100vh",
        spacing="0",
        background="linear-gradient(135deg, #c9d1f5 0%, #d7c8e8 100%)",
    )


# ✅ MODIFICAR: Página principal con autenticación local


@rx.page(route="/", title="Inicio")
def index() -> rx.Component:
    """Página principal que maneja autenticación local."""

    # Contenido para usuarios NO autenticados (actual)
    unauthenticated_content = rx.center(
        rx.vstack(
            rx.box(
                # Contenedor fijo y sin recortes para el ícono
                rx.image(
                    src="/balanza.png",
                    width="100%",
                    height="100%",
                    object_fit="contain",
                    object_position="center",
                    margin="0",
                    display="block",
                ),
                width="80px",
                height="80px",
                margin_bottom="1rem",
                # Padding mínimo para evitar que el borde visual "toque" el canvas del PNG
                padding="2px",
                overflow="visible",
                display="flex",
                align_items="center",
                justify_content="center",
                margin_x="auto",
            ),
            rx.heading(
                "Asistente Legal Constitucional con IA",
                size="7",
                margin_bottom="1rem",
                color_scheme="blue",
                weight="bold",
                text_align="center",
                class_name="text-shadow",
            ),
            rx.text(
                "Sistema especializado en análisis de jurisprudencia y leyes con inteligencia artificial.",
                size="4",
                color_scheme="blue",
                margin_bottom="0.8rem",
                text_align="center",
            ),
            # ✅ MODIFICAR: Card de autenticación con botones de auth local
            rx.card(
                rx.vstack(
                    rx.heading("🔐 Acceso Protegido", size="5", color="orange", text_align="center"),
                    rx.text("Para proteger los recursos de IA y personalizar tu experiencia, " "todas las funcionalidades requieren autenticación.", text_align="center", margin_bottom="1rem"),
                    rx.vstack(
                        rx.text("🌟 Funcionalidades Disponibles:", weight="bold", color="blue"),
                        rx.text("• 🤖 Asistente Legal Inteligente", size="2"),
                        rx.text("• 📋 Análisis de Proyectos de Ley", size="2"),
                        rx.text("• 📚 Biblioteca de Prompts Especializados", size="2"),
                        rx.text("• 📝 Notebooks Personales y Persistentes", size="2"),
                        rx.text("• 🎤 Transcripción de Audio con Whisper", size="2"),
                        spacing="2",
                        align="start",
                        margin_bottom="1.5rem",
                    ),
                    # ✅ CAMBIO: Enlaces a páginas de login/registro (auth local)
                    rx.hstack(
                        rx.link(rx.button("💎 Comenzar", size="4", color_scheme="blue"), href="/login"),
                        rx.link(rx.button("Crear Cuenta", size="4", variant="outline"), href="/register"),
                        spacing="4",
                        justify="center",
                    ),
                    spacing="3",
                    align="center",
                ),
                max_width="600px",
                padding="2rem",
                margin="1rem",
            ),
            rx.text("💡 Crea una cuenta gratuita para acceder a todas las herramientas.", size="3", color="gray", text_align="center", font_style="italic"),
            align="center",
            spacing="3",
            on_mount=ChatState.limpiar_chat,
        ),
        min_height="80vh",
         width="100%",
    )

    # Contenido para usuarios autenticados (con sidebar)
    authenticated_content = rx.flex(
        rx.box(
            rx.image(
                src="/balanza.png",
                width="100%",
                height="100%",
                object_fit="contain",
                object_position="center",
                margin="0",
                display="block",
            ),
            width="120px",
            height="120px",
            margin_bottom="1.5rem",
            padding="3px",
            overflow="visible",
            display="flex",
            align_items="center",
            justify_content="center",
        ),
        rx.heading("¡Bienvenido!", size="7", color="blue", text_align="center", margin_bottom="1rem"),
        rx.text("Selecciona una herramienta del menú lateral para comenzar.", size="4", text_align="center", color="gray", margin_bottom="2rem"),
        rx.hstack(
            rx.link(rx.button("🤖 Ir al Asistente", color_scheme="blue", size="3"), href="/asistente"),
            rx.link(rx.button("📝 Mis Notebooks", variant="outline", size="3"), href="/notebooks"),
            spacing="4",
            justify="center",
        ),
        direction="column",
        align="center",
        justify="center",
        spacing="4",
        width="100%",
        height="100%",
        max_width="600px",
        margin_x="auto",
    )

    # Con auth local, usamos un condicional simple sobre el estado de autenticación
    return rx.cond(
        lauth.LocalAuthState.is_authenticated,  # type: ignore[attr-defined]
        # Usuario autenticado: usar layout sin container
        main_layout(authenticated_content, use_container=False),
        # Usuario NO autenticado: mostrar landing sin sidebar
        public_layout(unauthenticated_content),
    )


def create_protected_page(page_func, title: str):
    """Crea una página protegida sin decorador @rx.page."""

    def protected_page_component() -> rx.Component:
        # Con auth local protegemos por estado
        return rx.cond(
            lauth.LocalAuthState.is_authenticated,  # type: ignore[attr-defined]
            page_func(),
            rx.center(
                rx.vstack(
                    rx.image(src="/balanza.png", width="80px", height="80px", margin_bottom="1rem", object_fit="contain", margin_x="auto"),
                    rx.heading("Acceso Restringido", size="6"),
                    rx.text("Debes iniciar sesión para acceder a esta página."),
                    rx.link(rx.button("Iniciar Sesión", color_scheme="blue"), href="/login"),
                    spacing="4",
                    align="center",
                ),
                min_height="100vh",
            ),
        )

    return protected_page_component


# ✅ MODIFICAR: Aplicar protección a todas las páginas except index
app.add_page(create_protected_page(asistente_page, "Asistente Constitucional"), route="/asistente", title="Asistente Constitucional")

app.add_page(create_protected_page(proyectos_page, "Proyectos de Ley"), route="/proyectos", title="Proyectos de Ley", on_load=ProyectosState.scrape_proyectos)

app.add_page(create_protected_page(prompts_page, "Biblioteca de Prompts"), route="/prompts", title="Biblioteca de Prompts")

app.add_page(create_protected_page(notebooks_page, "Mis Notebooks"), route="/notebooks", title="Mis Notebooks")

app.add_page(create_protected_page(lambda: notebook_viewer_page(), "Ver Notebook"), route="/notebooks/[notebook_id]", title="Ver Notebook")

app.add_page(create_protected_page(transcription_page, "Transcripción de Audio"), route="/transcription", title="Transcripción de Audio")

# Rutas de autenticación local (páginas personalizadas)
try:
    app.add_page(custom_login_page, route="/login", title="Iniciar Sesión", on_load=ChatState.limpiar_chat)
    app.add_page(custom_register_page, route="/register", title="Crear Cuenta", on_load=ChatState.limpiar_chat)
except Exception:
    pass
