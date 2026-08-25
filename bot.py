import os
import asyncio
import logging
import json
import os
import time
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)

# ============ КОНФИГ ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "8931378017:AAFUr0_NdN8hcaZ1djEG1VH1qizjp5QPdIM")

# 🔽 ТРИ КАНАЛА ДЛЯ ПОДПИСКИ 🔽
REQUIRED_CHANNELS = [
    {
        "id": "@spookyscripts",
        "link": "https://t.me/spookyscripts",
        "name": "Spooky Scripts"
    },
    {
        "id": -1003788328996,
        "link": "https://t.me/+GMHDq5Fij2M5MmFh",
        "name": "Spooky mod"
    },
    {
        "id": -1004356916182,
        "link": "https://t.me/+GIrw6Qj8tkZiMzhh",
        "name": "OUTLOW SCRIPTS"
    }
]

ADMIN_IDS = [6621617827, 7326365411]
# ================================

storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# Файлы для хранения
COMMANDS_FILE = "hidden_commands.json"
USERS_FILE = "users_stats.json"

# Статистика бота
bot_stats = {
    "start_time": time.time(),
    "messages_processed": 0,
    "commands_used": 0,
    "errors": 0
}

# Загрузка/сохранение команд
def load_commands():
    if os.path.exists(COMMANDS_FILE):
        with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_commands(commands):
    with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(commands, f, ensure_ascii=False, indent=2)

hidden_commands = load_commands()

# Загрузка/сохранение статистики пользователей
def load_users_stats():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users_stats(stats):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

users_stats = load_users_stats()

# --- Состояния FSM ---
class AddCommandStates(StatesGroup):
    waiting_for_command_name = State()
    waiting_for_text = State()
    waiting_for_media = State()

# ==================== РАБОТА СО СТАТИСТИКОЙ ====================

def update_user_stats(user_id: int, username: str = None, first_name: str = None):
    """Обновляет статистику пользователя"""
    now = time.time()
    today = datetime.now().strftime('%Y-%m-%d')
    user_id_str = str(user_id)
    
    if user_id_str not in users_stats:
        users_stats[user_id_str] = {
            "first_seen": now,
            "last_seen": now,
            "first_name": first_name or "",
            "username": username or "",
            "total_visits": 0,
            "daily_visits": {},
            "total_commands": 0
        }
    
    user = users_stats[user_id_str]
    user["last_seen"] = now
    user["total_visits"] += 1
    
    if first_name:
        user["first_name"] = first_name
    if username:
        user["username"] = username
    
    if today not in user["daily_visits"]:
        user["daily_visits"][today] = 0
    user["daily_visits"][today] += 1
    
    save_users_stats(users_stats)

