"""Screen text. Arabic (RTL).

Commands and buttons render through the same functions, so the two entry points
cannot drift apart as features are added.

Every Latin run -- @usernames, IDs, command names, the brand -- goes through
`ltr()` or `code()`. Bare Latin inside an Arabic paragraph reorders visually on
the client; see `core/text.py`.
"""

from datetime import UTC, datetime, tzinfo
from html import escape

from aiogram.utils.markdown import hbold

from powerbank.core.audit import AuditAction
from powerbank.core.cards import CardType
from powerbank.core.coins import CoinType
from powerbank.core.power_pass import PowerPassType
from powerbank.core.roles import Role
from powerbank.core.store_cards import StoreCardType
from powerbank.core.text import cmd, code, ltr
from powerbank.db.models import AuditEvent, Card, CoinCard, PowerPassCard, StoreCard, User
from powerbank.services.audit import HistoryPage

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
{cmd("cards")} — بطاقات موظف بعينه
{cmd("card")} — البحث عن بطاقة

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


def profile(found: User, issued_count: int = 0) -> str:
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
    if found.role.is_member:
        lines.append(f"بطاقات صادرة: {ltr(issued_count)}")
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
ASK_TARGET_CARDS = "عن بطاقات من تبحث؟\n\nأرسل المعرّف الرقمي أو @اسم المستخدم."
ASK_CARD_QUERY = "🔎 أرسل <b>الرقم البنكي</b> أو <b>الاسم</b> للبحث عن بطاقة."
CANCELLED = "تم الإلغاء."
NOT_FOUND = "لا يوجد سجل لهذا الشخص."
NOT_A_MEMBER = "هذا الشخص ليس عضواً."
CARD_NOT_FOUND = "لا توجد بطاقة مطابقة."
BAD_ROLE = f"الصلاحية يجب أن تكون {ltr('user')} أو {ltr('admin')}."
BALANCE_SOON = "💰 الحسابات لم تُفتح بعد.\n\nقريباً في التحديث القادم."


# --- account card ---------------------------------------------------------

ASK_CARD_TYPE = "اختر <b>نوع البطاقة</b>:"
ASK_REAL_NAME = "1/4 — أرسل <b>الاسم الحقيقي</b>."
ASK_FACEBOOK_NAME = "2/4 — أرسل <b>الاسم بالفيسبوك</b>."
ASK_BANK_NUMBER = (
    "3/4 — أرسل <b>الرقم البنكي</b>.\n\n"
    "أرقام فقط، ويمكن كتابته بدون الأصفار في البداية "
    f"(مثلاً {ltr('76')} تصبح {ltr('00000076')})."
)
ASK_CARD_USERNAME = "4/4 — أرسل <b>اسم المستخدم</b> الذي تريده على البطاقة."
CARD_RENDERING = "⏳ جاري إصدار البطاقة..."
CARD_HOME = "🪪 اضغط الزر بالأسفل لإصدار بطاقة."


def card_caption(card: Card) -> str:
    """Caption sent alongside the rendered image."""
    return (
        f"🪪 <b>البطاقة {card.card_type.label}</b>\n\n"
        f"الاسم الحقيقي: {_name(card.real_name)}\n"
        f"الاسم بالفيسبوك: {_name(card.facebook_name)}\n"
        f"الرقم البنكي: {code(card.formatted_number)}\n"
        f"اسم المستخدم: {ltr(card.display_username)}"
    )


def card_details(card: Card, issuer: User | None) -> str:
    """The full record of one card, for an admin lookup."""
    return (
        f"🪪 <b>البطاقة {card.card_type.label}</b>\n\n"
        f"الاسم الحقيقي: {_name(card.real_name)}\n"
        f"الاسم بالفيسبوك: {_name(card.facebook_name)}\n"
        f"الرقم البنكي: {code(card.formatted_number)}\n"
        f"اسم المستخدم: {ltr(card.display_username)}\n"
        f"أصدرها: {ltr(issuer.display) if issuer else '—'}\n"
        f"بتاريخ: {_issued_at(card)}"
    )


def _card_line(card: Card) -> str:
    return f"• {code(card.formatted_number)} — {_name(card.real_name)} — {_issued_at(card)}"


def my_issued(cards: list[Card], total: int) -> str:
    """The employee's own issued-cards list."""
    if not cards:
        return "🪪 لم تُصدر أي بطاقة بعد.\n\nاضغط الزر بالأسفل لإصدار بطاقة."
    head = f"🪪 <b>بطاقاتك</b> ({ltr(total)})"
    if total > len(cards):
        head += f"\nأحدث {ltr(len(cards))}"
    return head + "\n" + "\n".join(_card_line(c) for c in cards)


