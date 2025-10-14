# asistente_legal_constitucional_con_ia/pages/transcription_page.py
"""Página para transcripción de audio."""

import reflex as rx

from ..components.layout import main_layout
from ..states.transcription_state import TranscriptionState, TranscriptionType


def transcription_page() -> rx.Component:
    """Página de transcripción de audio."""

    is_processing = TranscriptionState.transcribing
    has_error = TranscriptionState.error_message != ""
    is_successful = TranscriptionState.current_transcription == "SUCCESS"
    no_file_selected = rx.selected_files("upload_mp3") == ""

    content = rx.vstack(
        rx.heading("Transcripción de Audio", size="8", margin_bottom="2rem"),
        # --- SECCIÓN DE SUBIDA Y PROCESO ---
        # ✅ REFACTORIZADO: Esta sección se oculta cuando la transcripción es exitosa
        rx.cond(
            ~is_successful,
            rx.card(
                rx.vstack(
                    rx.heading("Subir archivo de audio", size="5"),
                    rx.text("Sube un archivo MP3 para transcribirlo.", size="2", color_scheme="gray"),
                    rx.upload(
                        rx.vstack(
                            rx.button("📁 Seleccionar archivo"),
                            rx.text("o arrastra y suelta aquí"),
                        ),
                        id="upload_mp3",
                        border="2px dashed",
                        padding="2em",
                        accept={"audio/mpeg": [".mp3"]},
                        max_files=1,
                        disabled=is_processing,
                        multiple=False,
                    ),
                    rx.hstack(rx.foreach(rx.selected_files("upload_mp3"), lambda file: rx.text(f"Archivo: {file}"))),
                    rx.button(
                        rx.cond(
                            is_processing,
                            rx.hstack(
                                rx.spinner(size="2"),
                                rx.text("Procesando..."),
                                spacing="2",
                            ),
                            rx.text("🎙️ Iniciar Transcripción"),
                        ),
                        on_click=[
                            rx.call_script(
                                """
                                (function() {
                                    const placeholder = document.getElementById('instant-feedback-placeholder');
                                    if (placeholder) {
                                        placeholder.style.display = 'block';
                                    }
                                })();
                                """
                            ),
                            TranscriptionState.handle_transcription_request(rx.upload_files(upload_id="upload_mp3")),
                        ],
                        loading=is_processing,
                        disabled=is_processing | no_file_selected,
                        size="3",
                        margin_top="1rem",
                    ),
                    # ✅ FEEDBACK INSTANTÁNEO del lado del cliente (aparece sin esperar al servidor)
                    rx.box(
                        rx.callout.root(
                            rx.callout.icon(rx.icon("loader", class_name="animate-spin")),
                            rx.callout.text(
                                "🔄 Iniciando proceso de transcripción...",
                                weight="medium",
                            ),
                            color_scheme="blue",
                            variant="soft",
                        ),
                        id="instant-feedback-placeholder",
                        display="none",
                        margin_top="1rem",
                    ),
                    # ✅ INDICADOR DE PROGRESO: Muestra el estado de la transcripción en tiempo real
                    rx.cond(
                        is_processing,
                        rx.vstack(
                            # Ocultar el placeholder cuando aparezca el indicador real
                            rx.script(
                                """
                                const placeholder = document.getElementById('instant-feedback-placeholder');
                                if (placeholder) {
                                    placeholder.style.display = 'none';
                                }
                                """
                            ),
                            rx.divider(),
                            rx.card(
                                rx.vstack(
                                    # Título
                                    rx.heading(
                                        "Procesando Transcripción", 
                                        size="4", 
                                        color_scheme="blue",
                                        text_align="center",
                                    ),
                                    # Spinner + mensaje principal
                                    rx.hstack(
                                        rx.spinner(size="3", color_scheme="blue"),
                                        rx.text(
                                            TranscriptionState.progress_message,
                                            size="3",
                                            weight="medium",
                                        ),
                                        align="center",
                                        spacing="3",
                                        justify="center",
                                    ),
                                    # Barra de progreso
                                    rx.progress(
                                        is_indeterminate=True, 
                                        width="100%", 
                                        color_scheme="blue",
                                        height="8px",
                                    ),
                                    # Mensaje informativo
                                    rx.callout.root(
                                        rx.callout.icon(rx.icon("info")),
                                        rx.callout.text(
                                            "El proceso puede tomar varios minutos dependiendo de la duración del audio. "
                                            "Puedes dejar esta página abierta y el proceso continuará.",
                                        ),
                                        color_scheme="blue",
                                        variant="soft",
                                    ),
                                    spacing="4",
                                    align="center",
                                ),
                                width="100%",
                            ),
                            width="100%",
                        ),
                    ),
                    spacing="4",
                    align="center",
                ),
                width="100%",
            ),
        ),
        # --- MENSAJE DE ÉXITO ---
        rx.cond(
            is_successful,
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.icon("check", color_scheme="green", size=32),
                        rx.heading("¡Notebook Generado!", size="5"),
                        align="center",
                    ),
                    rx.text("Se creó un notebook con tu transcripción."),
                    rx.hstack(
                        rx.button(
                            "📓 Ver Mis Notebooks",
                            on_click=rx.redirect("/notebooks"),
                        ),
                        rx.button(
                            "🎙️ Nueva Transcripción",
                            on_click=TranscriptionState.reset_upload_state,
                            variant="outline",
                        ),
                    ),
                    spacing="4",
                    align="center",
                ),
                width="100%",
                style={"border": "2px solid", "border_color": "var(--green-a6)"},
            ),
        ),
        # --- HISTORIAL DE TRANSCRIPCIONES ---
        rx.card(
            rx.vstack(
                rx.hstack(
                    rx.heading("Transcripciones Anteriores", size="5"),
                    rx.spacer(),
                    rx.button(
                        "Actualizar",
                        on_click=TranscriptionState.refresh_transcriptions,
                        variant="ghost",
                        size="2",
                    ),
                    align="center",
                ),
                rx.cond(
                    TranscriptionState.transcriptions,
                    rx.vstack(
                        rx.foreach(
                            TranscriptionState.transcriptions,
                            transcription_item,
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    rx.text(
                        "No hay transcripciones anteriores.",
                        color_scheme="gray",
                        padding="2rem 0",
                    ),
                ),
                spacing="4",
            ),
            width="100%",
        ),
        # --- MENSAJE DE ERROR ---
        rx.cond(
            has_error,
            rx.callout.root(
                rx.callout.icon(rx.icon("triangle_alert")),
                rx.callout.text(TranscriptionState.error_message),
                color_scheme="red",
            ),
        ),
        spacing="6",
        width="100%",
        max_width="800px",
        margin="auto",
        padding="2rem",
        on_mount=[
            TranscriptionState.refresh_transcriptions,
            TranscriptionState.reset_upload_state,
        ],
    )

    return main_layout(content)


def transcription_item(trans: TranscriptionType) -> rx.Component:
    """Componente para mostrar una transcripción en el historial."""
    notebook_exists = trans.notebook_id > 0

    return rx.card(
        rx.hstack(
            rx.vstack(
                rx.text(trans.filename, weight="bold"),
                rx.hstack(
                    rx.text(trans.created_at, size="2", color_scheme="gray"),
                    rx.text("•", size="2", color_scheme="gray"),
                    rx.text(f"Duración: {trans.audio_duration}", size="2"),
                ),
                rx.text(
                    trans.transcription_text,
                    size="2",
                    color_scheme="gray",
                    no_of_lines=2,
                ),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.vstack(
                rx.button(
                    "Ver Notebook",
                    on_click=rx.redirect(f"/notebooks/{trans.notebook_id}"),
                    variant="soft",
                    size="2",
                    disabled=~notebook_exists,
                ),
                rx.button(
                    "Eliminar",
                    on_click=TranscriptionState.delete_transcription(trans.id),
                    variant="outline",
                    size="2",
                    color_scheme="red",
                ),
                min_width="130px",
                spacing="2",
            ),
            align="center",
        ),
        width="100%",
    )