def get_user_stats(user_id: int) -> dict:
    """Получает статистику пользователя"""
    user_id_str = str(user_id)
    if user_id_str not in users_stats:
        return None
    
    user = users_stats[user_id_str]
    now = time.time()
    first_seen = datetime.fromtimestamp(user["first_seen"])
    last_seen = datetime.fromtimestamp(user["last_seen"])
    
    total_seconds = now - user["first_seen"]
    days = int(total_seconds // 86400)
    hours = int((total_seconds % 86400) // 3600)
    minutes = int((total_seconds % 3600) // 60)
    
    today = datetime.now().strftime('%Y-%m-%d')
    today_visits = user["daily_visits"].get(today, 0)
    
    week_visits = 0
    month_visits = 0
    year_visits = 0
    
    now_date = datetime.now()
    for date, count in user["daily_visits"].items():
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            days_diff = (now_date - date_obj).days
            if days_diff <= 7:
                week_visits += count
            if days_diff <= 30:
                month_visits += count
            if days_diff <= 365:
                year_visits += count
        except:
            pass
    
    total_commands = user.get("total_commands", 0)
    
    return {
        "user_id": user_id,
        "first_name": user.get("first_name", "Неизвестно"),
        "username": user.get("username"),
        "first_seen": first_seen.strftime('%d.%m.%Y %H:%M'),
        "last_seen": last_seen.strftime('%d.%m.%Y %H:%M'),
        "total_seconds": total_seconds,
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "total_visits": user["total_visits"],
        "today_visits": today_visits,
        "week_visits": week_visits,
        "month_visits": month_visits,
        "year_visits": year_visits,
        "total_commands": total_commands,
        "daily_visits": user["daily_visits"]
    }

def get_all_users_stats() -> list:
    """Получает статистику всех пользователей"""
    result = []
    for user_id_str, data in users_stats.items():
        try:
            user_id = int(user_id_str)
            stats = get_user_stats(user_id)
            if stats:
                result.append(stats)
        except:
            continue
    # Сортируем по количеству визитов (по убыванию)
    result.sort(key=lambda x: x['total_visits'], reverse=True)
    return result

# ==================== ПРОВЕРКА ПОДПИСКИ ====================

async def is_user_subscribed(user_id: int) -> bool:
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel["id"], user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            return False
    return True

def get_subscription_keyboard():
    keyboard = []
    for channel in REQUIRED_CHANNELS:
        keyboard.append([InlineKeyboardButton(
            text=f"📢 Подписаться на {channel['name']}", 
            url=channel["link"]
        )])
    keyboard.append([InlineKeyboardButton(
        text="🔄 Проверить подписку", 
        callback_data="check_sub"
    )])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ==================== МОНИТОРИНГ СКОРОСТИ ====================

async def check_bot_speed() -> dict:
    uptime_seconds = time.time() - bot_stats["start_time"]
    uptime_hours = uptime_seconds // 3600
    uptime_minutes = (uptime_seconds % 3600) // 60
    uptime_seconds_formatted = uptime_seconds % 60
    
    ping_times = []
    for _ in range(3):
        try:
            start_ping = time.time()
            await bot.get_me()
            ping = round((time.time() - start_ping) * 1000)
            ping_times.append(ping)
        except:
            ping_times.append(None)
    
    valid_pings = [p for p in ping_times if p is not None]
    avg_ping = round(sum(valid_pings) / len(valid_pings)) if valid_pings else "❌ Ошибка"
    min_ping = min(valid_pings) if valid_pings else "❌"
    max_ping = max(valid_pings) if valid_pings else "❌"
    
    return {
        "uptime": f"{int(uptime_hours)}ч {int(uptime_minutes)}м {int(uptime_seconds_formatted)}с",
        "avg_ping": avg_ping,
        "min_ping": min_ping,
        "max_ping": max_ping,
        "messages": bot_stats["messages_processed"],
        "commands": bot_stats["commands_used"],
        "errors": bot_stats["errors"],
        "hidden_commands": len(hidden_commands),
        "last_check": datetime.now().strftime('%H:%M:%S')
    }

# ==================== ФУНКЦИЯ ОТПРАВКИ КОМАНДЫ ====================

async def send_command_response(message: types.Message, command_data: dict):
    text = command_data.get('text', '')
    media_type = command_data.get('media_type')
    media_file_id = command_data.get('media_file_id')
    
    if media_type == 'photo':
        await message.answer_photo(photo=media_file_id, caption=text, parse_mode="HTML")
    elif media_type == 'video':
        await message.answer_video(video=media_file_id, caption=text, parse_mode="HTML")
    elif media_type == 'document':
        await message.answer_document(document=media_file_id, caption=text, parse_mode="HTML")
    elif media_type == 'animation':
        await message.answer_animation(animation=media_file_id, caption=text, parse_mode="HTML")
    elif media_type == 'audio':
        await message.answer_audio(audio=media_file_id, caption=text, parse_mode="HTML")
    elif media_type == 'voice':
        await message.answer_voice(voice=media_file_id, caption=text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")

# ==================== ОБРАБОТЧИКИ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    bot_stats["messages_processed"] += 1
    
    update_user_stats(
        user_id, 
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    
    args = message.text.split()
    if len(args) >= 2:
        command_name = args[1]
        if command_name in hidden_commands:
            bot_stats["commands_used"] += 1
            
            if str(user_id) in users_stats:
                users_stats[str(user_id)]["total_commands"] += 1
                save_users_stats(users_stats)
            
            if not await is_user_subscribed(user_id):
                keyboard = get_subscription_keyboard()
                await message.answer(
                    "⚠️ Для доступа к этой команде подпишитесь на все каналы:",
                    reply_markup=keyboard
                )
                return
            
            await send_command_response(message, hidden_commands[command_name])
            return
    
    if not await is_user_subscribed(user_id):
        keyboard = get_subscription_keyboard()
        await message.answer(
            "⚠️ Для использования бота подпишитесь на все каналы:",
            reply_markup=keyboard
        )
        return
    
    if is_admin(user_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")]
        ])
        await message.answer(
            "👋 Добро пожаловать, Админ!\n"
            "Нажмите кнопку для управления ботом.",
            reply_markup=keyboard
        )
    else:
        await message.answer("✅ Добро пожаловать! Вы подписаны на все каналы.")

# --- КОМАНДА /info ---
@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    """Показывает статистику пользователя по ID или username"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "❌ **Использование:** `/info @username` или `/info 123456789`\n\n"
            "Примеры:\n"
            "• `/info @spookyscripts`\n"
            "• `/info 6621617827`",
            parse_mode="Markdown"
        )
        return
    
    query = args[1]
    target_user_id = None
    
    # Проверяем, что это ID (число)
    if query.isdigit():
        target_user_id = int(query)
    else:
        # Это username, ищем в базе
        username = query.replace('@', '').lower()
        for user_id_str, data in users_stats.items():
            if data.get('username', '').lower() == username:
                target_user_id = int(user_id_str)
                break
    
    if not target_user_id or str(target_user_id) not in users_stats:
        await message.answer("❌ Пользователь не найден в базе данных!")
        return
    
    stats = get_user_stats(target_user_id)
    if not stats:
        await message.answer("❌ Пользователь не найден!")
        return
    
    username_display = f"@{stats['username']}" if stats['username'] else "❌ нету username"
    
    time_str = ""
    if stats['days'] > 0:
        time_str += f"{stats['days']}д "
    if stats['hours'] > 0:
        time_str += f"{stats['hours']}ч "
    time_str += f"{stats['minutes']}м"
    
    info_text = f"""
👤 **Информация о пользователе**
━━━━━━━━━━━━━━━━━━

🆔 **ID:** `{stats['user_id']}`
📛 **Имя:** {stats['first_name']}
🔗 **Username:** {username_display}

━━━━━━━━━━━━━━━━━━
⏱ **Время в боте:** {time_str}
📅 **Впервые:** {stats['first_seen']}
🕐 **Последний раз:** {stats['last_seen']}

━━━━━━━━━━━━━━━━━━
📊 **Активность:**
• Всего визитов: {stats['total_visits']}
• Сегодня: {stats['today_visits']}
• За неделю: {stats['week_visits']}
• За месяц: {stats['month_visits']}
• За год: {stats['year_visits']}
• Команд активировано: {stats['total_commands']}
    """
    
    await message.answer(info_text, parse_mode="Markdown")

# --- АДМИН-ПАНЕЛЬ ---
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return
    
    total_users = len(users_stats)
    total_commands_all = sum(u.get('total_commands', 0) for u in users_stats.values())
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Моя статистика", callback_data="my_stats")],
        [InlineKeyboardButton(text="📊 Статистика всех пользователей", callback_data="all_users_stats")],
        [InlineKeyboardButton(text="⚡ Проверить скорость", callback_data="check_speed")],
        [InlineKeyboardButton(text="➕ Добавить команду", callback_data="add_command")],
        [InlineKeyboardButton(text="📋 Список команд", callback_data="list_commands")],
        [InlineKeyboardButton(text="❌ Удалить команду", callback_data="delete_command")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_start")]
    ])
    
    try:
        await callback.message.edit_text(
            f"⚙️ **Админ-панель**\n\n"
            f"👥 **Всего пользователей:** {total_users}\n"
            f"🎯 **Всего команд активировано:** {total_commands_all}\n"
            f"📁 **Скрытых команд:** {len(hidden_commands)}\n\n"
            "📊 **Статистика всех пользователей** - список всех юзеров\n"
            "👤 **Моя статистика** - ваша активность в боте\n"
            "⚡ **Проверить скорость** - задержка бота\n"
            "➕ **Добавить команду** - создайте скрытую команду",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()

# --- СТАТИСТИКА ВСЕХ ПОЛЬЗОВАТЕЛЕЙ ---
@dp.callback_query(F.data == "all_users_stats")
async def all_users_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return
    
    all_stats = get_all_users_stats()
    
    if not all_stats:
        await callback.message.edit_text(
            "📭 **Нет пользователей**\n\n"
            "Пока никто не использовал бота.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
            ]),
            parse_mode="Markdown"
        )
        await callback.answer()
        return
    
    # Формируем список (топ-20)
    text = "📊 **Статистика всех пользователей**\n"
    text += f"👥 Всего: {len(all_stats)}\n━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, stats in enumerate(all_stats[:20], 1):
        username_display = f"@{stats['username']}" if stats['username'] else "нет"
        time_str = ""
        if stats['days'] > 0:
            time_str += f"{stats['days']}д "
        if stats['hours'] > 0:
            time_str += f"{stats['hours']}ч "
        time_str += f"{stats['minutes']}м"
        
        text += f"{i}. **{stats['first_name']}**\n"
        text += f"   🆔 `{stats['user_id']}`\n"
        text += f"   🔗 {username_display}\n"
        text += f"   👁 Визитов: {stats['total_visits']} | ⏱ {time_str}\n"
        text += f"   📅 Посл. визит: {stats['last_seen']}\n\n"
    
    if len(all_stats) > 20:
        text += f"... и ещё {len(all_stats) - 20} пользователей"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="all_users_stats")],
        [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_panel")]
    ])
    
    try:
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()

# --- СТАТИСТИКА ПОЛЬЗОВАТЕЛЯ ---
@dp.callback_query(F.data == "my_stats")
async def my_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return
    
    user_id = callback.from_user.id
    stats = get_user_stats(user_id)
    
    if not stats:
        await callback.answer("❌ Статистика не найдена!", show_alert=True)
        return
    
    username_display = f"@{stats['username']}" if stats['username'] else "❌ нету username"
    
    time_str = ""
    if stats['days'] > 0:
        time_str += f"{stats['days']}д "
    if stats['hours'] > 0:
        time_str += f"{stats['hours']}ч "
    time_str += f"{stats['minutes']}м"
    
    stats_text = f"""
👤 **Моя статистика**
━━━━━━━━━━━━━━━━━━

📛 **Имя:** {stats['first_name']}
🔗 **Username:** {username_display}
🆔 **ID:** `{stats['user_id']}`

━━━━━━━━━━━━━━━━━━
⏱ **Время в боте:** {time_str}
📅 **Впервые:** {stats['first_seen']}
🕐 **Последний раз:** {stats['last_seen']}

━━━━━━━━━━━━━━━━━━
📊 **Активность:**
• Всего визитов: {stats['total_visits']}
• Сегодня: {stats['today_visits']}
• За неделю: {stats['week_visits']}
• За месяц: {stats['month_visits']}
• За год: {stats['year_visits']}
• Команд активировано: {stats['total_commands']}
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="my_stats")],
        [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_panel")]
    ])
    
    try:
        await callback.message.edit_text(
            stats_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()

# ==================== ДОБАВЛЕНИЕ КОМАНДЫ ====================

@dp.callback_query(F.data == "add_command")
async def add_command_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return
    
    try:
        await callback.message.edit_text(
            "📝 **Шаг 1 из 2: Название команды**\n\n"
            "Введите **название команды** (латиницей, без пробелов):\n"
            "Пример: `special_offer`\n\n"
            "⚠️ Команда будет скрыта и доступна только по ссылке.\n\n"
            "❌ Для отмены отправьте /cancel",
            parse_mode="Markdown"
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            raise
    await state.set_state(AddCommandStates.waiting_for_command_name)
    await callback.answer()

@dp.message(Command("cancel"))
async def cancel_add_command(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Создание команды отменено.")

@dp.message(StateFilter(AddCommandStates.waiting_for_command_name))
async def add_command_get_name(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен!")
        return
    
    command_name = message.text.strip().replace(" ", "_")
    
    if command_name in hidden_commands:
        await message.answer("❌ Команда с таким именем уже существует! Введите другое имя.")
        return
    
    await state.update_data(command_name=command_name)
    await state.set_state(AddCommandStates.waiting_for_media)
    
    await message.answer(
        f"✅ Имя команды: `{command_name}`\n\n"
        "📝 **Шаг 2 из 2: Отправьте контент**\n\n"
        "Теперь просто отправьте:\n"
        "• 📝 **Текст** (с HTML-разметкой)\n"
        "• 📷 **Фото**\n"
        "• 🎬 **Видео**\n"
        "• 📄 **Файл** (документ)\n"
        "• 🎥 **GIF-анимацию**\n"
        "• 🎵 **Аудио**\n"
        "• 🎤 **Голосовое сообщение**\n\n"
        "⚠️ Если отправите медиа без текста - команда сохранится с пустым текстом.\n"
        "⚠️ Если отправите текст - команда сохранится без медиа.\n\n"
        "❌ Отмена: /cancel",
        parse_mode="Markdown"
    )

# --- АВТОМАТИЧЕСКОЕ ОПРЕДЕЛЕНИЕ ТИПА ---

@dp.message(StateFilter(AddCommandStates.waiting_for_media), F.text)
async def get_command_text(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    command_name = data.get('command_name')
    text = message.text
    
    existing_media = data.get('media_type')
    
    if existing_media:
        hidden_commands[command_name]['text'] = text
        save_commands(hidden_commands)
        await show_command_created(message, command_name, text, hidden_commands[command_name])
        await state.clear()
    else:
        hidden_commands[command_name] = {
            "text": text,
            "media_type": None,
            "media_file_id": None
        }
        save_commands(hidden_commands)
        await show_command_created(message, command_name, text, hidden_commands[command_name])
        await state.clear()

@dp.message(StateFilter(AddCommandStates.waiting_for_media), F.photo)
async def get_command_photo(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    command_name = data.get('command_name')
    text = message.caption or ""
    
    photo = message.photo[-1]
    
    hidden_commands[command_name] = {
        "text": text,
        "media_type": 'photo',
        "media_file_id": photo.file_id
    }
    save_commands(hidden_commands)
    await show_command_created(message, command_name, text, hidden_commands[command_name])
    await state.clear()

@dp.message(StateFilter(AddCommandStates.waiting_for_media), F.video)
async def get_command_video(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    command_name = data.get('command_name')
    text = message.caption or ""
    
    video = message.video
    
    hidden_commands[command_name] = {
        "text": text,
        "media_type": 'video',
        "media_file_id": video.file_id
    }
    save_commands(hidden_commands)
    await show_command_created(message, command_name, text, hidden_commands[command_name])
    await state.clear()

@dp.message(StateFilter(AddCommandStates.waiting_for_media), F.document)
async def get_command_document(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    command_name = data.get('command_name')
    text = message.caption or ""
    
    document = message.document
    
    hidden_commands[command_name] = {
        "text": text,
        "media_type": 'document',
        "media_file_id": document.file_id
    }
    save_commands(hidden_commands)
    await show_command_created(message, command_name, text, hidden_commands[command_name])
    await state.clear()

@dp.message(StateFilter(AddCommandStates.waiting_for_media), F.animation)
async def get_command_gif(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    command_name = data.get('command_name')
    text = message.caption or ""
    
    animation = message.animation
    
    hidden_commands[command_name] = {
        "text": text,
        "media_type": 'animation',
        "media_file_id": animation.file_id
    }
    save_commands(hidden_commands)
    await show_command_created(message, command_name, text, hidden_commands[command_name])
    await state.clear()

@dp.message(StateFilter(AddCommandStates.waiting_for_media), F.audio)
async def get_command_audio(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    command_name = data.get('command_name')
    text = message.caption or ""
    
    audio = message.audio
    
    hidden_commands[command_name] = {
        "text": text,
        "media_type": 'audio',
        "media_file_id": audio.file_id
    }
    save_commands(hidden_commands)
    await show_command_created(message, command_name, text, hidden_commands[command_name])
    await state.clear()

@dp.message(StateFilter(AddCommandStates.waiting_for_media), F.voice)
async def get_command_voice(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    command_name = data.get('command_name')
    text = message.caption or ""
    
    voice = message.voice
    
    hidden_commands[command_name] = {
        "text": text,
        "media_type": 'voice',
        "media_file_id": voice.file_id
    }
    save_commands(hidden_commands)
    await show_command_created(message, command_name, text, hidden_commands[command_name])
    await state.clear()

# --- ФУНКЦИЯ ПОКАЗА ГОТОВОЙ КОМАНДЫ ---
async def show_command_created(message: types.Message, command_name: str, text: str, command_data: dict):
    bot_username = (await bot.get_me()).username
    bot_link = f"https://t.me/{bot_username}?start={command_name}"
    
    media_emoji = "📝"
    media_name = "нет"
    if command_data.get('media_type') == 'photo':
        media_emoji = "📷"
        media_name = "фото"
    elif command_data.get('media_type') == 'video':
        media_emoji = "🎬"
        media_name = "видео"
    elif command_data.get('media_type') == 'document':
        media_emoji = "📄"
        media_name = "файл"
    elif command_data.get('media_type') == 'animation':
        media_emoji = "🎥"
        media_name = "GIF"
    elif command_data.get('media_type') == 'audio':
        media_emoji = "🎵"
        media_name = "аудио"
    elif command_data.get('media_type') == 'voice':
        media_emoji = "🎤"
        media_name = "голосовое"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Ссылка-кнопка", url=bot_link)],
        [InlineKeyboardButton(text="📋 Копировать ссылку", callback_data=f"copy_{command_name}")],
        [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_panel")]
    ])
    
    result_text = (
        f"✅ **Команда создана!**\n\n"
        f"📌 Имя: `{command_name}`\n"
        f"📝 Текст: {text[:100] if text else '❌ нет'}\n"
        f"📎 Медиа: {media_emoji} {media_name}\n\n"
        f"🔗 **Ссылка для кнопки:**\n"
        f"`{bot_link}`\n\n"
        f"⚠️ Эту команду нельзя вызвать через /start - только по ссылке!"
    )
    
    media_type = command_data.get('media_type')
    media_file_id = command_data.get('media_file_id')
    
    if media_type == 'photo':
        await message.answer_photo(photo=media_file_id, caption=result_text, reply_markup=keyboard, parse_mode="Markdown")
    elif media_type == 'video':
        await message.answer_video(video=media_file_id, caption=result_text, reply_markup=keyboard, parse_mode="Markdown")
    elif media_type == 'document':
        await message.answer_document(document=media_file_id, caption=result_text, reply_markup=keyboard, parse_mode="Markdown")
    elif media_type == 'animation':
        await message.answer_animation(animation=media_file_id, caption=result_text, reply_markup=keyboard, parse_mode="Markdown")
    elif media_type == 'audio':
        await message.answer_audio(audio=media_file_id, caption=result_text, reply_markup=keyboard, parse_mode="Markdown")
    elif media_type == 'voice':
        await message.answer_voice(voice=media_file_id, caption=result_text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await message.answer(result_text, reply_markup=keyboard, parse_mode="Markdown")

# ==================== ОСТАЛЬНЫЕ ФУНКЦИИ ====================

@dp.callback_query(F.data == "check_speed")
async def check_speed(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return
    
    try:
        await callback.message.edit_text(
            "⏳ **Измерение скорости бота...**\n"
            "Выполняется 3 замера...",
            parse_mode="Markdown"
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            raise
    
    try:
        stats = await check_bot_speed()
        
        if isinstance(stats["avg_ping"], int):
            if stats["avg_ping"] < 200:
                speed_emoji = "🟢"
                speed_status = "Отлично 🚀"
            elif stats["avg_ping"] < 500:
                speed_emoji = "🟡"
                speed_status = "Нормально ⚡"
            elif stats["avg_ping"] < 1000:
                speed_emoji = "🟠"
                speed_status = "Медленно 🐢"
            else:
                speed_emoji = "🔴"
                speed_status = "Критично ❌"
        else:
            speed_emoji = "❌"
            speed_status = "Ошибка замера"
        
        speed_text = f"""
{speed_emoji} **⚡ СКОРОСТЬ БОТА**
━━━━━━━━━━━━━━━━━━

📡 **Задержка (пинг):**
• Средняя: {stats['avg_ping']} мс
• Минимальная: {stats['min_ping']} мс  
• Максимальная: {stats['max_ping']} мс

📊 **Статус:** {speed_status}

━━━━━━━━━━━━━━━━━━
⏱ **Время работы:** {stats['uptime']}
📨 **Сообщений:** {stats['messages']}
🎯 **Команд активировано:** {stats['commands']}
📁 **Скрытых команд:** {stats['hidden_commands']}
⚠️ **Ошибок:** {stats['errors']}

🕐 Проверено: {stats['last_check']}
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="check_speed")],
            [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_panel")]
        ])
        
        await callback.message.edit_text(
            speed_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        bot_stats["errors"] += 1
        await callback.message.edit_text(
            f"❌ **Ошибка при проверке скорости:**\n```\n{str(e)}\n```\n\n"
            "Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_panel")]
            ]),
            parse_mode="Markdown"
        )
    
    await callback.answer()

@dp.callback_query(F.data.startswith("copy_"))
async def copy_command_link(callback: types.CallbackQuery):
    command_name = callback.data.replace("copy_", "")
    bot_username = (await bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={command_name}"
    
    await callback.answer(f"🔗 Ссылка скопирована!", show_alert=True)
    await callback.message.answer(
        f"🔗 **Ссылка на команду `{command_name}`:**\n"
        f"`{link}`",
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "list_commands")
async def list_commands(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return
    
    if not hidden_commands:
        try:
            await callback.message.edit_text(
                "📭 **Список команд пуст**\n\n"
                "Добавьте первую команду через админ-панель.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
                ]),
                parse_mode="Markdown"
            )
        except Exception as e:
            if "message is not modified" not in str(e):
                raise
        await callback.answer()
        return
    
    text = "📋 **Список скрытых команд:**\n\n"
    for idx, (name, data) in enumerate(hidden_commands.items(), 1):
        media_emoji = "📝"
        if data.get('media_type') == 'photo':
            media_emoji = "📷"
        elif data.get('media_type') == 'video':
            media_emoji = "🎬"
        elif data.get('media_type') == 'document':
            media_emoji = "📄"
        elif data.get('media_type') == 'animation':
            media_emoji = "🎥"
        elif data.get('media_type') == 'audio':
            media_emoji = "🎵"
        elif data.get('media_type') == 'voice':
            media_emoji = "🎤"
        
        text += f"{idx}. {media_emoji} `{name}`\n"
        text += f"   {data.get('text', '')[:50] if data.get('text') else '❌ без текста'}...\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()

@dp.callback_query(F.data == "delete_command")
async def delete_command_menu(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return
    
    if not hidden_commands:
        await callback.answer("📭 Нет команд для удаления!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for name in hidden_commands.keys():
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"❌ {name}", callback_data=f"del_{name}")
        ])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    
    try:
        await callback.message.edit_text(
            "🗑 **Выберите команду для удаления:**",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer()

@dp.callback_query(F.data.startswith("del_"))
async def delete_command_confirm(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return
    
    command_name = callback.data.replace("del_", "")
    
    if command_name in hidden_commands:
        del hidden_commands[command_name]
        save_commands(hidden_commands)
        await callback.answer(f"✅ Команда {command_name} удалена!", show_alert=True)
        await admin_panel(callback)
    else:
        await callback.answer("❌ Команда не найдена!", show_alert=True)

@dp.callback_query(F.data == "check_sub")
async def check_subscription_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if await is_user_subscribed(user_id):
        if is_admin(user_id):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")]
            ])
            try:
                await callback.message.edit_text(
                    "✅ Подписка на все каналы подтверждена!\n\n"
                    "👋 Добро пожаловать, Админ!",
                    reply_markup=keyboard
                )
            except Exception as e:
                if "message is not modified" not in str(e):
                    raise
        else:
            try:
                await callback.message.edit_text("✅ Подписка на все каналы подтверждена! Добро пожаловать!")
            except Exception as e:
                if "message is not modified" not in str(e):
                    raise
    else:
        keyboard = get_subscription_keyboard()
        try:
            await callback.message.edit_text(
                "❌ Вы ещё не подписались на все каналы!\n\n"
                "Подпишитесь и нажмите 'Проверить подписку':",
                reply_markup=keyboard
            )
        except Exception as e:
            if "message is not modified" not in str(e):
                raise

@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: types.CallbackQuery):
    await cmd_start(callback.message)
    await callback.answer()

# --- ЗАПУСК ---
async def main():
    me = await bot.get_me()
    print(f"🤖 Бот запущен! Username: @{me.username}")
    print(f"📁 Загружено команд: {len(hidden_commands)}")
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"👥 Всего пользователей: {len(users_stats)}")
    print(f"📢 Обязательные каналы (3):")
    for channel in REQUIRED_CHANNELS:
        print(f"   - {channel['name']}: {channel['link']}")
    print(f"⚡ Мониторинг скорости активен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