def employee_cards(employee: User, cards: list[Card], total: int) -> str:
    """One employee's issued cards, for an admin."""
    head = f"🪪 بطاقات {hbold(ltr(employee.display))} ({ltr(total)})"
    if not cards:
        return head + "\n\nلا توجد بطاقات."
    if total > len(cards):
        head += f"\nأحدث {ltr(len(cards))}"
    return head + "\n" + "\n".join(_card_line(c) for c in cards)


def issue_summary(rows: list[tuple[User, int]]) -> str:
    """Every member and how many cards they have issued."""
    if not rows:
        return "لا يوجد أعضاء بعد."
    lines = [f"• {ltr(user.display)} — {ltr(count)} بطاقة" for user, count in rows]
    return f"{hbold('البطاقات الصادرة')}\n" + "\n".join(lines)


# --- power-pass cards ------------------------------------------------------

ASK_POWER_PASS_TYPE = "اختر <b>نوع الباور باس</b>:"
ASK_POWER_PASS_COUNT = "كم عدد البطاقات التي تريد إصدارها؟\n\nأرسل رقماً من 1 إلى 100."
POWER_PASS_RENDERING = "⏳ جاري إصدار الدفعة..."


def power_pass_panel(last: dict[PowerPassType, str | None]) -> str:
    lines = [
        f"• {pp_type.label} — {ltr(last[pp_type])}"
        if last.get(pp_type)
        else f"• {pp_type.label} — لم يُصدر بعد"
        for pp_type in PowerPassType
    ]
    return f"{hbold('🎫 باور باس')}\n\nآخر كود صادر لكل نوع:\n" + "\n".join(lines)


def power_pass_batch_caption(card_type: PowerPassType, batch: list[PowerPassCard]) -> str:
    """Caption sent with the first photo of a freshly minted batch."""
    lines = [
        f"🎫 {hbold(card_type.label)}",
        f"العدد: {ltr(len(batch))}",
        f"من {code(batch[0].code)}",
        f"إلى {code(batch[-1].code)}",
    ]
    return "\n".join(lines)


# --- coins -------------------------------------------------------------------

ASK_COIN_TYPE = "اختر <b>فئة العملة</b>:"
ASK_COIN_COUNT = "كم عدد العملات التي تريد إصدارها؟\n\nأرسل رقماً من 1 إلى 100."
COIN_RENDERING = "⏳ جاري إصدار الدفعة..."


def coins_panel(last: dict[CoinType, str | None]) -> str:
    lines = [
        f"• {coin_type.label} — {ltr(last[coin_type])}"
        if last.get(coin_type)
        else f"• {coin_type.label} — لم تُصدر بعد"
        for coin_type in CoinType
    ]
    return f"{hbold('🪙 عملات')}\n\nآخر كود صادر لكل فئة:\n" + "\n".join(lines)


def coin_batch_caption(coin_type: CoinType, batch: list[CoinCard]) -> str:
    """Caption sent with the first photo of a freshly minted batch."""
    lines = [
        f"🪙 {hbold(coin_type.label)}",
        f"العدد: {ltr(len(batch))}",
        f"من {code(batch[0].code)}",
        f"إلى {code(batch[-1].code)}",
    ]
    return "\n".join(lines)


# --- store cards -------------------------------------------------------------

ASK_STORE_CARD_TYPE = "اختر <b>نوع بطاقة المتجر</b>:"
ASK_STORE_CARD_COUNT = "كم عدد البطاقات التي تريد إصدارها؟\n\nأرسل رقماً من 1 إلى 100."
STORE_CARD_RENDERING = "⏳ جاري إصدار الدفعة..."


def store_cards_panel(last: dict[StoreCardType, str | None]) -> str:
    lines = [
        f"• {card_type.label} — {ltr(last[card_type])}"
        if last.get(card_type)
        else f"• {card_type.label} — لم تُصدر بعد"
        for card_type in StoreCardType
    ]
    return f"{hbold('🛒 بطاقات المتجر')}\n\nآخر كود صادر لكل نوع:\n" + "\n".join(lines)


def store_card_batch_caption(card_type: StoreCardType, batch: list[StoreCard]) -> str:
    """Caption sent with the first photo of a freshly minted batch."""
    lines = [
        f"🛒 {hbold(card_type.label)}",
        f"العدد: {ltr(len(batch))}",
        f"من {code(batch[0].code)}",
        f"إلى {code(batch[-1].code)}",
    ]
    return "\n".join(lines)


