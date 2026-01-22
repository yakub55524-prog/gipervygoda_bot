import logging
import re
from urllib.parse import urlparse, parse_qs

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes, CallbackQueryHandler
)

from config import BOT_TOKEN, ADMIN_ID, COMMISSION_RATE, WAITING_FOR_PRODUCT, WAITING_FOR_LINK, WAITING_FOR_CITY, \
    WAITING_FOR_CONTACT, WAITING_REVIEW_TEXT, WAITING_REVIEW_RATING, CHANNEL_ID, MAX_REVIEW_LENGTH, MIN_REVIEW_LENGTH
from database import save_request, get_user_requests, save_review, get_review, update_review_status

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ========== УТИЛИТЫ ==========
def extract_price_from_url(url):
    """
    Пытается извлечь цену из URL популярных маркетплейсов
    В реальном проекте здесь будет парсинг страниц или API
    """
    try:
        url_lower = url.lower()

        # Проверяем, что это ссылка на популярные маркетплейсы
        supported_domains = [
            'wildberries.ru', 'wildberries.', 'ozon.ru', 'ozon.',
            'market.yandex.ru', 'citilink.ru', 'dns-shop.ru',
            'mvideo.ru', 'eldorado.ru', 'technopark.ru'
        ]

        if not any(domain in url_lower for domain in supported_domains):
            return None

        # Для тестирования - извлекаем цену из query параметров (если есть)
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        # Ищем цену в параметрах (для некоторых маркетплейсов)
        price_keys = ['price', 'cost', 'amount', 'sum']
        for key in price_keys:
            if key in query_params:
                try:
                    price_str = query_params[key][0].replace(' ', '').replace(',', '.')
                    price = int(float(price_str))
                    if 100 <= price <= 10000000:  # Разумные пределы
                        logger.info(f"Извлечена цена {price} из параметра {key}")
                        return price
                except (ValueError, TypeError):
                    continue

        # Если не нашли в параметрах, можно показать пользователю сообщение
        return None

    except Exception as e:
        logger.error(f"Ошибка при извлечении цены из URL: {e}")
        return None


# ========== ОСНОВНЫЕ КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_text = f"""
    🛍 <b>Добро пожаловать в ГиперВыгоду, {user.first_name}!</b>

    🤖 <b>Я ваш персональный помощник по поиску товаров дешевле!</b>

    📌 <b>Как это работает:</b>
    1. Вы находите товар и его цену в магазине
    2. Я ищу этот же товар дешевле
    3. Вы платите мне только <b>{int(COMMISSION_RATE * 100)}% от сэкономленной суммы</b>
    4. Вы все равно покупаете дешевле, чем нашли сами!

    💰 <b>Пример:</b>
    • Ваша цена: 70 000 ₽
    • Моя цена: 57 000 ₽
    • Экономия: 13 000 ₽
    • Моя комиссия ({int(COMMISSION_RATE * 100)}%): 5 200 ₽
    • <b>Ваш итог: 62 200 ₽ (выгода 7 800 ₽!)</b>

    🚀 Чтобы начать, нажмите /order
    ⭐ Оставить отзыв: /review
    📋 Мои заявки: /myrequest
    ℹ️ Подробнее: /help
    """
    await update.message.reply_html(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = f"""
    ❓ <b>Частые вопросы:</b>

    <b>1. Как происходит оплата?</b>
    Вы платите комиссию только после того, как:
    • Я нашел товар дешевле
    • Вы подтвердили, что хотите его купить
    • Совершили покупку по моей ссылке

    <b>2. Как оформить заявку?</b>
    Используйте /order и укажите:
    • Название товара
    • Ссылку на товар (Wildberries, Ozon, Яндекс.Маркет и др.)
    • Ваш город
    • Контакт для связи

    <b>3. Какие товары можно искать?</b>
    Любые: электроника, техника, мебель, одежда, автотовары и т.д.

    <b>4. Сколько времени занимает поиск?</b>
    Обычно 1-24 часа в зависимости от сложности.

    <b>5. Как оставить отзыв?</b>
    Используйте команду /review - ваш отзыв будет отправлен на модерацию.

    <b>6. Как связаться с поддержкой?</b>
    Пишите напрямую: @ваш_логин_в_telegram

    📝 <b>Начать поиск:</b> /order
    ⭐ <b>Оставить отзыв:</b> /review
    📋 <b>Мои заявки:</b> /myrequest
    """
    await update.message.reply_html(help_text)


# ========== СИСТЕМА ЗАЯВОК ==========
async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало диалога оформления заявки"""
    # Очищаем предыдущие данные
    context.user_data.clear()

    await update.message.reply_text(
        "🎯 <b>Отлично! Давайте найдем товар дешевле!</b>\n\n"
        "📝 <b>Шаг 1 из 4:</b>\n"
        "Напишите <b>точное название товара</b> (модель, артикул).\n"
        "Пример: <i>Телевизор Samsung QE55Q70BAUXRU</i>",
        parse_mode='HTML'
    )
    return WAITING_FOR_PRODUCT


