"""Componente del área de chat, versión estable con input controlado."""

import reflex as rx

from ..states.chat_state import ChatState
from .token_meter import token_meter

# Constante para el color principal de la UI del chat
ACCENT_COLOR = "indigo"


def message_bubble(message: rx.Var[dict]) -> rx.Component:
    """Crea una burbuja de mensaje con estilo diferenciado."""
    is_user = message["role"] == "user"
    return rx.box(
        rx.hstack(
            # Volvemos a los avatares simples para garantizar estabilidad
            rx.flex(
                rx.cond(
                    is_user,
                    rx.avatar(
                        src="/usuario.png",
                        fallback="US",
                        size="2",
                        color_scheme="blue",
                        variant="solid",
                        flex_shrink="0",
                    ),
                    rx.avatar(
                        src="/balanza.png",
                        fallback="BT",
                        size="2",
                        color_scheme="green",
                        variant="solid",
                        flex_shrink="0",
                    ),
                ),
                spacing="2",
            ),
            rx.box(
                rx.markdown(
                    message["content"],
                    class_name="prose prose-base max-w-none break-words",
                    component_map={
                        "a": lambda *children, **props: rx.link(
                            *children,  # Pasa el texto del enlace
                            is_external=True,  # Abre en una nueva pestaña
                            # Pasa las demás propiedades (href, etc.)
                            **props,
                        )
                    },
                ),
                rx.cond(
                    ~is_user,
                    rx.icon_button(
                        "copy",
                        on_click=rx.set_clipboard(message["content"]),
                        size="1",
                        variant="ghost",
                        color_scheme="gray",
                        class_name=("absolute top-2 right-2 " "opacity-50 hover:opacity-100 transition-opacity"),
                        title="Copiar texto",
                    ),
                ),
                padding_x="1em",
                padding_y="0.75em",
                border_radius="var(--radius-4)",
                bg=rx.cond(is_user, "#e0e7ff", "#d3dff8"),
                color=rx.cond(is_user, "black", "black"),
                position="relative",
                max_width="90%",
                min_width="0",  # Permite que se encoja
                word_wrap="break-word",
                overflow_wrap="break-word",
                style={
                    "word-break": "break-word",
                    "overflow-wrap": "break-word",
                    "hyphens": "auto",
                },
            ),
            spacing="3",
            align_items="start",
            flex_direction=rx.cond(is_user, "row-reverse", "row"),
            width="100%",
            min_width="0",  # Permite que el hstack se encoja
        ),
        width="100%",
        min_width="0",
        padding_x="0.25rem",  # Pequeño padding lateral
        margin_bottom="0.75rem",  # Espacio entre mensajes
    )


# Versión que funcionaba localmente, restaurada como punto de partida.
# Usa rx.el.textarea con enter_key_submit y el wrapper rx.box.


def chat_input_area() -> rx.Component:
    """Área de entrada de texto con soporte para texto largo."""
    return rx.box(
        rx.form(
            rx.hstack(
                # Envolvemos el textarea en un rx.box que se expandirá.
                rx.box(
                    rx.el.textarea(
                        name="prompt",
                        id="chat-input-box",
                        placeholder=("Escribe tu pregunta aquí... " "pulsa Enter para enviar."),
                        # value=ChatState.current_question,
                        on_change=ChatState.set_current_question.debounce(250),
                        disabled=ChatState.processing,
                        resize="vertical",
                        min_height="60px",
                        max_height="200px",
                        py="0.5em",
                        enter_key_submit=True,
                        width="100%",
                        style={
                            "font-size": "16px",
                            "white-space": "pre-wrap",
                            "word-wrap": "break-word",
                            "overflow-wrap": "break-word",
                            "background_color": "transparent",
                            "border": "none",
                            "outline": "none",
                            "box_shadow": "none",
                        },
                    ),
                    flex_grow=1,
                    width="0",
                ),
                rx.icon_button(
                    rx.cond(ChatState.processing, rx.spinner(size="3"), rx.icon("send", size=20)),
                    type="submit",
                    disabled=ChatState.processing | (ChatState.current_question.strip() == ""),
                    size="3",
                    color_scheme="indigo",
                ),
                align_items="end",
                spacing="3",
                width="100%",
            ),
            on_submit=ChatState.send_message,
            reset_on_submit=False,  # Como lo tenías originalmente.
            width="100%",
        ),
        padding_x="0.5em",
        padding_y="0.5em",
        border="1px solid var(--gray-4)",
        border_radius="var(--radius-4)",
        bg="white",
        width="calc(100% - 1em)",
        margin_x="0.5em",
        margin_bottom="1em",
        box_shadow="0 0 15px rgba(0,0,0,0.05)",
        flex_shrink="0",
    )


