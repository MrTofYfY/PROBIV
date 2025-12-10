import os
import logging
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from enum import Enum
import aiohttp
import asyncio

from dotenv import load_dotenv
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ChatPermissions,
    ChatMember,
    User,
    Chat,
    MenuButtonCommands
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    ContextTypes, 
    filters,
    ConversationHandler
)
from telegram.constants import ParseMode, ChatMemberStatus, ChatType

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

# Состояния
class States(Enum):
    WAITING_API_KEY = 1
    SET_RULES = 2
    SET_WELCOME = 3
    AI_CHAT = 4

# Файлы для хранения данных
DATA_DIR = Path("data")
CHANNELS_FILE = DATA_DIR / "channels.json"
USERS_FILE = DATA_DIR / "users.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
CHANNEL_SETTINGS_FILE = DATA_DIR / "channel_settings.json"
AI_SETTINGS_FILE = DATA_DIR / "ai_settings.json"

# Убедимся, что директория существует
DATA_DIR.mkdir(exist_ok=True)

class AIService:
    """Сервис для работы с OpenAI API"""
    
    def __init__(self):
        self.ai_settings = self.load_ai_settings()
        self.session = None
    
    def load_ai_settings(self) -> dict:
        """Загрузка настроек ИИ"""
        try:
            if AI_SETTINGS_FILE.exists():
                with open(AI_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек ИИ: {e}")
        return {"enabled": False, "api_key": "", "model": "gpt-3.5-turbo"}
    
    def save_ai_settings(self, settings: dict):
        """Сохранение настроек ИИ"""
        try:
            with open(AI_SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек ИИ: {e}")
    
    def is_enabled(self) -> bool:
        """Проверка, включен ли ИИ"""
        return self.ai_settings.get("enabled", False) and self.ai_settings.get("api_key", "")
    
    def get_api_key(self) -> str:
        """Получение API ключа"""
        return self.ai_settings.get("api_key", "")
    
    def enable_ai(self, api_key: str, model: str = "gpt-3.5-turbo"):
        """Включение ИИ"""
        self.ai_settings = {
            "enabled": True,
            "api_key": api_key,
            "model": model,
            "enabled_at": datetime.now().isoformat()
        }
        self.save_ai_settings(self.ai_settings)
    
    def disable_ai(self):
        """Выключение ИИ"""
        self.ai_settings = {"enabled": False, "api_key": "", "model": ""}
        self.save_ai_settings(self.ai_settings)
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Получение или создание сессии"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def chat_completion(self, message: str, context: str = "") -> Tuple[bool, str]:
        """
        Отправка запроса к OpenAI API
        
        Returns: (success, response)
        """
        if not self.is_enabled():
            return False, "ИИ не настроен. Включите его в настройках бота."
        
        api_key = self.get_api_key()
        model = self.ai_settings.get("model", "gpt-3.5-turbo")
        
        try:
            session = await self.get_session()
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Используем официальный OpenAI API
            url = "https://api.openai.com/v1/chat/completions"
            
            # Формируем промпт с контекстом
            system_message = "Ты полезный помощник в Telegram-боте для управления каналами. Отвечай кратко и по делу."
            if context:
                system_message += f"\nКонтекст: {context}"
            
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": message}
                ],
                "max_tokens": 500,
                "temperature": 0.7
            }
            
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return True, result["choices"][0]["message"]["content"].strip()
                elif response.status == 401:
                    return False, "❌ Неверный API ключ. Проверьте ключ и попробуйте снова."
                elif response.status == 429:
                    return False, "⚠️ Превышен лимит запросов. Попробуйте позже."
                else:
                    error_text = await response.text()
                    return False, f"❌ Ошибка API: {response.status}"
                    
        except Exception as e:
            logger.error(f"Ошибка запроса к OpenAI: {e}")
            return False, "❌ Ошибка подключения к ИИ. Проверьте интернет-соединение."

