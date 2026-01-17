import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple
import discord


def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()

    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER, guild_id INTEGER, balance REAL, 
                  PRIMARY KEY (user_id, guild_id))''')

    # Таблица фракций
    c.execute('''CREATE TABLE IF NOT EXISTS factions
                 (faction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  guild_id INTEGER, name TEXT, balance REAL,
                  leader_id INTEGER, color TEXT, created_at TEXT,
                  description TEXT DEFAULT '', role_id INTEGER DEFAULT NULL,
                  is_role_based INTEGER DEFAULT 0)''')

    # Таблица членов фракций
    c.execute('''CREATE TABLE IF NOT EXISTS faction_members
                 (user_id INTEGER, guild_id INTEGER, faction_id INTEGER,
                  role TEXT, joined_at TEXT)''')

    # Таблица настроек интерфейса
    c.execute('''CREATE TABLE IF NOT EXISTS ui_settings
                 (guild_id INTEGER PRIMARY KEY, 
                  embed_color TEXT, footer_text TEXT,
                  admin_channel_id INTEGER)''')

    # Проверяем наличие столбцов
    c.execute("PRAGMA table_info(factions)")
    columns = [column[1] for column in c.fetchall()]

    if 'role_id' not in columns:
        c.execute('ALTER TABLE factions ADD COLUMN role_id INTEGER DEFAULT NULL')
    if 'is_role_based' not in columns:
        c.execute('ALTER TABLE factions ADD COLUMN is_role_based INTEGER DEFAULT 0')

    # Таблица ролей с доступом к админ-панели
    c.execute('''CREATE TABLE IF NOT EXISTS admin_roles
                 (guild_id INTEGER, role_id INTEGER,
                  added_by INTEGER, added_at TEXT,
                  PRIMARY KEY (guild_id, role_id))''')

    # Таблица пользователей с доступом к админ-панели
    c.execute('''CREATE TABLE IF NOT EXISTS admin_users
                 (guild_id INTEGER, user_id INTEGER,
                  added_by INTEGER, added_at TEXT,
                  PRIMARY KEY (guild_id, user_id))''')

    # Таблица зарплат по ролям
    c.execute('''CREATE TABLE IF NOT EXISTS role_salaries
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  guild_id INTEGER, role_id INTEGER,
                  salary_amount REAL, added_by INTEGER,
                  added_at TEXT, last_paid TEXT,
                  UNIQUE(guild_id, role_id))''')

    # Таблица истории выплат
    c.execute('''CREATE TABLE IF NOT EXISTS salary_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  guild_id INTEGER, user_id INTEGER,
                  role_id INTEGER, amount REAL,
                  paid_at TEXT, paid_by TEXT DEFAULT 'system')''')

    # Таблица ожидающих переводов
    c.execute('''CREATE TABLE IF NOT EXISTS pending_transfers
                 (transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  guild_id INTEGER, from_user_id INTEGER, to_user_id INTEGER,
                  to_faction_id INTEGER, amount REAL, type TEXT,
                  created_at TEXT, expires_at TEXT)''')

    conn.commit()
    conn.close()


# Функции для работы с ролями админов
def get_admin_roles(guild_id: int) -> List[int]:
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('SELECT role_id FROM admin_roles WHERE guild_id = ?', (guild_id,))
    roles = [row[0] for row in c.fetchall()]
    conn.close()
    return roles


def get_admin_users(guild_id: int) -> List[int]:
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM admin_users WHERE guild_id = ?', (guild_id,))
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users


def add_admin_role(guild_id: int, role_id: int, added_by: int) -> bool:
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO admin_roles (guild_id, role_id, added_by, added_at) VALUES (?, ?, ?, ?)',
                  (guild_id, role_id, added_by, datetime.now().isoformat()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_admin_role(guild_id: int, role_id: int):
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('DELETE FROM admin_roles WHERE guild_id = ? AND role_id = ?', (guild_id, role_id))
    conn.commit()
    conn.close()


def add_admin_user(guild_id: int, user_id: int, added_by: int) -> bool:
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO admin_users (guild_id, user_id, added_by, added_at) VALUES (?, ?, ?, ?)',
                  (guild_id, user_id, added_by, datetime.now().isoformat()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_admin_user(guild_id: int, user_id: int):
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('DELETE FROM admin_users WHERE guild_id = ? AND user_id = ?', (guild_id, user_id))
    conn.commit()
    conn.close()


# Получение настроек интерфейса
def get_ui_settings(guild_id: int):
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()

    # Проверяем структуру таблицы
    c.execute("PRAGMA table_info(ui_settings)")
    columns = [column[1] for column in c.fetchall()]

    # Определяем какие столбцы запрашивать
    select_columns = []
    if 'embed_color' in columns:
        select_columns.append('embed_color')
    if 'footer_text' in columns:
        select_columns.append('footer_text')
    if 'admin_channel_id' in columns:
        select_columns.append('admin_channel_id')

    if not select_columns:
        conn.close()
        return {
            'color_hex': "3498db",
            'footer': f"© {datetime.now().year} Экономика сервера",
            'admin_channel': None
        }

    select_query = f"SELECT {', '.join(select_columns)} FROM ui_settings WHERE guild_id = ?"
    c.execute(select_query, (guild_id,))
    result = c.fetchone()
    conn.close()

    if result:
        result_dict = {}
        for i, col in enumerate(select_columns):
            result_dict[col] = result[i]

        return {
            'color_hex': result_dict.get('embed_color') or "3498db",
            'footer': result_dict.get('footer_text') or f"© {datetime.now().year} Экономика сервера",
            'admin_channel': result_dict.get('admin_channel_id')
        }

    return {
        'color_hex': "3498db",
        'footer': f"© {datetime.now().year} Экономика сервера",
        'admin_channel': None
    }


def save_ui_settings(guild_id: int, embed_color: Optional[str] = None, footer_text: Optional[str] = None):
    """Сохранение настроек интерфейса"""
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()

    c.execute('SELECT * FROM ui_settings WHERE guild_id = ?', (guild_id,))
    if c.fetchone():
        if embed_color:
            c.execute('UPDATE ui_settings SET embed_color = ? WHERE guild_id = ?', (embed_color, guild_id))
        if footer_text:
            c.execute('UPDATE ui_settings SET footer_text = ? WHERE guild_id = ?', (footer_text, guild_id))
    else:
        c.execute('INSERT INTO ui_settings (guild_id, embed_color, footer_text) VALUES (?, ?, ?)',
                  (guild_id, embed_color or "3498db", footer_text or ""))

    conn.commit()
    conn.close()


# Функции для работы с балансом
def get_balance(user_id: int, guild_id: int, default_balance: float = 1000.0) -> float:
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
    result = c.fetchone()

    if not result:
        c.execute('INSERT INTO users (user_id, guild_id, balance) VALUES (?, ?, ?)',
                  (user_id, guild_id, default_balance))
        conn.commit()
        conn.close()
        return default_balance

    conn.close()
    return result[0]


def update_balance(user_id: int, guild_id: int, amount: float, default_balance: float = 1000.0) -> float:
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    current = get_balance(user_id, guild_id, default_balance)
    new_balance = current + amount

    c.execute('UPDATE users SET balance = ? WHERE user_id = ? AND guild_id = ?',
              (new_balance, user_id, guild_id))
    conn.commit()
    conn.close()
    return new_balance


def get_all_balances(guild_id: int) -> List[tuple]:
    """Получить все балансы на сервере"""
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('SELECT user_id, balance FROM users WHERE guild_id = ?', (guild_id,))
    all_balances = c.fetchall()
    conn.close()
    return all_balances


def get_total_balance(guild_id: int, exclude_role_id: Optional[int] = None) -> Tuple[float, int, int]:
    """Получить общий баланс, количество игроков и количество игроков с исключенной ролью"""
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()

    c.execute('SELECT SUM(balance), COUNT(*) FROM users WHERE guild_id = ?', (guild_id,))
    result = c.fetchone()

    total_balance = result[0] if result and result[0] is not None else 0.0
    total_users = result[1] if result else 0

    conn.close()
    return total_balance, total_users, 0


# Функции для работы с фракциями
def get_faction_balance(faction_id: int) -> float:
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM factions WHERE faction_id = ?', (faction_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0


def update_faction_balance(faction_id: int, amount: float):
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('UPDATE factions SET balance = balance + ? WHERE faction_id = ?', (amount, faction_id))
    conn.commit()
    conn.close()


def get_user_faction(user_id: int, guild_id: int):
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('''SELECT f.* FROM factions f
                 JOIN faction_members fm ON f.faction_id = fm.faction_id
                 WHERE fm.user_id = ? AND f.guild_id = ?''',
              (user_id, guild_id))
    result = c.fetchone()
    conn.close()
    return result


def get_faction_by_name(guild_id: int, faction_name: str):
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM factions 
                 WHERE guild_id = ? AND LOWER(name) LIKE LOWER(?)''',
              (guild_id, f"%{faction_name}%"))
    result = c.fetchone()
    conn.close()
    return result


