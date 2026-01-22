import json
import os
from datetime import datetime

# Имена файлов для хранения данных
DB_FILE = 'requests.json'
REVIEWS_FILE = 'reviews.json'


# ========== УТИЛИТЫ ==========
def _read_json(filename):
    """Читает JSON файл, создает если его нет"""
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({'requests': []} if 'request' in filename else {'reviews': []},
                      f, ensure_ascii=False, indent=2)

    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)


def _write_json(filename, data):
    """Записывает данные в JSON файл"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ========== СИСТЕМА ЗАЯВОК ==========
def save_request(user_data):
    """Сохраняет заявку в базу и возвращает её ID"""
    data = _read_json(DB_FILE)

    request_id = len(data['requests']) + 1
    request = {
        'id': request_id,
        'user_id': user_data['user_id'],
        'username': user_data.get('username', ''),
        'product': user_data['product'],
        'known_price': user_data['known_price'],
        'city': user_data['city'],
        'contact': user_data['contact'],
        'status': 'new',  # new, in_progress, completed, cancelled
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'found_price': None,
        'economy': None,
        'commission': None,
        'notes': ''
    }

    data['requests'].append(request)
    _write_json(DB_FILE, data)

    return request_id


def get_user_requests(user_id):
    """Получает все заявки пользователя"""
    data = _read_json(DB_FILE)
    return [req for req in data['requests'] if req['user_id'] == user_id]


def get_all_requests():
    """Получает все заявки (для админа)"""
    data = _read_json(DB_FILE)
    return data['requests']


def get_request(request_id):
    """Получает заявку по ID"""
    data = _read_json(DB_FILE)
    for request in data['requests']:
        if request['id'] == request_id:
            return request
    return None


def update_request(request_id, **kwargs):
    """Обновляет заявку (найденная цена, статус и т.д.)"""
    data = _read_json(DB_FILE)
    updated = False

    for request in data['requests']:
        if request['id'] == request_id:
            # Обновляем поля
            for key, value in kwargs.items():
                if key in request:
                    request[key] = value

            # Автоматически рассчитываем экономию и комиссию
            if 'found_price' in kwargs and request['known_price'] and kwargs['found_price']:
                request['economy'] = request['known_price'] - kwargs['found_price']
                if request['economy'] > 0:
                    request['commission'] = request['economy'] * 0.4  # 40% комиссия

            request['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            updated = True
            break

    if updated:
        _write_json(DB_FILE, data)
        return True
    return False


def get_requests_by_status(status):
    """Получает заявки по статусу"""
    data = _read_json(DB_FILE)
    return [req for req in data['requests'] if req['status'] == status]


def delete_request(request_id):
    """Удаляет заявку (для админа)"""
    data = _read_json(DB_FILE)
    initial_length = len(data['requests'])

    data['requests'] = [req for req in data['requests'] if req['id'] != request_id]

    if len(data['requests']) < initial_length:
        _write_json(DB_FILE, data)
        return True
    return False


# ========== СИСТЕМА ОТЗЫВОВ ==========
def save_review(user_id, username, review_text, rating):
    """Сохраняет отзыв и возвращает его ID"""
    data = _read_json(REVIEWS_FILE)

    # Проверяем корректность рейтинга
    if not 1 <= rating <= 5:
        rating = 5  # По умолчанию 5 звезд

    review_id = len(data['reviews']) + 1
    review = {
        'id': review_id,
        'user_id': user_id,
        'username': username or '',
        'review_text': review_text,
        'rating': rating,
        'status': 'pending',  # pending, approved, rejected
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'published_at': None,
        'published_message_id': None,
        'admin_notes': ''
    }

    data['reviews'].append(review)
    _write_json(REVIEWS_FILE, data)

    return review_id


def get_review(review_id):
    """Получает отзыв по ID"""
    data = _read_json(REVIEWS_FILE)
    for review in data['reviews']:
        if review['id'] == review_id:
            return review
    return None


def get_user_reviews(user_id):
    """Получает все отзывы пользователя"""
    data = _read_json(REVIEWS_FILE)
    return [rev for rev in data['reviews'] if rev['user_id'] == user_id]


def get_all_reviews():
    """Получает все отзывы (для админа)"""
    data = _read_json(REVIEWS_FILE)
    return data['reviews']


def get_reviews_by_status(status):
    """Получает отзывы по статусу"""
    data = _read_json(REVIEWS_FILE)
    return [rev for rev in data['reviews'] if rev['status'] == status]


def get_pending_reviews():
    """Получает отзывы на модерации (pending)"""
    return get_reviews_by_status('pending')


def get_approved_reviews(limit=10):
    """Получает опубликованные отзывы (для команды /reviews)"""
    data = _read_json(REVIEWS_FILE)
    approved = [rev for rev in data['reviews'] if rev['status'] == 'approved']

    # Сортируем по дате публикации (новые первые)
    approved.sort(key=lambda x: x['published_at'] or x['created_at'], reverse=True)

    return approved[:limit]


def update_review_status(review_id, status, published_message_id=None):
    """Обновляет статус отзыва и при необходимости добавляет ID сообщения"""
    data = _read_json(REVIEWS_FILE)
    updated = False

    for review in data['reviews']:
        if review['id'] == review_id:
            review['status'] = status

            if status == 'approved':
                review['published_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if published_message_id:
                    review['published_message_id'] = published_message_id

            updated = True
            break

    if updated:
        _write_json(REVIEWS_FILE, data)
        return True
    return False


def update_review(review_id, **kwargs):
    """Обновляет поля отзыва (для админа)"""
    data = _read_json(REVIEWS_FILE)
    updated = False

    for review in data['reviews']:
        if review['id'] == review_id:
            for key, value in kwargs.items():
                if key in review:
                    review[key] = value
            updated = True
            break

    if updated:
        _write_json(REVIEWS_FILE, data)
        return True
    return False


def delete_review(review_id):
    """Удаляет отзыв (для админа)"""
    data = _read_json(REVIEWS_FILE)
    initial_length = len(data['reviews'])

    data['reviews'] = [rev for rev in data['reviews'] if rev['id'] != review_id]

    if len(data['reviews']) < initial_length:
        _write_json(REVIEWS_FILE, data)
        return True
    return False


# ========== СТАТИСТИКА ==========
def get_statistics():
    """Возвращает статистику по заявкам и отзывам"""
    requests_data = _read_json(DB_FILE)
    reviews_data = _read_json(REVIEWS_FILE)

    stats = {
        'total_requests': len(requests_data['requests']),
        'new_requests': len([r for r in requests_data['requests'] if r['status'] == 'new']),
        'completed_requests': len([r for r in requests_data['requests'] if r['status'] == 'completed']),
        'total_economy': sum([r['economy'] or 0 for r in requests_data['requests']]),
        'total_commission': sum([r['commission'] or 0 for r in requests_data['requests']]),

        'total_reviews': len(reviews_data['reviews']),
        'pending_reviews': len([r for r in reviews_data['reviews'] if r['status'] == 'pending']),
        'approved_reviews': len([r for r in reviews_data['reviews'] if r['status'] == 'approved']),
        'average_rating': 0
    }

    # Рассчитываем средний рейтинг
    approved_reviews = [r for r in reviews_data['reviews'] if r['status'] == 'approved']
    if approved_reviews:
        stats['average_rating'] = sum([r['rating'] for r in approved_reviews]) / len(approved_reviews)

    return stats


# ========== ИНИЦИАЛИЗАЦИЯ ==========
def init_databases():
    """Инициализирует базы данных при первом запуске"""
    # Создаем файлы если их нет
    _read_json(DB_FILE)
    _read_json(REVIEWS_FILE)
    print("✅ Базы данных инициализированы")
    print(f"   - Заявки: {DB_FILE}")
    print(f"   - Отзывы: {REVIEWS_FILE}")


# Инициализация при импорте
init_databases()