def _name(value: str) -> str:
    """Isolate a value as LTR only if it carries no Arabic letters."""
    return ltr(value) if _is_latin(value) else value


def _issued_at(card: Card) -> str:
    return ltr(f"{card.created_at:%Y-%m-%d}")


def _is_latin(value: str) -> bool:
    """Whether a value needs LTR isolation (no Arabic letters in it)."""
    return not any("؀" <= ch <= "ۿ" for ch in value)


# --- history (audit log) -------------------------------------------------------

ASK_HISTORY_PERSON = "أرسل المعرّف الرقمي أو @اسم_المستخدم لعرض سجل هذا الشخص فقط."
HISTORY_EMPTY = "لا توجد أي عمليات مسجلة بعد."


def _who(user: User | None) -> str:
    """The person on a history line; None means the bot itself."""
    if user is None:
        return "🤖 النظام"
    return ltr(escape(user.display))


def _label(enum: type, value: str | None) -> str:
    """An enum value's Arabic label, falling back to the raw value if unknown."""
    try:
        return enum(value).label
    except ValueError:
        return escape(str(value))


def _batch_line(label: str, d: dict) -> str:
    return (
        f"أصدر {ltr(d.get('count'))} × {hbold(label)}\n"
        f"    من {code(d.get('first'))} إلى {code(d.get('last'))}"
    )


def _event_text(event: AuditEvent) -> str:
    """What happened, as one Arabic sentence (plus a detail line for batches)."""
    d = event.details or {}
    target = _who(event.target) if event.target_id else "—"
    match event.action:
        case AuditAction.MEMBER_ADDED:
            return f"أضاف {target} بصفة {hbold(_label(Role, d.get('role')))}"
        case AuditAction.ROLE_CHANGED:
            return (
                f"غيّر صلاحية {target} من {_label(Role, d.get('previous_role'))} "
                f"إلى {hbold(_label(Role, d.get('role')))}"
            )
        case AuditAction.MEMBER_REMOVED:
            previous = d.get("previous_role")
            was = f" (كان {_label(Role, previous)})" if previous else ""
            return f"أزال {target}{was}"
        case AuditAction.SUPER_ADMIN_SEEDED:
            return f"عيّن {target} {hbold('مشرفاً عاماً')} من الإعدادات"
        case AuditAction.CARD_ISSUED:
            return (
                f"أصدر بطاقة {hbold(_label(CardType, d.get('card_type')))} "
                f"رقم {code(d.get('bank_number'))} لـ {_name(escape(str(d.get('real_name', ''))))}"
            )
        case AuditAction.CARD_VIEWED:
            found = d.get("bank_number")
            result = f"← {code(found)}" if found else "← لم يُعثر عليها"
            return f"بحث عن بطاقة «{escape(str(d.get('query', '')))}» {result}"
        case AuditAction.POWER_PASS_BATCH:
            return _batch_line(_label(PowerPassType, d.get("type")), d)
        case AuditAction.COIN_BATCH:
            return _batch_line(_label(CoinType, d.get("type")), d)
        case AuditAction.STORE_CARD_BATCH:
            return _batch_line(_label(StoreCardType, d.get("type")), d)
        case AuditAction.ACCESS_DENIED:
            return "حاول استخدام البوت بدون صلاحية"
    return escape(str(event.action))


def _when(moment: datetime, tz: tzinfo) -> str:
    if moment.tzinfo is None:  # SQLite returns naive datetimes; they are UTC
        moment = moment.replace(tzinfo=UTC)
    return ltr(f"{moment.astimezone(tz):%Y-%m-%d %H:%M}")


def history_page(page: HistoryPage, tz: tzinfo, person: User | None = None) -> str:
    """One page of the audit log, newest first."""
    title = "📜 السجل" if person is None else f"📜 سجل {ltr(escape(person.display))}"
    head = f"{hbold(title)} — {ltr(page.total)} عملية"
    if not page.events:
        return f"{head}\n\n{HISTORY_EMPTY}"

    blocks = [
        f"{event.action.icon} {_when(event.created_at, tz)} — {_who(event.actor)}\n"
        f"{_event_text(event)}"
        for event in page.events
    ]
    footer = f"صفحة {ltr(page.page + 1)} من {ltr(page.pages)}"
    return f"{head}\n\n" + "\n\n".join(blocks) + f"\n\n{footer}"
