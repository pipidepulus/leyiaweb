import asyncio
import json
import logging
import os
import tempfile
import time
from typing import Any, Dict, List, Optional, TypedDict

import reflex as rx
from dotenv import load_dotenv
from openai import APIError, OpenAI

from asistente_legal_constitucional_con_ia.services.token_counter import (
    count_text_tokens,
)
from asistente_legal_constitucional_con_ia.util.scraper import (
    scrape_proyectos_recientes_camara,
)
from asistente_legal_constitucional_con_ia.util.text_extraction import (
    extract_text_from_bytes,
)
from asistente_legal_constitucional_con_ia.util.tools import (
    buscar_documento_legal,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("asistente_legal")

load_dotenv()

TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "buscar_documento_legal",
            "description": ("Herramienta de búsqueda avanzada para encontrar documentos legales colombianos " "(leyes, sentencias, gacetas) aplicando la estrategia más adecuada para cada tipo."),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "La consulta de búsqueda específica. Para Gacetas, usar solo el número y año, "
                            "ej: '758 de 2017'. Para Sentencias, el identificador completo, "
                            "ej: 'Sentencia C-123 de 2023'. "
                            "Para Leyes, el número y año, ej: 'Ley 1437 de 2011'."
                        ),
                    },
                    "tipo_documento": {
                        "type": "string",
                        "description": ("El tipo de documento legal a buscar. " "Debe ser uno de: 'gaceta', 'sentencia', 'ley'."),
                        "enum": ["gaceta", "sentencia", "ley"],
                    },
                    "sitio_preferido": {
                        "type": "string",
                        "description": (
                            "Opcional. Usar para priorizar dominios de alta autoridad. "
                            "Ej: 'corteconstitucional.gov.co' para sentencias o "
                            "'suin-juriscol.gov.co' para leyes. NO usar para gacetas."
                        ),
                    },
                },
                "required": ["query", "tipo_documento"],
            },
        },
    }
]
AVAILABLE_TOOLS = {
    "buscar_documento_legal": buscar_documento_legal,
}


class Message(TypedDict):
    role: str
    content: str


class FileInfo(TypedDict):
    file_id: str
    filename: str
    uploaded_at: float