async def receive_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение названия товара"""
    product = update.message.text.strip()

    if len(product) < 3:
        await update.message.reply_text(
            "❌ <b>Название товара слишком короткое.</b>\n"
            "Пожалуйста, укажите полное название товара:",
            parse_mode='HTML'
        )
        return WAITING_FOR_PRODUCT

    context.user_data['product'] = product
    await update.message.reply_text(
        "🔗 <b>Шаг 2 из 4:</b>\n"
        "Пришлите <b>ссылку на товар</b> из магазина.\n\n"
        "<i>Поддерживаемые магазины:</i>\n"
        "• Wildberries\n• Ozon\n• Яндекс.Маркет\n• Ситилинк\n• ДНС\n• MVideo\n• и другие\n\n"
        "<b>Пример:</b>\n<code>https://www.wildberries.ru/catalog/12345678/detail.aspx</code>\n\n"
        "<i>По ссылке я проверю актуальную цену.</i>",
        parse_mode='HTML'
    )
    return WAITING_FOR_LINK


async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение ссылки на товар и извлечение цены"""
    url = update.message.text.strip()

    # Проверяем, что это ссылка
    if not re.match(r'^https?://', url, re.IGNORECASE):
        await update.message.reply_text(
            "❌ <b>Это не похоже на ссылку.</b>\n"
            "Пожалуйста, пришлите полную ссылку на товар, начинающуюся с http:// или https://\n"
            "<i>Пример: https://www.wildberries.ru/catalog/12345678/detail.aspx</i>",
            parse_mode='HTML'
        )
        return WAITING_FOR_LINK

    # Сохраняем ссылку
    context.user_data['product_url'] = url

    # Пробуем извлечь цену автоматически
    auto_price = extract_price_from_url(url)

    if auto_price:
        context.user_data['known_price'] = auto_price
        context.user_data['price_source'] = 'auto'

        await update.message.reply_text(
            f"✅ <b>Цена определена автоматически:</b> {auto_price:,} ₽\n\n"
            f"<i>Если цена неверна, вы сможете исправить её на следующем шаге.</i>\n\n"
            f"🏙️ <b>Шаг 3 из 4:</b>\n"
            f"В каком <b>городе</b> вы находитесь?\n"
            f"Это нужно для поиска местных предложений.",
            parse_mode='HTML'
        )
        return WAITING_FOR_CITY
    else:
        # Если не удалось извлечь цену, просим ввести вручную
        context.user_data['awaiting_manual_price'] = True
        context.user_data['price_source'] = 'manual'

        await update.message.reply_text(
            "📝 <b>Шаг 2.1 из 4:</b>\n"
            "Пожалуйста, введите цену товара <b>вручную</b> (только цифры):\n"
            "<i>Пример: 70000</i>\n\n"
            "<b>Укажите ту цену, которую вы видите на сайте по вашей ссылке.</b>",
            parse_mode='HTML'
        )
        return WAITING_FOR_LINK