class ChannelManagerBot:
    def __init__(self):
        self.channels_data = self.load_json(CHANNELS_FILE)
        self.users_data = self.load_json(USERS_FILE)
        self.settings_data = self.load_json(SETTINGS_FILE)
        self.channel_settings_data = self.load_json(CHANNEL_SETTINGS_FILE)
        self.ai_service = AIService()
        
        # Настройки по умолчанию
        if "bot_name" not in self.settings_data:
            self.settings_data["bot_name"] = "🤖 Channel Manager AI"
        if "bot_version" not in self.settings_data:
            self.settings_data["bot_version"] = "4.0"
        self.save_settings()
    
    def load_json(self, file_path: Path) -> dict:
        """Загрузка данных из JSON файла"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки {file_path}: {e}")
        return {}
    
    def save_json(self, data: dict, file_path: Path):
        """Сохранение данных в JSON файл"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения {file_path}: {e}")
    
    def save_settings(self):
        """Сохранение настроек"""
        self.save_json(self.settings_data, SETTINGS_FILE)
    
    def get_user_channels(self, user_id: int) -> List[Dict]:
        """Получение каналов пользователя"""
        user_str = str(user_id)
        if user_str in self.channels_data:
            return self.channels_data[user_str]
        return []
    
    def add_channel(self, user_id: int, channel_data: Dict):
        """Добавление канала пользователя"""
        user_str = str(user_id)
        if user_str not in self.channels_data:
            self.channels_data[user_str] = []
        
        # Проверяем, нет ли уже такого канала
        for channel in self.channels_data[user_str]:
            if channel.get("id") == channel_data.get("id"):
                return False
        
        self.channels_data[user_str].append(channel_data)
        self.save_json(self.channels_data, CHANNELS_FILE)
        return True
    
    def remove_channel(self, user_id: int, channel_id: int):
        """Удаление канала"""
        user_str = str(user_id)
        if user_str in self.channels_data:
            self.channels_data[user_str] = [
                ch for ch in self.channels_data[user_str] 
                if ch.get("id") != channel_id
            ]
            self.save_json(self.channels_data, CHANNELS_FILE)
            return True
        return False
    
    def get_channel_settings(self, channel_id: int) -> Dict:
        """Получение настроек канала"""
        channel_str = str(channel_id)
        if channel_str not in self.channel_settings_data:
            self.channel_settings_data[channel_str] = {
                "auto_post": False,
                "schedule_posts": False,
                "delete_commands": True,
                "notify_new_members": True,
                "welcome_message": "Добро пожаловать в канал!",
                "rules": "Правила канала ещё не установлены.",
                "ai_assistant": False,  # ИИ ассистент для канала
                "admins": [],
                "moderators": [],
                "created_at": datetime.now().isoformat(),
                "stats": {
                    "messages_today": 0,
                    "members": 0,
                    "bans": 0
                }
            }
        return self.channel_settings_data[channel_str]
    
    def save_channel_settings(self, channel_id: int, settings: Dict):
        """Сохранение настроек канала"""
        self.channel_settings_data[str(channel_id)] = settings
        self.save_json(self.channel_settings_data, CHANNEL_SETTINGS_FILE)

# Инициализация менеджера
manager = ChannelManagerBot()

# ==================== ИНЛАЙН МЕНЮ С ИИ ====================