def create_faction(guild_id: int, name: str, leader_id: int, description: str = "",
                   color: str = "3498db", role_id: Optional[int] = None) -> int:
    """Создание новой фракции"""
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()

    # Проверяем, не существует ли уже фракция с таким именем
    c.execute('SELECT faction_id FROM factions WHERE guild_id = ? AND LOWER(name) = LOWER(?)',
              (guild_id, name))
    if c.fetchone():
        conn.close()
        raise ValueError("Фракция с таким названием уже существует")

    is_role_based = 1 if role_id is not None else 0

    c.execute('''INSERT INTO factions (guild_id, name, balance, leader_id, color, 
                                       description, role_id, is_role_based)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (guild_id, name, 0.0, leader_id, color,
               description, role_id, is_role_based))
    faction_id = c.lastrowid

    # Если фракция не привязана к роли, добавляем лидера в члены
    if role_id is None:
        c.execute('''INSERT INTO faction_members (user_id, guild_id, faction_id, role, joined_at)
                     VALUES (?, ?, ?, ?, ?)''',
                  (leader_id, guild_id, faction_id, 'Лидер', datetime.now().isoformat()))

    conn.commit()
    conn.close()
    return faction_id


def get_faction_members(faction_id: int):
    """Получить всех членов фракции"""
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('''SELECT fm.user_id, fm.role, fm.joined_at, u.balance 
                 FROM faction_members fm
                 LEFT JOIN users u ON fm.user_id = u.user_id AND fm.guild_id = u.guild_id
                 WHERE fm.faction_id = ?''', (faction_id,))
    members = c.fetchall()
    conn.close()
    return members


def get_all_factions(guild_id: int):
    """Получить все фракции на сервере"""
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('''SELECT f.*, COUNT(fm.user_id) as member_count 
                 FROM factions f
                 LEFT JOIN faction_members fm ON f.faction_id = fm.faction_id
                 WHERE f.guild_id = ?
                 GROUP BY f.faction_id
                 ORDER BY f.name''', (guild_id,))
    factions = c.fetchall()
    conn.close()
    return factions


def get_role_based_factions(guild_id: int):
    """Получить фракции, привязанные к ролям"""
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM factions 
                 WHERE guild_id = ? AND is_role_based = 1
                 ORDER BY name''', (guild_id,))
    factions = c.fetchall()
    conn.close()
    return factions


