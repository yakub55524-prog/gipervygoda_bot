import os
from dotenv import load_dotenv

# ========== ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ==========
# Загружаем переменные из файла .env
load_dotenv()

# Выводим информацию о загрузке для отладки
print("=" * 50)
print("🔧 НАСТРОЙКИ КОНФИГУРАЦИИ")
print("=" * 50)

# ========== ОБЯЗАТЕЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
# Токен бота от @BotFather
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден в файле .env")
    print("   Добавьте в .env строку: BOT_TOKEN=ваш_токен_бота")
    BOT_TOKEN = None  # Без токена бот не запустится
else:
    print(f"✅ BOT_TOKEN загружен (первые 15 символов): {BOT_TOKEN[:15]}...")

# ID администратора (ваш Telegram ID)
ADMIN_ID_STR = os.getenv('ADMIN_ID')
if not ADMIN_ID_STR:
    print("❌ ОШИБКА: ADMIN_ID не найден в файле .env")
    print("   Добавьте в .env строку: ADMIN_ID=ваш_telegram_id")
    print("   ID можно получить у бота @userinfobot")
    ADMIN_ID = None
else:
    try:
        ADMIN_ID = int(ADMIN_ID_STR)
        print(f"✅ ADMIN_ID загружен: {ADMIN_ID}")
    except ValueError:
        print(f"❌ ОШИБКА: ADMIN_ID должен быть числом, а не '{ADMIN_ID_STR}'")
        ADMIN_ID = None

# ========== ОПЦИОНАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
# ID канала для публикации отзывов
# Можно использовать username (@gipervygoda) или числовой ID (например: -1001234567890)
CHANNEL_ID = os.getenv('CHANNEL_ID', '@gipervygoda')
print(f"📢 Канал для публикации: {CHANNEL_ID}")
print("   Примечание: Для ID каналов используйте формат -1001234567890")

# Процент комиссии (по умолчанию 40%)
COMMISSION_RATE_STR = os.getenv('COMMISSION_RATE', '0.4')
try:
    COMMISSION_RATE = float(COMMISSION_RATE_STR)
    if not 0.01 <= COMMISSION_RATE <= 0.99:
        print(f"⚠️  Внимание: COMMISSION_RATE {COMMISSION_RATE} выходит за разумные пределы (0.01-0.99)")
        COMMISSION_RATE = 0.4
except ValueError:
    print(f"⚠️  Ошибка: COMMISSION_RATE должен быть числом, установлено 0.4 по умолчанию")
    COMMISSION_RATE = 0.4
print(f"💰 Процент комиссии: {int(COMMISSION_RATE * 100)}%")

# Лимиты и настройки
MAX_REVIEW_LENGTH = int(os.getenv('MAX_REVIEW_LENGTH', '1000'))  # Максимальная длина отзыва
MIN_REVIEW_LENGTH = int(os.getenv('MIN_REVIEW_LENGTH', '10'))  # Минимальная длина отзыва
REQUEST_TIMEOUT_HOURS = int(os.getenv('REQUEST_TIMEOUT_HOURS', '24'))  # Таймаут выполнения заявки

print(f"📝 Максимальная длина отзыва: {MAX_REVIEW_LENGTH} символов")
print(f"📝 Минимальная длина отзыва: {MIN_REVIEW_LENGTH} символов")
print(f"⏰ Таймаут заявки: {REQUEST_TIMEOUT_HOURS} часов")

# ========== НАСТРОЙКИ ПУБЛИКАЦИИ ==========
# Форматирование отзывов для канала
REVIEW_TEMPLATE = os.getenv('REVIEW_TEMPLATE', """
📢 <b>НОВЫЙ ОТЗЫВ</b>

⭐ <b>Оценка:</b> {stars}
📝 <b>Отзыв:</b>
{review_text}

<i>Спасибо за доверие! ❤️</i>
""")

# Форматирование уведомлений о новых заявках
REQUEST_NOTIFICATION_TEMPLATE = os.getenv('REQUEST_NOTIFICATION_TEMPLATE', """
🚨 <b>НОВАЯ ЗАЯВКА #{request_id}</b>

👤 Пользователь: @{username}
📞 Контакт: {contact}
📦 Товар: {product}
💰 Цена клиента: {known_price:,} ₽
🏙️ Город: {city}

🆔 ID заявки: {request_id}
⏰ Время создания: {created_at}
""")

