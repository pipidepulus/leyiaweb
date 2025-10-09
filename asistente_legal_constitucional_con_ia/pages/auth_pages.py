"""Páginas personalizadas de autenticación (login y registro).

Estas páginas usan los estados de reflex_local_auth pero con diseño personalizado.
"""

import reflex as rx
from ..auth_config import lauth


def login_error() -> rx.Component:
    """Renderiza el mensaje de error de login."""
    return rx.cond(
        lauth.LoginState.error_message != "",  # type: ignore[attr-defined]
        rx.callout(
            lauth.LoginState.error_message,  # type: ignore[attr-defined]
            icon="triangle_alert",
            color_scheme="red",
            role="alert",
            width="100%",
        ),
    )


def custom_login_form() -> rx.Component:
    """Formulario de login personalizado."""
    return rx.form(
        rx.vstack(
            rx.heading("Iniciar Sesión", size="6", margin_bottom="0.5em"),
            login_error(),
            rx.text("Usuario", size="2", weight="medium", margin_bottom="0.3em"),
            rx.input(
                placeholder="Usuario",
                name="username",
                width="100%",
                size="3"
            ),
            rx.text("Contraseña", size="2", weight="medium", margin_bottom="0.3em", margin_top="0.5em"),
            rx.input(
                type="password",
                placeholder="Contraseña",
                name="password",
                width="100%",
                size="3"
            ),
            rx.button(
                "Entrar",
                type="submit",
                width="100%",
                size="3",
                margin_top="1em"
            ),
            rx.center(
                rx.link(
                    "Registrarse",
                    on_click=lauth.RegistrationState.redir,  # type: ignore[attr-defined]
                    color_scheme="blue",
                    size="2"
                ),
                width="100%",
                margin_top="0.5em"
            ),
            width="100%",
            spacing="2"
        ),
        on_submit=lauth.LoginState.on_submit,  # type: ignore[attr-defined]
        width="100%"
    )


def custom_login_page() -> rx.Component:
    """Página de login personalizada."""
    return rx.center(
        rx.cond(
            lauth.LoginState.is_hydrated,  # type: ignore[attr-defined]
            rx.card(
                rx.vstack(
                    rx.heading(
                        "Bienvenido",
                        size="8",
                        weight="bold",
                        margin_bottom="0.3em",
                        color="var(--accent-9)"
                    ),
                    rx.text(
                        "Inicia sesión en tu cuenta",
                        size="3",
                        color="var(--gray-11)",
                        margin_bottom="1.5em"
                    ),
                    custom_login_form(),
                    spacing="2",
                    width="100%",
                    align_items="stretch"
                ),
                max_width="400px",
                padding="2em",
                box_shadow="0 8px 32px rgba(0, 0, 0, 0.1)",
            ),
        ),
        height="100vh",
        width="100vw",
        background="linear-gradient(135deg, #c9d1f5 0%, #d7c8e8 100%)",
        padding="2em"
    )


def register_error() -> rx.Component:
    """Renderiza el mensaje de error de registro."""
    return rx.cond(
        lauth.RegistrationState.error_message != "",  # type: ignore[attr-defined]
        rx.callout(
            lauth.RegistrationState.error_message,  # type: ignore[attr-defined]
            icon="triangle_alert",
            color_scheme="red",
            role="alert",
            width="100%",
        ),
    )


def custom_register_form() -> rx.Component:
    """Formulario de registro personalizado."""
    return rx.form(
        rx.vstack(
            rx.heading("Crear Cuenta", size="6", margin_bottom="0.5em"),
            register_error(),
            rx.text("Usuario", size="2", weight="medium", margin_bottom="0.3em"),
            rx.input(
                placeholder="Usuario",
                name="username",
                width="100%",
                size="3"
            ),
            rx.text("Contraseña", size="2", weight="medium", margin_bottom="0.3em", margin_top="0.5em"),
            rx.input(
                type="password",
                placeholder="Contraseña",
                name="password",
                width="100%",
                size="3"
            ),
            rx.text("Confirmar Contraseña", size="2", weight="medium", margin_bottom="0.3em", margin_top="0.5em"),
            rx.input(
                type="password",
                placeholder="Confirmar Contraseña",
                name="confirm_password",
                width="100%",
                size="3"
            ),
            rx.button(
                "Registrarse",
                type="submit",
                width="100%",
                size="3",
                margin_top="1em"
            ),
            rx.center(
                rx.link(
                    "¿Ya tienes cuenta? Inicia sesión",
                    href="/login",
                    color_scheme="blue",
                    size="2"
                ),
                width="100%",
                margin_top="0.5em"
            ),
            width="100%",
            spacing="2"
        ),
        on_submit=lauth.RegistrationState.handle_registration,  # type: ignore[attr-defined]
        width="100%"
    )


def custom_register_page() -> rx.Component:
    """Página de registro personalizada."""
    return rx.center(
        rx.cond(
            lauth.RegistrationState.success,  # type: ignore[attr-defined]
            rx.card(
                rx.vstack(
                    rx.icon("circle_check", size=50, color="green"),
                    rx.heading("¡Registro Exitoso!", size="7", margin_top="0.5em"),
                    rx.text("Tu cuenta ha sido creada correctamente.", color="var(--gray-11)"),
                    rx.button(
                        "Ir a Login",
                        on_click=lambda: rx.redirect("/login"),
                        size="3",
                        margin_top="1em"
                    ),
                    spacing="3",
                    align_items="center"
                ),
                max_width="400px",
                padding="2em",
            ),
            rx.card(
                rx.vstack(
                    rx.heading(
                        "Crear Cuenta",
                        size="8",
                        weight="bold",
                        margin_bottom="0.3em",
                        color="var(--accent-9)"
                    ),
                    rx.text(
                        "Regístrate para comenzar",
                        size="3",
                        color="var(--gray-11)",
                        margin_bottom="1.5em"
                    ),
                    custom_register_form(),
                    spacing="2",
                    width="100%",
                    align_items="stretch"
                ),
                max_width="400px",
                padding="2em",
                box_shadow="0 8px 32px rgba(0, 0, 0, 0.1)",
            ),
        ),
        height="100vh",
        width="100vw",
        background="linear-gradient(135deg, #c9d1f5 0%, #d7c8e8 100%)",
        padding="2em"
    )