async def receive_manual_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение цены вручную, если не удалось извлечь из ссылки"""
    try:
        # Очищаем текст от пробелов и валютных символов
        price_text = update.message.text.strip()
        price_text = re.sub(r'[^\d]', '', price_text)

        if not price_text:
            raise ValueError("Пустая цена")

        price = int(price_text)

        # Проверяем разумные пределы
        if price < 100:
            await update.message.reply_text(
                "❌ <b>Цена слишком низкая.</b>\n"
                "Минимальная сумма для поиска - 100 ₽.\n"
                "Введите корректную цену:",
                parse_mode='HTML'
            )
            return WAITING_FOR_LINK

        if price > 10000000:
            await update.message.reply_text(
                "❌ <b>Цена слишком высокая.</b>\n"
                "Максимальная сумма для поиска - 10 000 000 ₽.\n"
                "Введите корректную цену:",
                parse_mode='HTML'
            )
            return WAITING_FOR_LINK

        context.user_data['known_price'] = price
        context.user_data['awaiting_manual_price'] = False

        await update.message.reply_text(
            f"✅ <b>Цена сохранена:</b> {price:,} ₽\n\n"
            f"🏙️ <b>Шаг 3 из 4:</b>\n"
            f"В каком <b>городе</b> вы находитесь?\n"
            f"<i>Пример: Москва, Санкт-Петербург, Казань</i>",
            parse_mode='HTML'
        )
        return WAITING_FOR_CITY

    except ValueError:
        await update.message.reply_text(
            "❌ <b>Некорректный формат цены.</b>\n"
            "Введите только цифры (например: 70000):",
            parse_mode='HTML'
        )
        return WAITING_FOR_LINK


async def receive_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение города"""
    city = update.message.text.strip()

    if len(city) < 2:
        await update.message.reply_text(
            "❌ <b>Название города слишком короткое.</b>\n"
            "Пожалуйста, укажите корректное название города:",
            parse_mode='HTML'
        )
        return WAITING_FOR_CITY

    context.user_data['city'] = city

    # Создаем кнопку для отправки контакта
    contact_button = KeyboardButton("📱 Отправить мой контакт", request_contact=True)
    reply_keyboard = [[contact_button]]

    await update.message.reply_text(
        "📞 <b>Шаг 4 из 4:</b>\n"
        "Нажмите кнопку ниже, чтобы отправить ваш контакт,\n"
        "или напишите ваш Telegram username/number.\n\n"
        "<i>Это нужно для связи по вашей заявке.</i>",
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return WAITING_FOR_CONTACT


async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение контакта и сохранение заявки"""
    if update.message.contact:
        contact = f"+{update.message.contact.phone_number}"
    else:
        contact = update.message.text.strip()
        if not contact:
            await update.message.reply_text(
                "❌ <b>Контакт не может быть пустым.</b>\n"
                "Пожалуйста, укажите ваш username или номер телефона:",
                parse_mode='HTML'
            )
            return WAITING_FOR_CONTACT

    # Проверяем, что у нас есть все необходимые данные
    required_fields = ['product', 'product_url', 'known_price', 'city']
    for field in required_fields:
        if field not in context.user_data:
            logger.error(f"Отсутствует поле {field} в user_data")
            await update.message.reply_text(
                "❌ <b>Произошла ошибка при обработке заявки.</b>\n"
                "Пожалуйста, начните заново с команды /order",
                parse_mode='HTML',
                reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
            )
            return ConversationHandler.END

    # Сохраняем все данные
    user_data = {
        'user_id': update.effective_user.id,
        'username': update.effective_user.username or '',
        'product': context.user_data['product'],
        'product_url': context.user_data['product_url'],
        'known_price': context.user_data['known_price'],
        'city': context.user_data['city'],
        'contact': contact,
        'price_source': context.user_data.get('price_source', 'unknown')
    }

    # Сохраняем в базу
    request_id = save_request(user_data)

    # Форматируем цену для красивого отображения
    formatted_price = f"{user_data['known_price']:,}".replace(',', ' ')

    # Уведомляем пользователя
    await update.message.reply_text(
        f"✅ <b>Заявка #{request_id} принята!</b>\n\n"
        f"📦 <b>Товар:</b> {user_data['product']}\n"
        f"🔗 <b>Ссылка:</b> {user_data['product_url'][:50]}...\n"
        f"💰 <b>Ваша цена:</b> {formatted_price} ₽\n"
        f"🏙️ <b>Город:</b> {user_data['city']}\n"
        f"📞 <b>Контакт:</b> {user_data['contact']}\n\n"
        f"🔍 <i>Я начал поиск. Обычно это занимает 1-24 часа.</i>\n\n"
        f"📊 <b>Статус заявки:</b> /myrequest\n"
        f"⭐ <b>После выполнения оставьте отзыв:</b> /review",
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True),  # Убираем клавиатуру
        disable_web_page_preview=True
    )

    # Уведомляем администратора (вас)
    admin_text = (
        f"🚨 <b>НОВАЯ ЗАЯВКА #{request_id}</b>\n\n"
        f"👤 <b>Пользователь:</b> @{user_data['username'] or 'без username'}\n"
        f"📞 <b>Контакт:</b> {user_data['contact']}\n"
        f"📦 <b>Товар:</b> {user_data['product']}\n"
        f"🔗 <b>Ссылка:</b> {user_data['product_url']}\n"
        f"💰 <b>Цена клиента:</b> {formatted_price} ₽\n"
        f"🏙️ <b>Город:</b> {user_data['city']}\n"
        f"📊 <b>Источник цены:</b> {user_data['price_source']}\n\n"
        f"🆔 <b>ID заявки:</b> {request_id}"
    )

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=admin_text,
        parse_mode='HTML',
        disable_web_page_preview=True
    )

    # Очищаем временные данные
    context.user_data.clear()

    return ConversationHandler.END


async def myrequest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать заявки пользователя"""
    user_id = update.effective_user.id
    requests = get_user_requests(user_id)

    if not requests:
        await update.message.reply_text(
            "📭 <b>У вас еще нет заявок.</b>\n\n"
            "Создайте первую заявку через /order",
            parse_mode='HTML'
        )
        return

    response = "📋 <b>Ваши заявки:</b>\n\n"

    # Показываем последние 5 заявок
    for req in requests[-5:]:
        status_icons = {
            'new': '🆕',
            'in_progress': '🔍',
            'completed': '✅',
            'cancelled': '❌'
        }

        status_icon = status_icons.get(req['status'], '📝')
        formatted_price = f"{req['known_price']:,}".replace(',', ' ')

        response += (
            f"{status_icon} <b>Заявка #{req['id']}</b>\n"
            f"📦 {req['product'][:40]}...\n"
            f"💰 <b>Цена:</b> {formatted_price} ₽\n"
            f"📊 <b>Статус:</b> {req['status']}\n"
        )

        if req['found_price']:
            found_price_formatted = f"{req['found_price']:,}".replace(',', ' ')
            economy_formatted = f"{req['economy']:,}".replace(',', ' ')
            commission_formatted = f"{req['commission']:,}".replace(',', ' ')

            response += (
                f"🎯 <b>Найдена цена:</b> {found_price_formatted} ₽\n"
                f"💸 <b>Экономия:</b> {economy_formatted} ₽\n"
                f"🧾 <b>Комиссия ({int(COMMISSION_RATE * 100)}%):</b> {commission_formatted} ₽\n"
            )

        response += f"📅 <b>Создана:</b> {req['created_at']}\n\n"

    await update.message.reply_html(response)


# ========== СИСТЕМА ОТЗЫВОВ ==========
async def review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало диалога для оставления отзыва"""
    # Очищаем предыдущие данные
    context.user_data.clear()

    await update.message.reply_text(
        "⭐️ <b>Оставить отзыв</b>\n\n"
        f"Вы можете оценить нашу работу от 1 до 5 звезд.\n"
        f"Отзыв должен быть от {MIN_REVIEW_LENGTH} до {MAX_REVIEW_LENGTH} символов.\n"
        f"Ваш отзыв будет отправлен на модерацию.\n\n"
        "📝 <b>Напишите ваш отзыв:</b>",
        parse_mode='HTML'
    )
    context.user_data['review_step'] = 'text'
    return WAITING_REVIEW_TEXT


async def receive_review_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение текста отзыва"""
    review_text = update.message.text.strip()

    # Проверяем длину отзыва
    if len(review_text) < MIN_REVIEW_LENGTH:
        await update.message.reply_text(
            f"❌ <b>Отзыв слишком короткий.</b>\n"
            f"Минимальная длина: {MIN_REVIEW_LENGTH} символов.\n"
            f"Сейчас: {len(review_text)} символов.\n\n"
            f"Пожалуйста, напишите более подробный отзыв:",
            parse_mode='HTML'
        )
        return WAITING_REVIEW_TEXT

    if len(review_text) > MAX_REVIEW_LENGTH:
        await update.message.reply_text(
            f"❌ <b>Отзыв слишком длинный.</b>\n"
            f"Максимальная длина: {MAX_REVIEW_LENGTH} символов.\n"
            f"Сейчас: {len(review_text)} символов.\n\n"
            f"Пожалуйста, сократите отзыв:",
            parse_mode='HTML'
        )
        return WAITING_REVIEW_TEXT

    context.user_data['review_text'] = review_text

    # Создаем клавиатуру с рейтингом
    keyboard = [
        [
            InlineKeyboardButton("⭐", callback_data="rating_1"),
            InlineKeyboardButton("⭐⭐", callback_data="rating_2"),
            InlineKeyboardButton("⭐⭐⭐", callback_data="rating_3"),
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data="rating_4"),
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="rating_5")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "✨ <b>Теперь оцените нашу работу:</b>\n"
        "Выберите количество звезд (от 1 до 5):",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    return WAITING_REVIEW_RATING


async def receive_review_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора рейтинга (через callback)"""
    query = update.callback_query
    await query.answer()

    rating = int(query.data.split('_')[1])

    # Сохраняем отзыв
    review_id = save_review(
        user_id=update.effective_user.id,
        username=update.effective_user.username,
        review_text=context.user_data['review_text'],
        rating=rating
    )

    # Уведомляем пользователя
    stars = "⭐" * rating
    await query.edit_message_text(
        f"✅ <b>Отзыв #{review_id} отправлен на модерацию!</b>\n\n"
        f"📝 <b>Ваш отзыв:</b>\n{context.user_data['review_text']}\n\n"
        f"⭐ <b>Оценка:</b> {stars}\n\n"
        f"<i>После проверки отзыв может быть опубликован в нашем канале.</i>\n"
        f"<i>Спасибо за обратную связь! ❤️</i>",
        parse_mode='HTML'
    )

    # Отправляем отзыв админу на модерацию
    await send_review_to_admin(context, review_id)

    # Очищаем временные данные
    context.user_data.clear()

    return ConversationHandler.END


async def send_review_to_admin(context: ContextTypes.DEFAULT_TYPE, review_id: int):
    """Отправляет отзыв админу на модерацию"""
    review = get_review(review_id)

    if not review:
        logger.error(f"Отзыв #{review_id} не найден в базе")
        return

    stars = "⭐" * review['rating']

    keyboard = [
        [
            InlineKeyboardButton("✅ Опубликовать", callback_data=f"approve_{review_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{review_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Обрезаем длинный текст для уведомления
    review_text_preview = review['review_text']
    if len(review_text_preview) > 300:
        review_text_preview = review_text_preview[:300] + "..."

    message_text = (
        f"📨 <b>НОВЫЙ ОТЗЫВ #{review_id}</b>\n\n"
        f"👤 <b>Пользователь:</b> @{review['username'] or 'без username'}\n"
        f"⭐ <b>Оценка:</b> {stars}\n"
        f"📝 <b>Текст:</b>\n{review_text_preview}\n\n"
        f"📅 <b>Дата:</b> {review['created_at']}\n"
        f"🆔 <b>ID отзыва:</b> {review_id}"
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message_text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке отзыва админу: {e}")


async def handle_review_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка решений админа (публикация/отклонение)"""
    query = update.callback_query
    await query.answer()

    action, review_id = query.data.split('_')
    review_id = int(review_id)
    review = get_review(review_id)

    if not review:
        await query.edit_message_text("❌ Отзыв не найден")
        return

    if action == 'approve':
        try:
            # Публикуем в канал
            stars = "⭐" * review['rating']
            channel_message_text = (
                f"📢 <b>НОВЫЙ ОТЗЫВ</b>\n\n"
                f"⭐ <b>Оценка:</b> {stars}\n"
                f"📝 <b>Отзыв:</b>\n{review['review_text']}\n\n"
                f"<i>Спасибо за доверие! ❤️</i>"
            )

            # Отправляем в канал
            channel_message = await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=channel_message_text,
                parse_mode='HTML'
            )

            # Обновляем статус
            update_review_status(review_id, 'approved', channel_message.message_id)

            # Формируем ссылку на сообщение
            if CHANNEL_ID.startswith('@'):
                channel_name = CHANNEL_ID.replace('@', '')
                message_url = f"https://t.me/{channel_name}/{channel_message.message_id}"
            else:
                # Для числовых ID каналов
                channel_id_clean = str(CHANNEL_ID).replace('-100', '')
                message_url = f"https://t.me/c/{channel_id_clean}/{channel_message.message_id}"

            # Обновляем сообщение админу
            await query.edit_message_text(
                f"✅ <b>Отзыв #{review_id} опубликован в канале!</b>\n\n"
                f"👤 <b>Пользователь:</b> @{review['username'] or 'без username'}\n"
                f"⭐ <b>Оценка:</b> {stars}\n"
                f"🔗 <b>Ссылка на пост:</b> {message_url}",
                parse_mode='HTML'
            )

            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    chat_id=review['user_id'],
                    text=(
                        f"🎉 <b>Ваш отзыв опубликован в нашем канале!</b>\n\n"
                        f"Спасибо за обратную связь! ❤️\n"
                        f"Ваш отзыв помогает другим пользователям доверять нашему сервису."
                    ),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить пользователя о публикации отзыва: {e}")

        except Exception as e:
            logger.error(f"Ошибка при публикации отзыва: {e}")
            await query.edit_message_text(
                f"❌ <b>Ошибка при публикации:</b>\n{str(e)[:100]}...\n\n"
                f"Проверьте, что бот добавлен как администратор канала {CHANNEL_ID}",
                parse_mode='HTML'
            )

    elif action == 'reject':
        # Обновляем статус
        update_review_status(review_id, 'rejected')

        # Обновляем сообщение админу
        await query.edit_message_text(
            f"❌ <b>Отзыв #{review_id} отклонен</b>\n\n"
            f"<i>Отзыв перемещен в архив.</i>",
            parse_mode='HTML'
        )


