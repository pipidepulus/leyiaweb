import reflex as rx

from ..states.chat_state import ChatState


def token_meter() -> rx.Component:
    # ...existing code...
    return rx.box(
        rx.card(
            rx.hstack(
                # Modelo
                rx.text("Modelo:", weight="bold", size="2"),
                rx.badge(
                    rx.cond(ChatState.model_name == "", "desconocido", ChatState.model_name),
                    variant="soft",
                    size="2",
                ),
                rx.spacer(),
                # Última respuesta
                rx.badge(
                    rx.hstack(
                        rx.text("Última:", size="2"),
                        rx.text(ChatState.formatted_last_total_tokens, size="2"),
                        rx.text("tok", size="1"),
                        spacing="1",
                        align="center",
                    ),
                    color_scheme="blue",
                    size="2",
                ),
                rx.badge(
                    rx.hstack(
                        rx.text("In:", size="2"), 
                        rx.text(ChatState.formatted_last_prompt_tokens, size="2"), 
                        spacing="1"
                    ),
                    variant="soft",
                    size="2",
                ),
                rx.badge(
                    rx.hstack(
                        rx.text("Out:", size="2"), 
                        rx.text(ChatState.formatted_last_completion_tokens, size="2"), 
                        spacing="1"
                    ),
                    variant="soft",
                    size="2",
                ),
                rx.spacer(),
                # Acumulado
                rx.badge(
                    rx.hstack(
                        rx.text("Acumulado:", size="2"),
                        rx.text(ChatState.formatted_total_tokens, size="2"),
                        rx.text("tok", size="1"),
                        spacing="1",
                        align="center",
                    ),
                    color_scheme="green",
                    size="2",
                ),
                # Costo
                rx.badge(
                    rx.hstack(
                        rx.text("Costo aprox: $", size="2"),
                        rx.text(ChatState.formatted_cost_usd, size="2"),
                        spacing="1",
                        align="center",
                    ),
                    color_scheme="orange",
                    size="2",
                ),
                # En vivo
                rx.cond(
                    ChatState.approx_output_tokens > 0,
                    rx.badge(
                        rx.hstack(
                            rx.text("En vivo Out≈", size="2"), 
                            rx.text(ChatState.formatted_approx_output_tokens, size="2"), 
                            spacing="1", 
                            align="center"
                        ),
                        variant="soft",
                        size="2",
                    ),
                    rx.fragment(),
                ),
                rx.spacer(),
                rx.button("Reiniciar", size="2", on_click=ChatState.reset_token_counters, variant="surface"),
                spacing="3",
                align="center",
                width="100%",
            ),
            padding="0.6rem",
            width="100%",
            background="linear-gradient(135deg, #c9d1f5 0%, #d7c8e8 100%)",
            border_bottom="1px solid rgba(255, 255, 255, 0.3)",
        ),
        # Fija el medidor arriba y por encima del scroll de los mensajes
        position="sticky",
        top="0px",
        z_index=10,
        width="100%",
        background="linear-gradient(135deg, #c9d1f5 0%, #d7c8e8 100%)",
    )