# ========== КОНСТАНТЫ ДЛЯ СОСТОЯНИЙ ДИАЛОГА ==========
# Состояния для диалога оформления заявки
(WAITING_FOR_PRODUCT,
 WAITING_FOR_PRICE,
 WAITING_FOR_CITY,
 WAITING_FOR_CONTACT) = range(4)

# Состояния для диалога отзыва
(WAITING_REVIEW_TEXT,
 WAITING_REVIEW_RATING) = range(4, 6)

print(f"🎯 Состояния диалогов инициализированы")


# ========== ПРОВЕРКА КОНФИГУРАЦИИ ==========
def validate_config():
    """Проверяет корректность конфигурации"""
    errors = []

    if not BOT_TOKEN:
        errors.append("BOT_TOKEN не установлен")

    if not ADMIN_ID:
        errors.append("ADMIN_ID не установлен или некорректен")

    # Проверяем, что токен выглядит как Telegram токен
    if BOT_TOKEN and ':' not in BOT_TOKEN:
        errors.append("BOT_TOKEN должен содержать двоеточие (формат: 123456:ABC-DEF1234)")

    if not CHANNEL_ID:
        errors.append("CHANNEL_ID не установлен")

    if errors:
        print("\n" + "=" * 50)
        print("❌ ОШИБКИ КОНФИГУРАЦИИ:")
        for error in errors:
            print(f"   • {error}")
        print("=" * 50)
        return False

    print("\n" + "=" * 50)
    print("✅ ВСЕ НАСТРОЙКИ ЗАГРУЖЕНЫ КОРРЕКТНО")
    print("=" * 50)
    return True


# ========== УТИЛИТЫ ==========
def get_channel_message_url(message_id):
    """Генерирует ссылку на сообщение в канале"""
    if CHANNEL_ID.startswith('-100'):
        # Для числовых ID каналов
        channel_id_clean = CHANNEL_ID.replace('-100', '')
        return f"https://t.me/c/{channel_id_clean}/{message_id}"
    else:
        # Для username каналов (@channelname)
        channel_name = CHANNEL_ID.replace('@', '')
        return f"https://t.me/{channel_name}/{message_id}"


def format_price(price):
    """Форматирует цену с разделителями тысяч"""
    try:
        return f"{int(price):,}".replace(',', ' ')
    except:
        return str(price)


def format_commission(price, commission_rate=None):
    """Рассчитывает и форматирует комиссию"""
    if commission_rate is None:
        commission_rate = COMMISSION_RATE
    commission = price * commission_rate
    return f"{int(commission):,}".replace(',', ' ')


# ========== ИНФОРМАЦИЯ О КОНФИГЕ ==========
CONFIG_INFO = f"""
🛠️ Конфигурация бота "ГиперВыгода"

Базовые настройки:
• Токен бота: {'Установлен' if BOT_TOKEN else 'ОТСУТСТВУЕТ'}
• Администратор: {ADMIN_ID if ADMIN_ID else 'НЕ УСТАНОВЛЕН'}
• Канал для публикаций: {CHANNEL_ID}
• Комиссия: {int(COMMISSION_RATE * 100)}%

Лимиты:
• Макс. длина отзыва: {MAX_REVIEW_LENGTH} символов
• Мин. длина отзыва: {MIN_REVIEW_LENGTH} символов
• Таймаут заявки: {REQUEST_TIMEOUT_HOURS} часов

Файл .env должен содержать:
BOT_TOKEN=ваш_токен_от_BotFather
ADMIN_ID=ваш_telegram_id
# Опционально:
CHANNEL_ID=@gipervygoda
COMMISSION_RATE=0.4
MAX_REVIEW_LENGTH=1000
MIN_REVIEW_LENGTH=10
REQUEST_TIMEOUT_HOURS=24
"""

# Автоматическая проверка конфигурации при импорте
if __name__ == "__main__":
    print(CONFIG_INFO)
    validate_config()
else:
    # При импорте модуля просто проверяем конфигурацию
    is_config_valid = validate_config()
    if not is_config_valid and (BOT_TOKEN is None or ADMIN_ID is None):
        print("\n⚠️  ВНИМАНИЕ: Бот может не запуститься из-за ошибок конфигурации")
        print("   Проверьте файл .env в корневой папке проекта")


def WAITING_FOR_LINK():
    return None