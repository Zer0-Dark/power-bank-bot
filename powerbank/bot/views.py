"""Screen text. Arabic (RTL).

Commands and buttons render through the same functions, so the two entry points
cannot drift apart as features are added.

Every Latin run -- @usernames, IDs, command names, the brand -- goes through
`ltr()` or `code()`. Bare Latin inside an Arabic paragraph reorders visually on
the client; see `core/text.py`.
"""

from aiogram.utils.markdown import hbold

from powerbank.core.roles import Role
from powerbank.core.text import cmd, code, ltr
from powerbank.db.models import User

BRAND = ltr("Power Bank")

MEMBER_HELP = f"""{hbold(BRAND)} — المساعدة

استخدم الأزرار بالأسفل، أو هذه الأوامر:

{cmd("start")} — القائمة الرئيسية
{cmd("help")} — هذه الشاشة"""

STAFF_HELP = f"""

{hbold("أوامر الإدارة")}
{cmd("add")} — منح صلاحية لشخص
{cmd("remove")} — سحب صلاحية شخص
{cmd("members")} — عرض كل من لديه صلاحية
{cmd("who")} — البحث عن شخص
{cmd("attempts")} — من حاول الدخول

كل أمر بالأعلى له زر في لوحة الإدارة.
يمكنك أيضاً كتابة الأمر مع المعرّف مباشرة، مثل {ltr("/add 12345 admin")}."""


def welcome(user: User) -> str:
    name = ltr(user.first_name) if user.first_name else "بك"
    return (
        f"أهلاً {name} في {hbold(BRAND)}!\n"
        f"أنت مسجّل بصفة {hbold(user.role.label)}.\n\n"
        "اختر من الأزرار بالأسفل."
    )


def help_text(role: Role) -> str:
    return MEMBER_HELP + (STAFF_HELP if role.is_staff else "")


def admin_panel() -> str:
    return f"{hbold('لوحة الإدارة')}\n\nتحكّم بمن يستطيع استخدام البوت."


def members_list(members: list[User]) -> str:
    if not members:
        return "لا يوجد أعضاء بعد."

    lines: list[str] = []
    current: Role | None = None
    for member in members:
        if member.role is not current:
            current = member.role
            lines.append(f"\n{hbold(current.label)}")
        lines.append(f"• {ltr(member.display)} — {code(member.telegram_id)}")

    return f"{hbold('الأعضاء')} ({ltr(len(members))})\n" + "\n".join(lines)


def attempts_list(knocking: list[User]) -> str:
    if not knocking:
        return "لا توجد محاولات دخول مسجّلة."

    lines = [
        f"• {ltr(u.display)} — {code(u.telegram_id)} "
        f"({ltr(u.denied_attempts)} محاولة، آخرها {ltr(f'{u.last_denied_at:%m-%d %H:%M}')})"
        for u in knocking
    ]
    return f"{hbold('آخر محاولات الدخول')}\n" + "\n".join(lines)


def profile(found: User) -> str:
    lines = [
        hbold(ltr(found.display)),
        f"المعرّف: {code(found.telegram_id)}",
        f"الصلاحية: {found.role.label}",
    ]
    if found.first_name:
        lines.append(f"الاسم: {ltr(found.first_name)}")
    if found.last_seen_at:
        lines.append(f"آخر ظهور: {ltr(f'{found.last_seen_at:%Y-%m-%d %H:%M}')}")
    if found.denied_attempts:
        lines.append(f"محاولات مرفوضة: {ltr(found.denied_attempts)}")
    if found.is_banned:
        lines.append("⚠️ محظور")
    return "\n".join(lines)


def granted(user: User, role: Role, *, is_new: bool) -> str:
    verb = "تمت إضافة" if is_new else "تم تحديث"
    return (
        f"✅ {verb} {hbold(ltr(user.display))} بصفة {hbold(role.label)}\n{code(user.telegram_id)}"
    )


def removed(user: User) -> str:
    return f"🗑 تمت إزالة {hbold(ltr(user.display))}\n{code(user.telegram_id)}"


def confirm_removal(user: User) -> str:
    return f"هل تريد إزالة {hbold(ltr(user.display))} ({code(user.telegram_id)})؟"


def unknown_username(query: str) -> str:
    return (
        f"لم يسبق أن راسلني {ltr(query)}.\n\n"
        "اطلب منه إرسال رسالة واحدة للبوت ثم أعد المحاولة، "
        "أو استخدم معرّفه الرقمي."
    )


# --- fixed strings ---

ASK_TARGET_ADD = (
    "من تريد إضافته؟\n\n"
    "أرسل <b>المعرّف الرقمي</b>، أو <b>@اسم المستخدم</b> إن كان قد راسل البوت من قبل."
)
ASK_TARGET_REMOVE = "من تريد إزالته؟\n\nأرسل المعرّف الرقمي أو @اسم المستخدم."
ASK_TARGET_WHO = "عن من تبحث؟\n\nأرسل المعرّف الرقمي أو @اسم المستخدم."
ASK_ROLE = "ما الصلاحية التي تريد منحها؟"
CANCELLED = "تم الإلغاء."
NOT_FOUND = "لا يوجد سجل لهذا الشخص."
NOT_A_MEMBER = "هذا الشخص ليس عضواً."
BAD_ROLE = f"الصلاحية يجب أن تكون {ltr('user')} أو {ltr('admin')}."
BALANCE_SOON = "💰 الحسابات لم تُفتح بعد.\n\nقريباً في التحديث القادم."


# --- account card ---------------------------------------------------------

CARD_MISSING = (
    "🪪 ليس لديك بطاقة بعد.\n\n"
    "اضغط على الزر بالأسفل لإدخال بياناتك."
)

ASK_REAL_NAME = "1/4 — أرسل <b>الاسم الحقيقي</b>."
ASK_FACEBOOK_NAME = "2/4 — أرسل <b>الاسم بالفيسبوك</b>."
ASK_BANK_NUMBER = (
    "3/4 — أرسل <b>الرقم البنكي</b>.\n\n"
    "أرقام فقط، ويمكن كتابته بدون الأصفار في البداية "
    f"(مثلاً {ltr('76')} تصبح {ltr('00000076')})."
)
ASK_CARD_USERNAME = "4/4 — أرسل <b>اسم المستخدم</b> الذي تريده على البطاقة."
CARD_RENDERING = "⏳ جاري إصدار البطاقة..."


def card_caption(card) -> str:
    """Caption sent alongside the rendered image."""
    return (
        f"🪪 <b>بطاقتك</b>\n\n"
        f"الاسم الحقيقي: {ltr(card.real_name) if _is_latin(card.real_name) else card.real_name}\n"
        f"الاسم بالفيسبوك: "
        f"{ltr(card.facebook_name) if _is_latin(card.facebook_name) else card.facebook_name}\n"
        f"الرقم البنكي: {code(card.formatted_number)}\n"
        f"اسم المستخدم: {ltr(card.display_username)}"
    )


def card_saved(card) -> str:
    return f"✅ تم حفظ بطاقتك برقم {code(card.formatted_number)}"


def _is_latin(value: str) -> bool:
    """Whether a value needs LTR isolation (no Arabic letters in it)."""
    return not any("؀" <= ch <= "ۿ" for ch in value)