async def show_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать последние опубликованные отзывы (команда /reviews)"""
    from database import get_approved_reviews

    approved_reviews = get_approved_reviews(limit=5)

    if not approved_reviews:
        await update.message.reply_text(
            "📢 <b>Опубликованные отзывы</b>\n\n"
            "Пока нет опубликованных отзывов.\n"
            "Будьте первым - оставьте отзыв через /review\n\n"
            "Все отзывы публикуются в нашем канале.",
            parse_mode='HTML'
        )
        return

    response = "📢 <b>Последние отзывы:</b>\n\n"

    for review in approved_reviews:
        stars = "⭐" * review['rating']
        response += (
            f"{stars}\n"
            f"{review['review_text'][:100]}...\n"
            f"📅 {review['published_at'] or review['created_at']}\n\n"
        )

    response += (
        f"<i>Все отзывы в канале: {CHANNEL_ID}</i>\n\n"
        f"⭐ <b>Оставить свой отзыв:</b> /review"
    )

    await update.message.reply_html(response)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена диалога"""
    # Определяем, какой диалог отменяем
    if 'review_step' in context.user_data:
        message_text = "❌ Создание отзыва отменено."
        command = "/review"
    else:
        message_text = "❌ Оформление заявки отменено."
        command = "/order"

    await update.message.reply_text(
        f"{message_text}\n"
        f"Если передумаете - нажмите {command}",
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )

    # Очищаем временные данные
    context.user_data.clear()

    return ConversationHandler.END