def get_welcome_keyboard():
    """Меню приветствия"""
    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить в канал", 
                               url=f"https://t.me/{BOT_TOKEN.split(':')[0]}?startchannel=true"),
            InlineKeyboardButton("👥 Мои каналы", callback_data="my_channels")
        ],
        [
            InlineKeyboardButton("🤖 ИИ Ассистент", callback_data="ai_assistant"),
            InlineKeyboardButton("⚙️ Настройки ИИ", callback_data="ai_settings")
        ],
        [
            InlineKeyboardButton("📚 Команды", callback_data="help_commands"),
            InlineKeyboardButton("⚙️ Общие настройки", callback_data="user_settings")
        ],
        [
            InlineKeyboardButton("⭐ Оценить бота", 
                               url="https://t.me/storebot?start=channelmanagerbot"),
            InlineKeyboardButton("💬 Поддержка", 
                               url="https://t.me/chatmanager_support")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_channels_list_keyboard(user_id: int):
    """Список каналов пользователя"""
    channels = manager.get_user_channels(user_id)
    
    keyboard = []
    for channel in channels:
        title = channel.get("title", "Без названия")
        channel_id = channel.get("id")
        username = channel.get("username", "")
        
        if username:
            display = f"📢 {title[:20]} (@{username})"
        else:
            display = f"📢 {title[:20]}"
        
        keyboard.append([
            InlineKeyboardButton(display, callback_data=f"channel_{channel_id}")
        ])
    
    if not channels:
        keyboard.append([
            InlineKeyboardButton("📭 У вас нет каналов", callback_data="no_channels")
        ])
    
    keyboard.append([
        InlineKeyboardButton("➕ Добавить новый канал", 
                           url=f"https://t.me/{BOT_TOKEN.split(':')[0]}?startchannel=true"),
        InlineKeyboardButton("🔄 Обновить список", callback_data="refresh_channels")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🤖 ИИ Ассистент", callback_data="ai_assistant"),
        InlineKeyboardButton("🔙 На главную", callback_data="menu_main")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_channel_control_keyboard(channel_id: int):
    """Панель управления каналом с ИИ"""
    settings = manager.get_channel_settings(channel_id)
    
    ai_enabled = "🤖" if settings.get("ai_assistant", False) else "🤖❌"
    auto_post = "✅" if settings["auto_post"] else "❌"
    schedule = "✅" if settings["schedule_posts"] else "❌"
    
    keyboard = [
        [
            InlineKeyboardButton(f"{ai_enabled} ИИ Ассистент", callback_data=f"chset_ai_{channel_id}"),
            InlineKeyboardButton(f"{auto_post} Автопостинг", callback_data=f"chset_autopost_{channel_id}")
        ],
        [
            InlineKeyboardButton("✏️ Приветствие", callback_data=f"chset_welcome_{channel_id}"),
            InlineKeyboardButton("📝 Правила", callback_data=f"chset_rules_{channel_id}")
        ],
        [
            InlineKeyboardButton("👮 Администраторы", callback_data=f"chset_admins_{channel_id}"),
            InlineKeyboardButton("📊 Статистика", callback_data=f"chset_stats_{channel_id}")
        ],
        [
            InlineKeyboardButton("👥 Участники", callback_data=f"chset_members_{channel_id}"),
            InlineKeyboardButton("⚡ Быстрые посты", callback_data=f"chset_quickpost_{channel_id}")
        ],
        [
            InlineKeyboardButton("🔧 Расширенные настройки", callback_data=f"chset_advanced_{channel_id}"),
            InlineKeyboardButton("🔄 Обновить", callback_data=f"chset_refresh_{channel_id}")
        ],
        [
            InlineKeyboardButton("🤖 Чат с ИИ", callback_data="ai_chat"),
            InlineKeyboardButton("🔙 К списку каналов", callback_data="my_channels")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_ai_settings_keyboard():
    """Настройки ИИ"""
    ai_enabled = manager.ai_service.is_enabled()
    status = "✅ ВКЛЮЧЕН" if ai_enabled else "❌ ВЫКЛЮЧЕН"
    
    keyboard = [
        [
            InlineKeyboardButton(f"Статус: {status}", callback_data="ai_status")
        ],
        [
            InlineKeyboardButton("🔑 Ввести API ключ", callback_data="ai_set_key"),
            InlineKeyboardButton("🚫 Выключить ИИ", callback_data="ai_disable")
        ] if ai_enabled else [
            InlineKeyboardButton("🔑 Ввести API ключ", callback_data="ai_set_key"),
            InlineKeyboardButton("🔄 Проверить ключ", callback_data="ai_test")
        ],
        [
            InlineKeyboardButton("⚙️ Выбор модели", callback_data="ai_model"),
            InlineKeyboardButton("📊 Статистика", callback_data="ai_stats")
        ],
        [
            InlineKeyboardButton("💡 Примеры использования", callback_data="ai_examples"),
            InlineKeyboardButton("❓ Помощь", callback_data="ai_help")
        ],
        [
            InlineKeyboardButton("🔙 На главную", callback_data="menu_main"),
            InlineKeyboardButton("👥 Мои каналы", callback_data="my_channels")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_ai_chat_keyboard():
    """Клавиатура для чата с ИИ"""
    keyboard = [
        [
            InlineKeyboardButton("💡 Примеры запросов", callback_data="ai_examples"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="ai_settings")
        ],
        [
            InlineKeyboardButton("📝 Сгенерировать пост", callback_data="ai_generate_post"),
            InlineKeyboardButton("🎯 Анализ канала", callback_data="ai_analyze")
        ],
        [
            InlineKeyboardButton("🔙 На главную", callback_data="menu_main"),
            InlineKeyboardButton("👥 Мои каналы", callback_data="my_channels")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_model_selection_keyboard():
    """Выбор модели ИИ"""
    keyboard = [
        [
            InlineKeyboardButton("🤖 GPT-3.5 Turbo (быстрый)", callback_data="ai_model_gpt35"),
            InlineKeyboardButton("🧠 GPT-4 (качественный)", callback_data="ai_model_gpt4")
        ],
        [
            InlineKeyboardButton("🎯 GPT-4 Turbo", callback_data="ai_model_gpt4t"),
            InlineKeyboardButton("💰 GPT-3.5 Turbo 16K", callback_data="ai_model_gpt35_16k")
        ],
        [
            InlineKeyboardButton("🔙 Назад", callback_data="ai_settings")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== ОСНОВНЫЕ КОМАНДЫ ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    
    if context.args and "startchannel" in context.args[0]:
        await update.message.reply_text(
            "✅ *Бот успешно добавлен в канал!*\n\n"
            "Теперь назначьте бота администратором канала "
            "и обновите список каналов.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Обновить список", callback_data="refresh_channels")
            ]])
        )
        return
    
    # Проверяем, включен ли ИИ
    ai_status = "✅ ВКЛЮЧЕН" if manager.ai_service.is_enabled() else "❌ ВЫКЛЮЧЕН"
    
    welcome_text = f"""
🎉 *Добро пожаловать, {user.first_name}!*

Я — *{manager.settings_data['bot_name']}*, умный менеджер каналов с ИИ!

✨ *Мои возможности:*
• 📢 Управление каналами Telegram
• 🤖 ИИ-ассистент для контента
• ⚙️ Автоматизация публикаций
• 📊 Детальная аналитика
• 🛡️ Модерация и управление

🤖 *ИИ Ассистент:* {ai_status}

🚀 *Чтобы начать:*
1. Добавьте меня в ваш канал
2. Назначьте администратором
3. Настройте ИИ для умных функций

👇 *Выберите действие:*
    """
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_welcome_keyboard()
    )

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /ai - управление ИИ"""
    ai_enabled = manager.ai_service.is_enabled()
    
    if not ai_enabled:
        text = """
🤖 *ИИ Ассистент*

ИИ функционал отключен. Чтобы включить:

1. Получите API ключ на platform.openai.com
2. Введите ключ в настройках ИИ
3. Настройте модель по желанию

Стоимость: ~$0.002 за 1K токенов
        """
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔑 Ввести API ключ", callback_data="ai_set_key"),
            InlineKeyboardButton("🔙 На главную", callback_data="menu_main")
        ]])
    else:
        text = """
🤖 *ИИ Ассистент включен*

Теперь вы можете:
• Общаться с ИИ в личных сообщениях
• Генерировать контент для каналов
• Получать аналитику и советы
• Автоматизировать публикации

Используйте кнопки ниже для управления.
        """
        keyboard = get_ai_settings_keyboard()
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )

# ==================== ОБРАБОТЧИКИ КНОПОК ДЛЯ ИИ ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на инлайн-кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    
    # Главное меню
    if data == "menu_main":
        await query.edit_message_text(
            "🏠 *Главное меню*\n\nВыберите действие:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_welcome_keyboard()
        )
    
    # Настройки ИИ
    elif data == "ai_settings":
        ai_enabled = manager.ai_service.is_enabled()
        
        if ai_enabled:
            api_key = manager.ai_service.get_api_key()
            masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
            
            text = f"""
⚙️ *Настройки ИИ Ассистента*

✅ *Статус:* Включен
🔑 *API ключ:* `{masked_key}`
🧠 *Модель:* {manager.ai_service.ai_settings.get('model', 'gpt-3.5-turbo')}

*Доступные действия:*
            """
        else:
            text = """
⚙️ *Настройк