class ChatState(rx.State):
    messages: list[Message] = []
    thread_id: Optional[str] = None
    file_info_list: list[FileInfo] = []
    session_files: list[FileInfo] = []
    processing: bool = False
    uploading: bool = False
    upload_progress: int = 0
    ocr_progress: str = ""  # (OCR removido)
    proyectos_recientes_df: str = ""
    assistant_id: str = os.getenv("ASSISTANT_ID_CONSTITUCIONAL", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    streaming_response: str = ""
    streaming: bool = False
    thinking_seconds: int = 0
    upload_error: str = ""
    focus_chat_input: bool = False
    current_question: str = ""
    chat_history: list = []
    current_answer: str = ""
    error_message: str = ""
    is_uploading: bool = False
    is_performing_ocr: bool = False
    uploaded_file_name: str = ""
    file_context: str = ""
    show_notebook_dialog: bool = False
    notebook_title: str = ""
    # nuevo: para poder cancelar el run en curso
    current_run_id: Optional[str] = None

    # límites para estabilidad
    max_chat_messages: int = 80  # conservar últimas 80 entradas en UI
    stream_min_chars: int = 120  # umbral de chars para actualizar streaming_response
    stream_min_interval_s: float = 0.15  # tiempo mínimo entre updates
    ocr_max_pages: int = 0  # OCR deshabilitado

    model_name: str = ""
    last_prompt_tokens: int = 0
    last_completion_tokens: int = 0
    last_total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    approx_output_tokens: int = 0
    # OCR completamente deshabilitado (removido). Mantener flag por compatibilidad si alguien la consulta.
    enable_ocr: bool = False

    # Propiedades computadas para formato de números
    @rx.var
    def formatted_last_total_tokens(self) -> str:
        """Retorna tokens de última respuesta formateados con separadores de miles"""
        return f"{self.last_total_tokens:,}"

    @rx.var
    def formatted_last_prompt_tokens(self) -> str:
        """Retorna tokens de entrada formateados"""
        return f"{self.last_prompt_tokens:,}"

    @rx.var
    def formatted_last_completion_tokens(self) -> str:
        """Retorna tokens de salida formateados"""
        return f"{self.last_completion_tokens:,}"

    @rx.var
    def formatted_total_tokens(self) -> str:
        """Retorna tokens totales formateados con separadores de miles"""
        return f"{self.total_tokens:,}"

    @rx.var
    def formatted_cost_usd(self) -> str:
        """Retorna costo formateado con 4 decimales"""
        return f"{self.cost_usd:.4f}"

    @rx.var
    def formatted_approx_output_tokens(self) -> str:
        """Retorna tokens aproximados formateados"""
        return f"{self.approx_output_tokens:,}"

    @staticmethod
    def get_client(api_key: str):
        if api_key:
            return OpenAI(api_key=api_key)
        return None

    def scroll_to_bottom(self):
        return rx.call_script(
            """
            (function(){
                const chat = document.getElementById('chat-messages-container');
                if (!chat) return;
                chat.scrollTop = chat.scrollHeight;
                requestAnimationFrame(()=>{ chat.scrollTop = chat.scrollHeight; });
                setTimeout(()=>{ chat.scrollTop = chat.scrollHeight; }, 120);
            })();
            """
        )

    def focus_input(self):
        return rx.call_script(
            """
            setTimeout(() => {
                const input = document.getElementById('chat-input-box');
                if (input) {
                    input.focus();
                    input.setSelectionRange(input.value.length, input.value.length);
                }
            }, 200);
            """
        )

    # Setter explícito para notebook_title para evitar dependencia de state_auto_setters
    @rx.event
    def set_notebook_title(self, value: str):
        self.notebook_title = value

    @rx.event
    def set_current_question(self, value: str):
        logger.info(f"set_current_question: '{value[:30]}...'")
        self.current_question = value

    @rx.var
    def has_api_keys(self) -> bool:
        return bool(self.assistant_id and self.openai_api_key)

    @rx.event(background=True)
    async def upload_timer(self):
        async with self:
            self.thinking_seconds = 0
        while self.uploading:
            await asyncio.sleep(1)
            async with self:
                self.thinking_seconds += 1

    @rx.var
    def proyectos_data(self) -> list[dict]:
        if not self.proyectos_recientes_df:
            return []
        try:
            return json.loads(self.proyectos_recientes_df)
        except json.JSONDecodeError:
            return []

    # _perform_ocr_with_progress eliminado (OCR deshabilitado)

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        logger.info(f"handle_upload: {len(files)} archivos recibidos")
        self.upload_error = ""
        if not files:
            self.upload_error = "No se seleccionaron archivos."
            yield rx.toast.error(self.upload_error)
            return

        self.uploading = True
        self.upload_progress = 0
        yield

        client = self.get_client(self.openai_api_key)
        if not client:
            self.upload_error = "Credenciales de OpenAI no configuradas."
            logger.error(self.upload_error)
            yield rx.toast.error(self.upload_error)
            self.uploading = False
            return

        for i, file in enumerate(files):
            if any(f["filename"] == file.name for f in self.file_info_list):
                self.upload_error = f"El archivo '{file.name}' ya fue subido."
                logger.warning(self.upload_error)
                yield rx.toast.error(self.upload_error)
                continue

            try:
                logger.info(f"Procesando archivo: {file.name}")
                upload_data = await file.read()
                # Primera pasada: extracción directa SIN OCR para PDFs (skip_ocr=True)
                extracted_text = extract_text_from_bytes(upload_data, file.name, skip_ocr=True)

                # Si es PDF y el texto es insuficiente, rechazar (OCR deshabilitado)
                if file.name.lower().endswith(".pdf") and (not extracted_text or len(extracted_text.strip()) < 100):
                    self.upload_error = f"El archivo '{file.name}' parece escaneado o sin texto digital. (OCR deshabilitado)"
                    logger.warning(self.upload_error)
                    yield rx.toast.warning("PDF escaneado sin texto. Sube un PDF con texto seleccionable.")
                    continue

                if not extracted_text or not extracted_text.strip():
                    self.upload_error = f"No se pudo extraer texto de '{file.name}'."
                    logger.warning(self.upload_error)
                    yield rx.toast.warning(self.upload_error)
                    continue

                original_name_no_ext = os.path.splitext(file.name)[0]
                temp_filename = f"{original_name_no_ext}_processed.txt"
                temp_dir = tempfile.gettempdir()
                tmp_path = os.path.join(temp_dir, temp_filename)

                with open(tmp_path, "w", encoding="utf-8") as tmp_file:
                    tmp_file.write(extracted_text)

                try:
                    response = await asyncio.to_thread(self._upload_file_to_openai, client, tmp_path)

                    self.file_info_list.append({"file_id": response.id, "filename": file.name, "uploaded_at": time.time()})
                    self.session_files.append({"file_id": response.id, "filename": file.name, "uploaded_at": time.time()})

                    logger.info(f"'{file.name}' subido con id {response.id}.")
                    self.upload_error = ""
                    yield rx.toast.success(f"'{file.name}' procesado y subido.")
                except APIError as e:
                    self.upload_error = f"Error al subir '{file.name}': {getattr(e, 'message', str(e))}"
                    logger.error(self.upload_error)
                    yield rx.toast.error(self.upload_error)
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

            except Exception as e:
                self.uploading = False
                self.is_performing_ocr = False
                self.ocr_progress = ""
                self.upload_error = f"Error procesando '{file.name}': {e}"
                logger.error(self.upload_error)
                yield rx.toast.error(self.upload_error)

            self.upload_progress = round((i + 1) / len(files) * 100)
            yield

        self.uploading = False
        self.is_performing_ocr = False
        self.ocr_progress = ""
        logger.info("handle_upload: proceso terminado")
        yield

    def _upload_file_to_openai(self, client: OpenAI, path: str):
        with open(path, "rb") as f_obj:
            return client.files.create(file=f_obj, purpose="assistants")

    @rx.event(background=True)
    async def delete_file(self, file_id: str):
        client = self.get_client(self.openai_api_key)
        if not client:
            yield rx.toast.error("Credenciales de OpenAI no configuradas.")
            return

        filename = next((f["filename"] for f in self.file_info_list if f["file_id"] == file_id), "archivo")
        try:
            await asyncio.to_thread(client.files.delete, file_id)
            # FIX: en eventos background, modificar estado dentro de `async with self:`
            async with self:
                self.file_info_list = [f for f in self.file_info_list if f["file_id"] != file_id]
                self.session_files = [f for f in self.session_files if f["file_id"] != file_id]
            yield rx.toast.success(f"'{filename}' eliminado.")
        except APIError as e:
            yield rx.toast.error(f"Error eliminando '{filename}': {getattr(e, 'message', str(e))}")

    @rx.event(background=True)
    async def scrape_proyectos(self):
        async with self:
            self.proyectos_recientes_df = ""
        df = await asyncio.to_thread(scrape_proyectos_recientes_camara, 15)
        async with self:
            if df is not None:
                self.proyectos_recientes_df = df.to_json(orient="records")
            else:
                self.proyectos_recientes_df = "[]"
                yield rx.toast.error("No se pudieron obtener los proyectos.")

    @rx.event(background=True)
    async def thinking_timer(self):
        async with self:
            self.thinking_seconds = 0
        logger.info(f"thinking_timer: Iniciado. self.processing={self.processing}")

        start_time = time.time()
        max_timeout = 600

        while self.processing:
            current_time = time.time()
            if current_time - start_time > max_timeout:
                logger.warning(f"thinking_timer: Timeout después de {max_timeout}s")
                async with self:
                    self.processing = False
                    self.streaming = False
                    self.streaming_response = "Error: Tiempo de respuesta agotado."
                    if self.messages:
                        self.messages[-1]["content"] = self.streaming_response
                break

            await asyncio.sleep(1)
            async with self:
                self.thinking_seconds += 1

        logger.info(f"thinking_timer: Detenido. self.processing={self.processing}")

    def _trim_messages(self, max_messages: int | None = None):
        try:
            limit = max_messages or self.max_chat_messages
            if len(self.messages) > limit:
                self.messages = self.messages[-limit:]
        except Exception:
            pass

    # === NUEVO: helpers de modelo, costo y usage ===

    async def _ensure_model_name(self, client: OpenAI):
        """Obtiene y cachea el modelo del Assistant para costos/estimaciones."""
        # Si ya hay modelo cacheado, no hagas nada
        if self.model_name:
            return

        # Si no hay cliente o assistant_id, usa fallback
        if not client or not self.assistant_id:
            async with self:
                if not self.model_name:
                    self.model_name = "gpt-4o-mini"
            return

        # Recuperar el modelo fuera del context manager
        try:
            assistant = await asyncio.to_thread(client.beta.assistants.retrieve, self.assistant_id)
            model = getattr(assistant, "model", "") or "gpt-4o-mini"
        except Exception:
            model = "gpt-4o-mini"

        # Asignar al estado dentro del context manager
        async with self:
            if not self.model_name:
                self.model_name = model

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """USD aproximados por 1M tokens (ajusta a tus precios)."""
        pricing = {
            "gpt-4o": (5.00, 15.00),
            "gpt-4o-mini": (0.150, 0.600),
            "gpt-4.1": (5.00, 15.00),
            "gpt-4.1-mini": (2.400, 3.600),
            "gpt-4-turbo": (10.00, 30.00),
            "gpt-3.5-turbo": (0.50, 1.50),
        }
        in_m, out_m = pricing.get(model, pricing["gpt-4o-mini"])
        return (input_tokens * in_m + output_tokens * out_m) / 1_000_000.0

    def _commit_usage(self, input_tokens: int, output_tokens: int):
        self.last_prompt_tokens = int(input_tokens or 0)
        self.last_completion_tokens = int(output_tokens or 0)
        self.last_total_tokens = self.last_prompt_tokens + self.last_completion_tokens
        self.total_prompt_tokens += self.last_prompt_tokens
        self.total_completion_tokens += self.last_completion_tokens
        self.total_tokens += self.last_total_tokens
        self.cost_usd += self._estimate_cost(self.model_name or "gpt-4o-mini", self.last_prompt_tokens, self.last_completion_tokens)

    def _apply_usage_object(self, usage: Any):
        """Acepta usage dict/obj y consolida. Soporta input/output y prompt/completion."""
        if not usage:
            return
        try:
            # 1) intentar input/output (Assistants v2)
            input_tokens = getattr(usage, "input_tokens", None)
            output_tokens = getattr(usage, "output_tokens", None)

            # 2) fallback a dict
            if isinstance(usage, dict):
                if input_tokens is None:
                    input_tokens = usage.get("input_tokens")
                if output_tokens is None:
                    output_tokens = usage.get("output_tokens")

            # 3) fallback a prompt/completion (algunos despliegues)
            if input_tokens is None:
                input_tokens = getattr(usage, "prompt_tokens", None)
            if output_tokens is None:
                output_tokens = getattr(usage, "completion_tokens", None)

            if isinstance(usage, dict):
                if input_tokens is None:
                    input_tokens = usage.get("prompt_tokens")
                if output_tokens is None:
                    output_tokens = usage.get("completion_tokens")

            input_tokens = int(input_tokens or 0)
            output_tokens = int(output_tokens or 0)

            # Registrar en logs para verificar
            logger.info(f"USAGE aplicado - input: {input_tokens}, output: {output_tokens}, modelo: {self.model_name}")

            self._commit_usage(input_tokens, output_tokens)
        except Exception as e:
            logger.warning(f"No se pudo aplicar usage: {e}")

    @rx.event
    def reset_token_counters(self):
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_total_tokens = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.cost_usd = 0.0
        self.approx_output_tokens = 0

    @rx.event
    def send_message(self, form_data: dict):
        user_prompt = self.current_question.strip()
        logger.info(f"send_message: INICIO. prompt='{user_prompt}'")
        if not user_prompt or self.processing:
            logger.warning("Prompt vacío o ya procesando.")
            return

        self.current_question = ""
        yield rx.call_script("const el=document.getElementById('chat-input-box'); if(el){el.value=''}")

        if not self.has_api_keys:
            msg = "Las credenciales de OpenAI no están configuradas."
            logger.error(msg)
            return rx.toast.error(msg)

        # Mostrar mensaje del usuario
        self.processing = True
        self.streaming = True
        self.streaming_response = ""
        self.thinking_seconds = 0
        self.messages.append({"role": "user", "content": user_prompt})
        self._trim_messages()
        yield
        yield self.scroll_to_bottom()

        # Placeholder del asistente
        self.messages.append({"role": "assistant", "content": "Estoy pensando..."})
        self._trim_messages()
        yield

        # Iniciar timers/proceso
        yield ChatState.thinking_timer
        yield ChatState.generate_response_streaming

    @rx.event(background=True)
    async def simple_background_test(self):
        logger.info("simple_background_test: INICIO Y FIN")
        async with self:
            if self.messages:
                self.messages[-1]["content"] = "Respuesta de prueba"
            self.processing = False
            self.streaming = False
            self.thinking_seconds = 0

    @rx.event(background=True)
    async def generate_response_streaming(self):
        logger.info((f"DEBUG: Estado actual - session_files: {len(self.session_files)}, " f"file_info_list: {len(self.file_info_list)}"))
        for fi in self.session_files:
            logger.info(f"DEBUG: Archivo en sesión: {fi['filename']} -> {fi['file_id']}")
        logger.info(f"generate_response_streaming: INICIO. thread_id={self.thread_id}")
        client = self.get_client(self.openai_api_key)

        try:

            await self._ensure_model_name(client)

            last_user_message = next((m["content"] for m in reversed(self.messages) if m["role"] == "user"), None)
            if not last_user_message:
                raise ValueError("No se encontró el último mensaje del usuario.")

            # Snapshot de archivos actuales
            current_files = self.session_files[-3:].copy()

            # Mantener un único thread por sesión, crear solo si no existe
            if not self.thread_id:
                thread = await asyncio.to_thread(client.beta.threads.create)
                async with self:
                    self.thread_id = thread.id
                logger.info(f"Thread nuevo creado: {self.thread_id}")

            logger.info(f"DEBUG THREAD - thread_id: {self.thread_id}")

            # Inspección opcional de mensajes previos del thread (debug)
            try:
                existing_messages = await asyncio.to_thread(client.beta.threads.messages.list, thread_id=self.thread_id, limit=3)
                logger.debug(f"DEBUG THREAD - mensajes existentes: {len(existing_messages.data)}")
            except Exception as e:
                logger.debug(f"Error verificando mensajes del thread: {e}")

            attachments = [{"file_id": fi["file_id"], "tools": [{"type": "file_search"}]} for fi in current_files]

            logger.info(f"DEBUG ARCHIVO - session_files: {len(self.session_files)}")
            logger.info(f"DEBUG ARCHIVO - current_files: {len(current_files)}")
            logger.info(f"DEBUG ARCHIVO - attachments: {len(attachments)}")
            files_debug = [f"{fi['filename']} ({fi['file_id']})" for fi in current_files]
            logger.info((f"DEBUG: Archivos que se van a usar: {files_debug}" if files_debug else "DEBUG: No se enviarán archivos"))

            if current_files:
                file_names = [fi["filename"] for fi in current_files]
                file_list = ", ".join(file_names)
                message_content = f"{last_user_message}\n\n[Archivos adjuntos: {file_list}]"
            else:
                message_content = f"{last_user_message}\n\n[SISTEMA: No hay archivos subidos]"

            await asyncio.to_thread(
                client.beta.threads.messages.create,
                thread_id=self.thread_id,
                role="user",
                content=message_content,
                attachments=attachments,
            )

            tools_for_run = TOOLS_DEFINITION.copy()
            if current_files:
                tools_for_run.append({"type": "file_search"})
            else:
                logger.info("Sin archivos de sesión: NO habilitando file_search")

            try:
                run_stream = await asyncio.wait_for(
                    asyncio.to_thread(
                        client.beta.threads.runs.create,
                        thread_id=self.thread_id,
                        assistant_id=self.assistant_id,
                        tools=tools_for_run,
                        stream=True,
                    ),
                    timeout=300,
                )
            except asyncio.TimeoutError:
                logger.error("Timeout creando run de OpenAI")
                async with self:
                    if self.messages:
                        self.messages[-1]["content"] = "Error: La respuesta tardó demasiado."
                    self.processing = False
                    self.streaming = False
                return

            logger.info("generate_response_streaming: Run creado con stream=True.")

            first_chunk_processed = False
            accumulated_response = ""
            accumulated_content = ""
            last_update_time = time.time()
            last_scroll_time = 0.0
            usage_applied = False

            while True:
                should_break_outer_loop = False

                for event in run_stream:
                    # Intentar capturar el run_id al inicio
                    try:
                        ev = getattr(event, "event", "")
                        data = getattr(event, "data", None)
                        if ev.startswith("thread.run.") and data is not None and getattr(data, "id", None):
                            async with self:
                                self.current_run_id = data.id
                    except Exception:
                        pass

                    if event.event == "thread.message.delta":
                        delta = event.data.delta
                        if delta.content:
                            text_chunk = delta.content[0].text.value
                            if text_chunk:
                                accumulated_content += text_chunk
                                current_time = time.time()
                                should_update = len(accumulated_content) >= self.stream_min_chars or "\n" in text_chunk or (current_time - last_update_time) >= self.stream_min_interval_s

                                if should_update:
                                    async with self:
                                        if not first_chunk_processed:
                                            # vaciar placeholder solo al final; mostrar stream en streaming_response
                                            first_chunk_processed = True
                                        accumulated_response += accumulated_content
                                        self.streaming_response = accumulated_response
                                        self.approx_output_tokens = count_text_tokens(self.streaming_response, self.model_name or "gpt-4o-mini")
                                    yield

                                    # scroll con moderación
                                    if (current_time - last_scroll_time) >= 0.8 or len(accumulated_response) % 1000 == 0:
                                        yield self.scroll_to_bottom()
                                        last_scroll_time = current_time

                                    accumulated_content = ""
                                    last_update_time = current_time

                    elif event.event == "thread.run.requires_action":
                        run_id = event.data.id
                        async with self:
                            self.current_run_id = run_id

                        tool_outputs = []
                        # feedback ligero para UI
                        try:
                            first_args = json.loads(event.data.required_action.submit_tool_outputs.tool_calls[0].function.arguments)
                            first_query = first_args.get("query", "...")
                            async with self:
                                self.streaming_response = f"Buscando: '{first_query}'..."
                            yield
                        except Exception:
                            pass

                        for tool_call in event.data.required_action.submit_tool_outputs.tool_calls:
                            function_name = tool_call.function.name
                            arguments = json.loads(tool_call.function.arguments)
                            if function_name in AVAILABLE_TOOLS:
                                try:
                                    output = await asyncio.wait_for(
                                        asyncio.to_thread(AVAILABLE_TOOLS[function_name], **arguments),
                                        timeout=120,
                                    )
                                except asyncio.TimeoutError:
                                    logger.error(f"Timeout ejecutando herramienta {function_name}")
                                    output = f"Error: La herramienta {function_name} tardó demasiado."
                                except Exception as e:
                                    logger.error(f"Error en herramienta {function_name}: {e}")
                                    output = f"Error ejecutando {function_name}: {str(e)}"
                                tool_outputs.append({"tool_call_id": tool_call.id, "output": output})

                        if tool_outputs:
                            run_stream = await asyncio.to_thread(
                                client.beta.threads.runs.submit_tool_outputs,
                                thread_id=self.thread_id,
                                run_id=run_id,
                                tool_outputs=tool_outputs,
                                stream=True,
                            )
                            break

                    elif event.event in ["thread.run.completed", "thread.run.failed", "error"]:
                        if event.event == "thread.run.completed":
                            # NUEVO: usage directo desde el evento
                            try:
                                usage = getattr(getattr(event, "data", None), "usage", None)
                                if usage:
                                    async with self:
                                        self._apply_usage_object(usage)
                                    usage_applied = True
                            except Exception:
                                pass
                        else:
                            logger.error(f"Stream: Run fallido. Evento: {event.event}")
                            async with self:
                                self.streaming_response = "Repite la solicitud por favor."
                        should_break_outer_loop = True
                        break

                if should_break_outer_loop:
                    break

            # Actualizar cualquier contenido restante
            if accumulated_content:
                async with self:
                    accumulated_response += accumulated_content
                    self.streaming_response = accumulated_response
                    self.approx_output_tokens = count_text_tokens(self.streaming_response, self.model_name or "gpt-4o-mini")
                yield

            # NUEVO: recuperar usage si no vino en el stream
            if not usage_applied and self.thread_id and self.current_run_id:
                try:
                    run_obj = await asyncio.to_thread(client.beta.threads.runs.retrieve, self.thread_id, self.current_run_id)
                    usage = getattr(run_obj, "usage", None)
                    if usage:
                        async with self:
                            self._apply_usage_object(usage)
                except Exception as e:
                    logger.debug(f"No se pudo recuperar usage del run: {e}")

            # Consolidar streaming_response dentro del mensaje
            async with self:
                if self.messages:
                    self.messages[-1]["content"] = self.streaming_response or "Sin contenido."
                self.processing = False
                self.streaming = False
                self.thinking_seconds = 0
                self.focus_chat_input = True
                self.current_run_id = None
                self.approx_output_tokens = 0
            yield
            yield self.scroll_to_bottom()
            yield self.focus_input()
            yield ChatState.reset_focus_trigger

            logger.info("generate_response_streaming: Bucle principal completado.")

        except Exception as e:
            logger.error(f"Error en generate_response_streaming: {e}", exc_info=True)
            async with self:
                if self.messages:
                    self.messages[-1]["content"] = f"Error inesperado: {e}"
                self.processing = False
                self.streaming = False
                self.current_run_id = None
        finally:
            # no yields aquí adicionales, ya se hizo consolidación o error
            pass

    @rx.event
    def reset_focus_trigger(self):
        self.focus_chat_input = False

    @rx.event(background=True)
    async def abort_current_run(self):
        """Cancela el run actual si está en curso para ahorrar costo/recursos."""
        if not (self.thread_id and self.current_run_id):
            return
        client = self.get_client(self.openai_api_key)
        if not client:
            return
        try:
            await asyncio.to_thread(client.beta.threads.runs.cancel, self.thread_id, self.current_run_id)
            logger.info(f"Run {self.current_run_id} cancelado.")
        except Exception as e:
            logger.warning(f"No se pudo cancelar run {self.current_run_id}: {e}")
        finally:
            async with self:
                self.current_run_id = None

    @rx.event
    def limpiar_chat(self):
        # Cancelar run en curso y limpiar archivos en background
        yield ChatState.abort_current_run
        yield ChatState.cleanup_session_files

        self.messages = [
            {
                "role": "assistant",
                "content": "¡Hola! Soy LeyIA, tu Asistente Legal. " "Puedes hacerme una pregunta o subir un " "documento para analizarlo.",
            }
        ]
        self.thread_id = None
        self.file_info_list = []
        self.processing = False
        self.uploading = False
        self.upload_progress = 0
        self.ocr_progress = ""
        self.streaming_response = ""
        self.streaming = False
        self.thinking_seconds = 0
        self.upload_error = ""
        self.focus_chat_input = False
        self.current_question = ""
        self.chat_history = []
        self.current_run_id = None
        logger.info("ChatState.limpiar_chat ejecutado.")

    @rx.event
    def logout_and_cleanup(self):
        """Limpia el chat y hace logout del usuario."""
        from ..auth_config import lauth
        # Primero limpiamos el chat
        yield ChatState.limpiar_chat
        # Luego hacemos el logout
        yield lauth.LocalAuthState.do_logout  # type: ignore[attr-defined]

    @rx.event
    async def show_create_notebook_dialog(self):
        if len(self.messages) < 2:
            return rx.toast.error("Necesitas al menos una conversación para crear un notebook.")
        self.show_notebook_dialog = True

    @rx.event
    def hide_create_notebook_dialog(self):
        self.show_notebook_dialog = False

    @rx.event
    async def create_notebook_from_current_chat(self):
        if not self.notebook_title.strip():
            yield rx.toast.error("El título no puede estar vacío.")
            return

        try:
            title_to_use = self.notebook_title.strip()
            from ..states.notebook_state import NotebookState  # evitar import circular

            # Delegar: usar auth local y guardar con el owner correcto
            yield NotebookState.create_notebook_from_chat(title_to_use, self.messages)

            # Cierra el diálogo y limpia
            self.show_notebook_dialog = False
            self.notebook_title = ""
        except Exception as e:
            yield rx.toast.error(f"Error creando notebook: {str(e)}")

    @rx.event
    async def suggest_notebook_creation(self):
        if len(self.messages) >= 4 and not self.processing:
            return rx.toast.info("💡 ¿Quieres guardar esta conversación como notebook?", duration=5000)

    @rx.event
    def limpiar_chat_y_redirigir(self):
        yield ChatState.abort_current_run
        yield ChatState.cleanup_session_files
        self.limpiar_chat()
        return rx.redirect("/")

    @rx.event
    def initialize_chat(self):
        if not self.messages:
            self.messages = [
                {
                    "role": "assistant",
                    "content": "¡Hola! Soy LeyIA, tu Asistente Legal. " "Puedes hacerme una pregunta o subir un " "documento para analizarlo.",
                }
            ]
        if self.has_api_keys:
            return [ChatState.monitor_session_health, ChatState.cleanup_by_timestamp]

    @rx.event
    def initialize_chat_simple(self):
        if not self.messages:
            self.messages = [
                {
                    "role": "assistant",
                    "content": "¡Hola! Soy LeyIA, tu Asistente Legal. " "Puedes hacerme una pregunta o subir un " "documento para analizarlo.",
                }
            ]

    @rx.event(background=True)
    async def cleanup_session_files(self):
        """Limpia archivos de la sesión en OpenAI (background para no bloquear UI)."""
        client = self.get_client(self.openai_api_key)
        if client and self.session_files:
            for file_info in list(self.session_files):
                try:
                    await asyncio.to_thread(client.files.delete, file_info["file_id"])
                except APIError:
                    pass
            async with self:
                self.session_files = []

    @rx.event(background=True)
    async def monitor_session_health(self):
        logger.info("Monitor de sesión iniciado")
        while True:
            await asyncio.sleep(300)
            if self.session_files and self.thread_id:
                client = self.get_client(self.openai_api_key)
                if client:
                    try:
                        await asyncio.to_thread(client.beta.threads.retrieve, self.thread_id)
                        logger.info(f"Thread {self.thread_id} activo - {len(self.session_files)} archivos")
                    except APIError as e:
                        if "No thread found" in str(e) or getattr(e, "status_code", None) == 404:
                            logger.warning(f"Thread {self.thread_id} no encontrado. Limpiando archivos...")
                            await self._cleanup_orphaned_files()
                        else:
                            logger.error(f"Error verificando thread: {e}")
                    except Exception as e:
                        logger.error(f"Error de conexión verificando thread: {e}")

    async def _cleanup_orphaned_files(self):
        client = self.get_client(self.openai_api_key)
        if client and self.session_files:
            logger.info(f"Limpiando {len(self.session_files)} archivos huérfanos")
            for file_info in list(self.session_files):
                try:
                    await asyncio.to_thread(client.files.delete, file_info["file_id"])
                    logger.info(f"Archivo huérfano eliminado: {file_info['filename']}")
                except APIError:
                    pass
            async with self:
                self.session_files = []
                self.thread_id = None
                logger.info("Estado de sesión limpiado por thread huérfano")

    @rx.event(background=True)
    async def cleanup_by_timestamp(self):
        logger.info("Monitor de limpieza por timestamp iniciado")
        while True:
            await asyncio.sleep(3600)
            if self.session_files:
                current_time = time.time()
                old_files = []
                for file_info in self.session_files:
                    file_age = current_time - file_info.get("uploaded_at", current_time)
                    if file_age > 7200:
                        old_files.append(file_info)

                if old_files:
                    logger.info(f"Encontrados {len(old_files)} archivos antiguos para limpiar")
                    client = self.get_client(self.openai_api_key)
                    if client:
                        for file_info in old_files:
                            try:
                                await asyncio.to_thread(client.files.delete, file_info["file_id"])
                                logger.info(f"Archivo antiguo eliminado: {file_info['filename']}")
                            except APIError:
                                pass
                        async with self:
                            self.session_files = [f for f in self.session_files if f not in old_files]

    def _convert_chat_to_notebook(self, chat_messages: List[Dict[str, str]], title: str) -> Dict[str, Any]:
        from datetime import datetime

        cells = []
        cells.append(
            {
                "cell_type": "markdown",
                "source": [f"# {title}\n\n", f"*Notebook generado automáticamente el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}*\n\n", "---\n\n"],
            }
        )

        for i, message in enumerate(chat_messages):
            if message["role"] == "user":
                cells.append(
                    {
                        "cell_type": "markdown",
                        "source": [f"## 🙋 Consulta {(i // 2) + 1}\n\n", f"{message['content']}\n\n"],
                    }
                )
            elif message["role"] == "assistant":
                cells.append(
                    {
                        "cell_type": "markdown",
                        "source": ["### 🤖 Respuesta del Asistente\n\n", f"{message['content']}\n\n", "---\n\n"],
                    }
                )

        return {
            "cells": cells,
            "metadata": {
                "kernelspec": {
                    "display_name": "Legal Analysis",
                    "language": "markdown",
                    "name": "legal_analysis",
                }
            },
        }