# ========== АДМИН КОМАНДЫ ==========
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику (только для админа)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Эта команда только для администратора")
        return

    from database import get_statistics

    stats = get_statistics()

    stats_text = (
        f"📊 <b>СТАТИСТИКА БОТА</b>\n\n"

        f"📋 <b>Заявки:</b>\n"
        f"• Всего: {stats['total_requests']}\n"
        f"• Новые: {stats['new_requests']}\n"
        f"• Выполнено: {stats['completed_requests']}\n"
        f"• Общая экономия: {stats['total_economy']:,} ₽\n"
        f"• Общая комиссия: {stats['total_commission']:,} ₽\n\n"

        f"⭐ <b>Отзывы:</b>\n"
        f"• Всего: {stats['total_reviews']}\n"
        f"• На модерации: {stats['pending_reviews']}\n"
        f"• Опубликовано: {stats['approved_reviews']}\n"
        f"• Средний рейтинг: {stats['average_rating']:.1f}/5.0\n\n"

        f"🤖 <b>Бот работает стабильно!</b>"
    )

    await update.message.reply_html(stats_text)


# ========== ЗАПУСК БОТА ==========
def main():
    """Запуск бота"""
    # Проверяем наличие обязательных настроек
    if not BOT_TOKEN or not ADMIN_ID:
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN или ADMIN_ID не установлены!")
        print("=" * 50)
        print("ПРОВЕРЬТЕ ФАЙЛ .env В КОРНЕ ПРОЕКТА!")
        print("Он должен содержать:")
        print("BOT_TOKEN=ваш_токен_от_BotFather")
        print("ADMIN_ID=ваш_telegram_id")
        print("=" * 50)
        return

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Настройка ConversationHandler для заявки
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('order', order)],
        states={
            WAITING_FOR_PRODUCT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_product)
            ],
            WAITING_FOR_LINK: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & filters.Regex(r'^https?://'),
                    receive_link
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_manual_price
                )
            ],
            WAITING_FOR_CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_city)
            ],
            WAITING_FOR_CONTACT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_contact),
                MessageHandler(filters.CONTACT, receive_contact)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    # Настройка ConversationHandler для отзывов
    review_handler = ConversationHandler(
        entry_points=[CommandHandler('review', review)],
        states={
            WAITING_REVIEW_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_review_text)
            ],
            WAITING_REVIEW_RATING: [
                CallbackQueryHandler(receive_review_rating, pattern='^rating_')
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    # Обработчик кнопок модерации отзывов
    application.add_handler(CallbackQueryHandler(handle_review_decision, pattern='^(approve|reject)_'))

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myrequest", myrequest))
    application.add_handler(CommandHandler("reviews", show_reviews))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(conv_handler)  # Для заявок
    application.add_handler(review_handler)  # Для отзывов

    # Запускаем бота
    print("=" * 50)
    print("🤖 БОТ 'ГИПЕРВЫГОДА' ЗАПУЩЕН!")
    print("=" * 50)
    print(f"👑 Админ ID: {ADMIN_ID}")
    print(f"📢 Канал для публикации: {CHANNEL_ID}")
    print(f"💰 Комиссия: {int(COMMISSION_RATE * 100)}%")
    print("=" * 50)
    print("📝 Основные команды:")
    print("• /start - Начало работы")
    print("• /order - Оформить заявку")
    print("• /review - Оставить отзыв")
    print("• /myrequest - Мои заявки")
    print("• /reviews - Посмотреть отзывы")
    print("• /help - Помощь")
    print("• /stats - Статистика (админ)")
    print("=" * 50)
    print("Для остановки нажмите Ctrl+C")
    print("=" * 50)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()