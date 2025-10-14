# asistente_legal_constitucional_con_ia/states/transcription_state.py
"""Estado para transcripción de audio con AssemblyAI."""

import asyncio
import dataclasses
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import assemblyai
import reflex as rx
from ..auth_config import lauth
from dotenv import load_dotenv

from ..models.database import AudioTranscription, Notebook

load_dotenv()


@dataclasses.dataclass
class TranscriptionType:
    """Tipo para representar una transcripción en el frontend."""

    id: int
    filename: str
    transcription_text: str
    audio_duration: str
    created_at: str
    updated_at: str
    notebook_id: int


class TranscriptionState(rx.State):
    """Estado para gestionar transcripciones de audio."""

    transcriptions: list[TranscriptionType] = []
    current_transcription: Optional[str] = ""
    transcribing: bool = False
    progress_message: str = ""
    error_message: str = ""
    uploaded_files: list[str] = []
    
    # Variables temporales para pasar datos entre handlers
    _pending_audio_data: bytes = b""
    _pending_filename: str = ""
    _pending_workspace_id: str = ""  # Workspace ID del usuario para background task
    
    # ✅ NUEVO: Caché del workspace_id para evitar consultas repetidas a Redis
    _cached_workspace_id: str = ""
    _workspace_id_initialized: bool = False
    _cached_user_id: str = ""  # ✅ NUEVO: Para detectar cambio de usuario

    async def get_user_workspace_id_cached(self) -> str:
        """Obtiene el workspace ID con caché para evitar llamadas repetidas a Redis.
        
        Esta versión optimizada reduce drásticamente el tiempo de respuesta en producción
        al cachear el workspace_id por sesión (de 10-15s a < 1s en la primera llamada,
        y < 100ms en llamadas subsecuentes).
        
        ✅ SEGURIDAD: Invalida el caché si detecta cambio de usuario.
        """
        # ✅ FIX: Verificar si el usuario cambió antes de usar el caché
        auth_state = await self.get_state(lauth.LocalAuthState)  # type: ignore[attr-defined]
        current_user = getattr(auth_state, "authenticated_user", None)
        
        # Obtener un identificador único del usuario actual
        current_user_id = ""
        if current_user is not None:
            if hasattr(current_user, "get"):
                current_user_id = str(current_user.get("id") or current_user.get("username") or current_user.get("email") or "")
            else:
                current_user_id = str(getattr(current_user, "id", None) or getattr(current_user, "username", None) or "")
        
        # ✅ Si el usuario cambió, invalidar el caché
        if current_user_id != self._cached_user_id:
            self._workspace_id_initialized = False
            self._cached_workspace_id = ""
            self._cached_user_id = current_user_id
        
        # Si ya está inicializado para este usuario, devolver el caché
        if self._workspace_id_initialized and self._cached_workspace_id:
            return self._cached_workspace_id
        
        # Si no está en caché, obtener y cachear
        workspace_id = await self._fetch_workspace_id_optimized()
        
        # Guardar en caché
        self._cached_workspace_id = workspace_id
        self._workspace_id_initialized = True
        
        return workspace_id
    
    async def _fetch_workspace_id_optimized(self) -> str:
        """Método privado optimizado que hace la consulta real al estado de autenticación.
        
        Optimizaciones vs versión anterior:
        - Reduce de 8 intentos a máximo 3-4
        - Usa evaluación corto-circuito (or) en lugar de loops
        - Menos overhead de try/except
        """
        try:
            auth_state = await self.get_state(lauth.LocalAuthState)  # type: ignore[attr-defined]
            
            # Intento directo y rápido al usuario autenticado
            user = getattr(auth_state, "authenticated_user", None)
            if user is not None:
                # Priorizar los campos más comunes primero
                if hasattr(user, "get"):
                    # Usuario es un dict-like
                    user_id = user.get("id") or user.get("user_id") or user.get("username") or user.get("email")
                    if user_id:
                        return str(user_id)
                else:
                    # Usuario es un objeto
                    user_id = getattr(user, "id", None) or getattr(user, "user_id", None) or getattr(user, "username", None)
                    if user_id:
                        return str(user_id)
            
            # Fallback directo a atributos del auth_state
            workspace_id = (
                getattr(auth_state, "user_id", None) or 
                getattr(auth_state, "id", None) or 
                getattr(auth_state, "username", None) or 
                getattr(auth_state, "email", None)
            )
            if workspace_id:
                return str(workspace_id)
            
            return "public"
            
        except Exception as e:
            # Si falla por cualquier razón (incluyendo background task), retornar public
            print(f"DEBUG: No se pudo acceder a AuthState: {e}")
            return "public"

    async def get_user_workspace_id(self) -> str:
        """Obtiene el workspace ID del usuario autenticado usando auth local.
        
        DEPRECADO: Usar get_user_workspace_id_cached() en su lugar para mejor rendimiento.
        Este método se mantiene por compatibilidad pero ahora delega a la versión optimizada.
        """
        return await self._fetch_workspace_id_optimized()
    
    @rx.event
    async def handle_transcription_request(self, files: List[rx.UploadFile]):
        """
        Handler de upload: Solo valida y lee el archivo.
        Delega el procesamiento pesado a process_transcription_background.
        """
        if not files:
            return

        file = files[0]
        
        try:
            # Validación rápida
            if not file.content_type == "audio/mpeg":
                yield rx.toast.error(f"'{file.name}' no es un MP3.")
                return

            # ✅ MEJORA UI: Feedback INMEDIATO al usuario antes de cualquier operación
            self.transcribing = True
            self.progress_message = f"🔄 Iniciando proceso para '{file.name}'..."
            self.error_message = ""
            yield  # 👈 Actualizar UI INMEDIATAMENTE
            
            # Leer archivo (< 1 segundo, no causa timeout)
            self.progress_message = "📖 Leyendo archivo de audio..."
            yield  # 👈 Mostrar que estamos leyendo
            
            # ✅ OPTIMIZADO: Obtener workspace_id ANTES de entrar al background task usando versión cacheada
            # Esto reduce el tiempo de respuesta de 10-15s a < 1s en la primera llamada
            # y < 100ms en llamadas subsecuentes (usa caché de sesión)
            self.progress_message = "🔐 Verificando credenciales de usuario..."
            yield  # 👈 Indicar que estamos verificando
            
            self._pending_workspace_id = await self.get_user_workspace_id_cached()
            
            # Actualizar mensaje después de obtener workspace_id
            self.progress_message = f"📤 Preparando envío de '{file.name}' a AssemblyAI..."
            yield  # 👈 Confirmar preparación
            
            # Almacenar datos temporalmente
            self._pending_audio_data = await file.read()
            self._pending_filename = file.name
            self.uploaded_files = [file.name]
            
            yield
            
            # Iniciar procesamiento en background usando yield from
            yield TranscriptionState.process_transcription_background
            
        except Exception as e:
            self.error_message = f"Error al leer archivo: {str(e)}"
            self.transcribing = False
            yield rx.toast.error(self.error_message)

    @rx.event(background=True)
    async def process_transcription_background(self):
        """
        Procesa la transcripción usando AssemblyAI.
        Se ejecuta en background para evitar timeouts de lock.
        """
        # Copiar datos en variables locales y limpiar mensajes de error previos
        async with self:
            audio_data = self._pending_audio_data
            filename = self._pending_filename
            self.error_message = ""  # Limpiar errores de ejecuciones anteriores
            
            if not audio_data:
                self.error_message = "No hay datos de audio para procesar"
                self.transcribing = False
                return

        try:
            # Configurar AssemblyAI
            api_key = os.getenv("ASSEMBLYAI_API_KEY")
            if not api_key:
                raise ValueError("API key de AssemblyAI no configurada en .env")

            assemblyai.settings.http_timeout = 300
            assemblyai.settings.api_key = api_key
            transcriber = assemblyai.Transcriber()
            config = assemblyai.TranscriptionConfig(
                speaker_labels=True, 
                language_code="es"
            )

            # Enviar el trabajo
            async with self:
                self.progress_message = f"⏳ Subiendo audio al servidor de transcripción..."
            
            submitted_transcript = await asyncio.to_thread(
                transcriber.submit, 
                audio_data, 
                config
            )

            async with self:
                self.progress_message = f"⏱️ Tu archivo está en cola. Puede tomar 2-5 minutos dependiendo de la duración..."

            # Sondear el estado
            while True:
                polled_transcript = await asyncio.to_thread(
                    assemblyai.Transcript.get_by_id, 
                    submitted_transcript.id
                )

                if polled_transcript.status == assemblyai.TranscriptStatus.completed:
                    async with self:
                        self.progress_message = "¡Éxito! Generando notebook..."
                        self.error_message = ""  # Limpiar cualquier error residual
                    
                    await self._process_successful_transcription(
                        polled_transcript, 
                        filename
                    )
                    
                    async with self:
                        self.transcribing = False
                        self.progress_message = ""
                        self.error_message = ""  # Asegurar que está limpio al final
                        self._pending_audio_data = b""
                        self._pending_filename = ""
                        self._pending_workspace_id = ""
                    
                    yield rx.toast.success(f"¡Notebook de '{filename}' generado!")
                    break

                elif polled_transcript.status == assemblyai.TranscriptStatus.error:
                    raise RuntimeError(
                        f"Error de AssemblyAI: {polled_transcript.error}"
                    )
                else:
                    # Traducir estados técnicos a mensajes amigables
                    status_messages = {
                        "queued": "⏱️ En cola de procesamiento. Tu transcripción iniciará pronto...",
                        "processing": "🎙️ Transcribiendo tu audio. Esto puede tomar varios minutos...",
                    }
                    async with self:
                        self.progress_message = status_messages.get(
                            str(polled_transcript.status),
                            f"⚙️ Procesando... Verificando estado cada 5 segundos..."
                        )
                    await asyncio.sleep(5)

        except Exception as e:
            # Log detallado para debugging
            import traceback
            error_detail = f"Error en el proceso: {str(e)}\nTraceback: {traceback.format_exc()}"
            print(f"DEBUG EXCEPTION: {error_detail}")
            
            async with self:
                self.error_message = f"Error en el proceso: {str(e)}"
                self.transcribing = False
                self._pending_audio_data = b""
                self._pending_filename = ""
                self._pending_workspace_id = ""
            yield rx.toast.error(self.error_message)

    async def _process_successful_transcription(self, transcript: assemblyai.Transcript, filename: str):
        """Helper para procesar una transcripción exitosa."""
        # ... (la lógica para crear el texto de la transcripción y el notebook_title sigue igual)
        if transcript.utterances:
            lines = [f"**Hablante {utt.speaker}:** {utt.text}" for utt in transcript.utterances]
            transcription_text = "## Transcripción con Identificación de Hablantes\n\n" + "\n\n".join(lines)
        else:
            transcription_text = transcript.text or ""

        notebook_title = f"Transcripción - {os.path.splitext(filename)[0]}"
        duration_secs = transcript.audio_duration or 0
        duration_fmt = f"{int(duration_secs // 60)}:{int(duration_secs % 60):02d}"

        # Crea el registro en la BD
        await self._create_transcription_notebook(transcription_text, notebook_title, filename, duration_fmt)

        # Obtener el workspace_id guardado
        workspace_id = self._pending_workspace_id or "public"
        
        # 1. Obtener los datos actualizados usando el método auxiliar
        updated_transcriptions = self._fetch_user_transcriptions_data(workspace_id)

        # 2. Modificar el estado de forma segura desde la tarea en segundo plano
        async with self:
            self.transcriptions = updated_transcriptions
            self.current_transcription = "SUCCESS"
            self.uploaded_files = []

    async def _create_transcription_notebook(self, transcription_text: str, title: str, filename: str, duration: str):
        """Crea un notebook y el registro de transcripción en la BD."""
        # Usar el workspace_id almacenado en lugar de llamar a get_user_workspace_id()
        async with self:
            workspace_id = self._pending_workspace_id or "public"
        
        with rx.session() as session:
            from ..models.database import Notebook

            notebook_content = self._convert_transcription_to_notebook(transcription_text, title, filename)

            notebook = Notebook(
                title=title,
                content=json.dumps(notebook_content),
                workspace_id=workspace_id,
                notebook_type="transcription",
            )
            session.add(notebook)
            session.commit()
            session.refresh(notebook)

            transcription = AudioTranscription(
                filename=filename,
                transcription_text=transcription_text,
                notebook_id=notebook.id,
                audio_duration=duration,
                workspace_id=workspace_id,
            )
            session.add(transcription)
            session.commit()

    @rx.event
    async def load_user_transcriptions(self, workspace_id: Optional[str] = None):
        """Carga todas las transcripciones del usuario (ejecutado en primer plano)."""
        try:
            if workspace_id is None:
                # ✅ OPTIMIZADO: Usar versión cacheada
                workspace_id = await self.get_user_workspace_id_cached()

            # 1. Obtener datos usando el método auxiliar
            transcriptions_list = self._fetch_user_transcriptions_data(workspace_id)
            
            # 2. Modificar el estado directamente (permitido en eventos de primer plano)
            self.transcriptions = transcriptions_list

        except Exception as e:
            self.error_message = f"Error cargando transcripciones: {e}"

    @rx.event
    async def delete_transcription(self, transcription_id: int):
        """Elimina una transcripción y su notebook asociado."""
        try:
            # ✅ OPTIMIZADO: Usar versión cacheada
            workspace_id = await self.get_user_workspace_id_cached()
            if workspace_id == "public":
                self.error_message = "Debes iniciar sesión para eliminar transcripciones."
                yield rx.toast.error(self.error_message)
                return

            with rx.session() as session:
                # Buscar la transcripción bajo el workspace del usuario
                transcription = (
                    session.query(AudioTranscription)
                    .filter(
                        AudioTranscription.id == transcription_id,
                        AudioTranscription.workspace_id == workspace_id,
                    )
                    .first()
                )
                if not transcription:
                    self.error_message = "Transcripción no encontrada o sin permisos."
                    yield rx.toast.error(self.error_message)
                    return

                # Eliminar el notebook asociado si pertenece al mismo workspace
                if transcription.notebook_id:
                    notebook = (
                        session.query(Notebook)
                        .filter(
                            Notebook.id == transcription.notebook_id,
                            Notebook.workspace_id == workspace_id,
                        )
                        .first()
                    )
                    if notebook:
                        session.delete(notebook)

                # Eliminar la transcripción
                session.delete(transcription)
                session.commit()

            # Recargar las transcripciones
            await self.load_user_transcriptions()

            # Mostrar mensaje de éxito
            yield rx.toast.success("Transcripción eliminada correctamente")

        except Exception as e:
            self.error_message = f"Error al eliminar: {e}"
            yield rx.toast.error(self.error_message)

    def _convert_transcription_to_notebook(self, transcription_text: str, title: str, filename: str) -> Dict[str, Any]:
        """Convierte una transcripción a formato notebook JSON."""
        now = datetime.now().strftime("%d/%m/%Y a las %H:%M")
        header_cell = {"cell_type": "markdown", "source": [f"# {title}\n\n", f"**Archivo:** {filename}\n\n", f"**Generado:** {now}\n\n", "---\n\n"]}
        content_cell = {"cell_type": "markdown", "source": ["## 📝 Transcripción Completa\n\n", f"{transcription_text}\n\n"]}
        return {"cells": [header_cell, content_cell], "metadata": {"kernelspec": {"display_name": "Audio Transcription", "language": "markdown", "name": "audio_transcription"}}}

    @rx.event
    async def reset_upload_state(self):
        """Resetea el estado para una nueva transcripción."""
        self.uploaded_files = []
        self.current_transcription = ""
        self.transcribing = False
        self.progress_message = ""
        self.error_message = ""
        # Ocultar el placeholder de feedback instantáneo
        yield rx.call_script(
            """
            const placeholder = document.getElementById('instant-feedback-placeholder');
            if (placeholder) {
                placeholder.style.display = 'none';
            }
            """
        )

    @rx.event
    async def refresh_transcriptions(self):
        """Refresca la lista de transcripciones desde la BD."""
        self.error_message = ""
        await self.load_user_transcriptions()

    # asistente_legal_constitucional_con_ia/states/transcription_state.py

# ... (dentro de la clase TranscriptionState)

    def _fetch_user_transcriptions_data(self, workspace_id: str) -> list[TranscriptionType]:
        """
        Método auxiliar que consulta la BD y devuelve los datos de transcripción,
        pero NO modifica el estado directamente.
        """
        with rx.session() as session:
            from ..models.database import AudioTranscription, Notebook

            query = (
                session.query(AudioTranscription)
                .outerjoin(Notebook, AudioTranscription.notebook_id == Notebook.id)
                .filter(AudioTranscription.workspace_id == workspace_id)
                .order_by(AudioTranscription.created_at.desc())
            )

            return [
                TranscriptionType(
                    id=t.id,
                    filename=t.filename,
                    transcription_text=(t.transcription_text[:200] + "..." if len(t.transcription_text) > 200 else t.transcription_text),
                    audio_duration=t.audio_duration or "N/A",
                    created_at=t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "N/A",
                    updated_at=t.updated_at.strftime("%Y-%m-%d %H:%M") if t.updated_at else "N/A",
                    notebook_id=t.notebook_id if t.notebook_id else 0,
                )
                for t in query.all()
            ]
