"""Domain exceptions.

Raised by the service layer, translated into user-facing messages by the bot
layer. Services never format Telegram replies themselves.
"""


class PowerBankError(Exception):
    """Base for every error this application raises deliberately."""

    user_message = "حدث خطأ. الرجاء المحاولة مرة أخرى."


class UserFacingError(PowerBankError):
    """An error whose message is safe to show the user verbatim."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.user_message = message


class PermissionDenied(UserFacingError):
    """The actor lacks the authority for what they attempted."""


class AccessDenied(PowerBankError):
    """The sender is not a member of the bot at all."""

    user_message = "هذا البوت بالدعوة فقط."


class InsufficientFunds(PowerBankError):
    user_message = "لا تملك عملات كافية لهذه العملية."


class AccountNotFound(PowerBankError):
    user_message = "هذا الحساب غير موجود."
