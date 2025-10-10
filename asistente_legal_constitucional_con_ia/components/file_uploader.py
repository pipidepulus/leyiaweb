"""Componente para subir archivos, con un diseño compacto y funcional."""

import reflex as rx

from ..states.chat_state import ChatState

# Constantes de diseño
MAX_FILES = 2
SUPPORTED_TYPES = ["pdf", "docx", "txt"]
ACCENT_COLOR = "indigo"
INFO_TEXT_COLOR = "gray"


def file_uploader() -> rx.Component:
    """Renderiza un widget de subida de archivos."""
    selected_files_var = rx.selected_files("sidebar_upload")
    has_selected_files = selected_files_var.length() > 0

    files_used_count = ChatState.file_info_list.length()
    files_available_count = MAX_FILES - files_used_count
    can_upload = files_available_count > 0

    is_processing_file = ChatState.uploading | ChatState.is_performing_ocr

    return rx.vstack(
        rx.text(
            "Soportados: PDF, DOCX, TXT (Solo Archivos Digitales)",
            size="2",
            color=INFO_TEXT_COLOR,
            weight="medium",
        ),
        rx.text(
            f"{files_used_count}/{MAX_FILES} usados, " f"{files_available_count} disponibles",
            size="2",
            color=INFO_TEXT_COLOR,
            weight="medium",
        ),
        rx.vstack(
            rx.upload(
                rx.button(
                    "Subir Archivo",
                    color_scheme=ACCENT_COLOR,
                    size="2",
                    variant="soft",
                    width="100%",
                ),
                id="sidebar_upload",
                border_radius="var(--radius-3)",
                border=f"1px dashed var(--{ACCENT_COLOR}-7)",
                padding="0.25rem",
                width="100%",
                cursor="pointer",
                _hover={
                    "background_color": f"var(--{ACCENT_COLOR}-2)",
                    "border_color": f"var(--{ACCENT_COLOR}-8)",
                },
                accept={
                    "application/pdf": [".pdf"],
                    "application/vnd.openxmlformats-officedocument." "wordprocessingml.document": [".docx"],
                    "text/plain": [".txt"],
                },
                multiple=False,
                disabled=~can_upload | is_processing_file,
            ),
            rx.button(
                rx.cond(
                    is_processing_file,
                    rx.spinner(size="2", color_scheme="white"),
                    rx.icon("play", size=16),
                ),
                "Procesar Archivo",
                width="100%",
                size="2",
                variant="solid",
                color_scheme=ACCENT_COLOR,
                disabled=(~has_selected_files | ~can_upload | is_processing_file),
                on_click=[
                    ChatState.handle_upload(rx.upload_files("sidebar_upload")),
                    rx.call_script("document.getElementById('sidebar_upload').value = ''"),
                ],
            ),
            spacing="3",
            width="100%",
            margin_top="0.5em",
        ),
        rx.vstack(
            rx.cond(
                ChatState.is_performing_ocr,
                rx.hstack(
                    rx.spinner(color_scheme=ACCENT_COLOR),
                    rx.text(
                        ChatState.ocr_progress,
                        size="2",
                        weight="bold",
                        color_scheme=ACCENT_COLOR,
                    ),
                    spacing="3",
                    align="center",
                ),
                rx.cond(
                    ChatState.uploading,
                    rx.text(
                        "Procesando archivo...",
                        size="2",
                        weight="medium",
                        padding_y="0.5em",
                    ),
                    rx.vstack(
                        rx.text(
                            rx.cond(
                                files_used_count > 0,
                                "Archivo procesado.",
                                "Selecciona un archivo para procesar.",
                            ),
                            size="2",
                            color=INFO_TEXT_COLOR,
                            mt="0.5em",
                            height="1.5em",
                            white_space="nowrap",
                            overflow="hidden",
                            text_overflow="ellipsis",
                            width="100%",
                            transition="all 0.3s ease",
                        ),
                        rx.cond(
                            ChatState.upload_error != "",
                            rx.badge(
                                rx.icon("triangle-alert", size=14, margin_right="0.25em"),
                                ChatState.upload_error,
                                color_scheme="red",
                                variant="soft",
                                size="1",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                        align_items="start",
                    ),
                ),
            ),
            width="100%",
            align_items="start",
            min_height="3.5em",
            padding_top="0.5em",
        ),
        spacing="2",
        width="100%",
    )