def chat_area() -> rx.Component:
    """
    Área principal del chat con autoscroll automático y sin desbordamiento
    horizontal.
    """
    return rx.vstack(
        token_meter(),
        rx.box(
            rx.foreach(ChatState.messages, message_bubble),
            id="chat-messages-container",
            padding_x="0.5rem",
            padding_y="1rem",
            width="100%",
            flex_grow=1,
            overflow_y="auto",
            overflow_x="hidden",
            min_height="0",
            style={
                "scroll-behavior": "smooth",
                "display": "flex",
                "flex-direction": "column",
                "max-width": "100%",  # Asegura que no exceda el contenedor
            },
        ),
        chat_input_area(),
        spacing="0",
        height="100%",
        width="100%",
        max_width="100%",  # Previene desbordamiento del contenedor principal
        align_items="stretch",
    )


def chat() -> rx.Component:
    """Componente principal de chat exportado."""
    return rx.box(
        # Diálogo para crear notebook
        rx.cond(ChatState.show_notebook_dialog, create_notebook_dialog(), rx.fragment()),
        # Botón flotante para crear notebook (solo si hay conversación)
        rx.cond(
            (ChatState.messages.length() >= 4) & (~ChatState.processing),
            rx.button(
                rx.icon("book-plus", size=20),
                "Crear Notebook",
                on_click=ChatState.show_create_notebook_dialog,
                position="fixed",
                bottom="80px",
                right="20px",
                z_index=50,
                size="3",
                color_scheme="green",
                variant="solid",
                box_shadow="lg",
            ),
            rx.fragment(),
        ),
        chat_area(),
        height="100%",
        width="100%",
        overflow="hidden",
        class_name="bg-gray-50",
        style={
            "display": "flex",
            "flex-direction": "column",
            "align-items": "stretch",
        },
        # Solo inicializar el chat sin los métodos de monitoreo
        # que causan recompilaciones
        on_mount=ChatState.initialize_chat_simple,
    )


def create_notebook_dialog() -> rx.Component:
    """Diálogo para crear un notebook a partir de la conversación."""
    return rx.dialog(
        # Trigger vacío ya que se controla con estado
        rx.dialog.trigger(rx.box()),
        rx.dialog.content(
            rx.dialog.title("Crear Notebook"),
            rx.dialog.description(("Convierte tu conversación actual en un notebook editable " "y persistente.")),
            rx.vstack(
                rx.text("Título del notebook:", weight="bold"),
                rx.input(placeholder="Ej: Análisis de la Ley 1437 de 2011", value=ChatState.notebook_title, on_change=ChatState.set_notebook_title, width="100%"),
                rx.text(f"Se incluirán {ChatState.messages.length()} " "mensajes en el notebook.", size="2", color="gray"),
                spacing="3",
                width="100%",
                margin_y="1rem",
            ),
            rx.hstack(
                rx.dialog.close(rx.button("Cancelar", variant="outline", on_click=ChatState.hide_create_notebook_dialog)),
                rx.dialog.close(rx.button("Crear Notebook", on_click=ChatState.create_notebook_from_current_chat, loading=ChatState.loading if hasattr(ChatState, "loading") else False)),
                spacing="3",
                justify="end",
                width="100%",
            ),
            max_width="500px",
        ),
        open=ChatState.show_notebook_dialog,
    )