# Функции для зарплат
def add_role_salary(guild_id: int, role_id: int, salary_amount: float, added_by: int) -> bool:
    """Добавить или обновить зарплату для роли"""
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    try:
        c.execute('''INSERT OR REPLACE INTO role_salaries 
                     (guild_id, role_id, salary_amount, added_by, added_at)
                     VALUES (?, ?, ?, ?, ?)''',
                  (guild_id, role_id, salary_amount, added_by, datetime.now().isoformat()))
        conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка при добавлении зарплаты: {e}")
        return False
    finally:
        conn.close()


def remove_role_salary(guild_id: int, role_id: int) -> bool:
    """Удалить зарплату для роли"""
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    try:
        c.execute('DELETE FROM role_salaries WHERE guild_id = ? AND role_id = ?', (guild_id, role_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка при удалении зарплаты: {e}")
        return False
    finally:
        conn.close()


def get_role_salary(guild_id: int, role_id: int) -> Optional[float]:
    """Получить зарплату для роли"""
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('SELECT salary_amount FROM role_salaries WHERE guild_id = ? AND role_id = ?',
              (guild_id, role_id))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def get_all_role_salaries(guild_id: int) -> List[tuple]:
    """Получить все зарплаты на сервере"""
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('''SELECT role_id, salary_amount, added_by, added_at, last_paid 
                 FROM role_salaries WHERE guild_id = ? ORDER BY salary_amount DESC''',
              (guild_id,))
    salaries = c.fetchall()
    conn.close()
    return salaries


def record_salary_payment(guild_id: int, user_id: int, role_id: int, amount: float, paid_by: str = "system"):
    """Записать выплату зарплаты в историю"""
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('''INSERT INTO salary_history (guild_id, user_id, role_id, amount, paid_at, paid_by)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (guild_id, user_id, role_id, amount, datetime.now().isoformat(), paid_by))

    # Обновляем время последней выплаты для роли
    c.execute('UPDATE role_salaries SET last_paid = ? WHERE guild_id = ? AND role_id = ?',
              (datetime.now().isoformat(), guild_id, role_id))

    conn.commit()
    conn.close()


def get_salary_history(guild_id: int, limit: int = 20) -> List[tuple]:
    """Получить историю выплат зарплат"""
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('''SELECT sh.*, rs.salary_amount 
                 FROM salary_history sh
                 LEFT JOIN role_salaries rs ON sh.role_id = rs.role_id AND sh.guild_id = rs.guild_id
                 WHERE sh.guild_id = ?
                 ORDER BY sh.paid_at DESC LIMIT ?''', (guild_id, limit))
    history = c.fetchall()
    conn.close()
    return history


# Функции для ожидающих переводов
def create_pending_transfer(guild_id: int, from_user_id: int, to_user_id: Optional[int],
                            to_faction_id: Optional[int], amount: float, transfer_type: str) -> int:
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()

    expires_at = datetime.now().timestamp() + 300

    c.execute('''INSERT INTO pending_transfers 
                 (guild_id, from_user_id, to_user_id, to_faction_id, amount, type, created_at, expires_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (guild_id, from_user_id, to_user_id, to_faction_id, amount, transfer_type,
               datetime.now().isoformat(), expires_at))

    transfer_id = c.lastrowid
    conn.commit()
    conn.close()
    return transfer_id


def get_pending_transfer(transfer_id: int):
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('SELECT * FROM pending_transfers WHERE transfer_id = ?', (transfer_id,))
    result = c.fetchone()
    conn.close()
    return result


def delete_pending_transfer(transfer_id: int):
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('DELETE FROM pending_transfers WHERE transfer_id = ?', (transfer_id,))
    conn.commit()
    conn.close()


def cleanup_expired_transfers() -> int:
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    now = datetime.now().timestamp()
    c.execute('DELETE FROM pending_transfers WHERE expires_at < ?', (now,))
    deleted = c.rowcount
    conn.commit()
    conn.close()
    return deleted


# Вспомогательные функции
def hex_to_color(hex_color: str) -> discord.Color:
    """Преобразование HEX цвета в discord.Color"""
    try:
        if hex_color and all(c in "0123456789ABCDEFabcdef" for c in hex_color):
            return discord.Color(int(hex_color, 16))
        else:
            return discord.Color.blue()
    except:
        return discord.Color.blue()


def get_formatted_settings(guild_id: int):
    """Получение форматированных настроек интерфейса"""
    settings = get_ui_settings(guild_id)
    return {
        'color': hex_to_color(settings['color_hex']),
        'footer': settings['footer'],
        'admin_channel': settings['admin_channel']
    }