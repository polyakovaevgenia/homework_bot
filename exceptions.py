class TokenError(Exception):
    """Ошибки проверки токена."""

    pass


class ApiAnswerError(Exception):
    """Ошибки ответа сервера."""

    pass


class StatusError(Exception):
    """Ошибки статуса работы."""

    pass
