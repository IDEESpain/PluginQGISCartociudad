try:
    from urllib.error import URLError
except ImportError:
    from urllib2 import URLError


# Mapeo de códigos de error de QtNetwork a mensajes descriptivos
ERROR_MESSAGES = {
    0: "Sin error",
    1: "Error de conexión: el servidor rechazó la conexión",
    2: "Error de conexión: el servidor cerró la conexión inesperadamente",
    3: "Error de conexión: no se pudo resolver el nombre del servidor",
    4: "Error de tiempo de espera: el servidor tardó demasiado en responder",
    6: "Error de seguridad SSL: problema con el certificado del servidor",
    7: "Error de red temporal: intente de nuevo",
    8: "Error de protocolo: respuesta no válida del servidor",
}

# Mapeo cuando llega como STRING 
STRING_ERROR_MAP = {
    "RemoteHostClosedError": 2,
    "ConnectionRefusedError": 1,
    "HostNotFoundError": 3,
    "TimeoutError": 4,
    "SslHandshakeFailedError": 6,
}


def get_friendly_error(error) -> str:
    print("DEBUG ERROR:", error, type(error))

    if isinstance(error, URLError):
        return _get_url_error_message(error)

    if isinstance(error, int):
        return _get_error_message(error)

    if isinstance(error, str):
        for key, code in STRING_ERROR_MAP.items():
            if key in error:
                return _get_error_message(code)
        return f"Error de conexión: {error}"

    return f"Error desconocido: {error}"


def _get_error_message(error_code) -> str:
    error_str = str(error_code)
    if "RemoteHostClosedError" in error_str:
        error_code = 2
    elif "ConnectionRefusedError" in error_str:
        error_code = 1
    elif "HostNotFoundError" in error_str:
        error_code = 3
    elif "TimeoutError" in error_str:
        error_code = 4
    elif "SslHandshakeFailedError" in error_str:
        error_code = 6

    msg = ERROR_MESSAGES.get(error_code)

    if msg:
        return f"{msg}\nCompruebe su conexión o inténtelo de nuevo."

    return f"Error de conexión desconocido. ({error_str})"


def _get_url_error_message(error: Exception) -> str:
    error_msg = str(error).lower()

    # Intenta obtener código HTTP real
    code = getattr(error, "code", None)
    if code == 404:
        return "Error 404: recurso no encontrado"
    elif code == 403:
        return "Error 403: acceso denegado"
    elif code == 500:
        return "Error 500: error interno del servidor"
    elif code == 503:
        return "Error 503: servidor no disponible"

   
    reason = getattr(error, "reason", None)
    reason_str = str(reason).lower() if reason else error_msg

    if "timeout" in reason_str:
        return "Error de tiempo de espera: el servidor tardó demasiado en responder (timeout)"
    elif "connection refused" in reason_str:
        return "Error de conexión: el servidor rechazó la conexión"
    elif "name or service not known" in reason_str or "getaddrinfo failed" in reason_str:
        return "Error de conexión: no se pudo resolver el nombre del dominio"
    elif "certificate" in reason_str or "ssl" in reason_str:
        return "Error de seguridad SSL: problema con el certificado del servidor"

    return "Error de conexión inesperado. Intente de nuevo."