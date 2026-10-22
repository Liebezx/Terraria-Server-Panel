# 🌲 Terraria & TShock Server Manager
> **Современная кибер-панель управления сервером Terraria 1.4.5.8 & TShock 6.2.1**  
> *Разработано: **Liebe** (Discord: `liebe213`)*

[![Terraria Version](https://img.shields.io/badge/Terraria-1.4.5.8-green.svg?logo=terraria)](https://terraria.org/)
[![TShock Version](https://img.shields.io/badge/TShock-6.2.1-blue.svg)](https://github.com/Pryaxis/TShock)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python)](https://python.org)
[![UI](https://img.shields.io/badge/UI-Cyber%20Emerald-00ff9d.svg)](#галерея-всех-вкладок)
[![Architecture](https://img.shields.io/badge/Architecture-x64%20Windows-lightgrey.svg)]()

---

## 📸 Галерея всех вкладок панели

### 1. 🖥️ Сервер — Главная панель и быстрые действия
> Состояние сервера, время работы, туннель Playit.gg для друзей без белого IP и переключение профилей.
![01_server_overview](Panel/screenshots/01_server_overview.png)

---

### 2. 👥 Игроки — Список онлайн и управление
> Мониторинг подключённых игроков, назначение ролей, быстрый кик и телепортация.
![02_players_management](Panel/screenshots/02_players_management.png)

---

### 3. 💻 Консоль — Живой терминал TShock
> Полнофункциональный журнал сервера в реальном времени с цветовой разметкой, отправкой команд TShock и сообщений в чат.
![03_live_console](Panel/screenshots/03_live_console.png)

---

### 4. 🌍 Миры — Менеджер и расширенный генератор
> Выбор активного мира, смена сложности (Классика / Эксперт / Мастер / Путешествие), генерация секретных сидов (*Zenith / Get Fixed Boi, Drunk World, For The Worthy, Don't Dig Up*) и автоматические бэкапы.
![04_worlds_and_generator](Panel/screenshots/04_worlds_and_generator.png)

---

### 5. ⚔️ Геймплей и Защита — Безопасность сервера
> Тонкая настройка защиты от гриферов, блокировка взрывов, сохранение инвентаря на сервере (SSC), белые списки и правила.
![05_gameplay_and_security](Panel/screenshots/05_gameplay_and_security.png)

---

### 6. ⚙️ Настройки — Конфигурация портов и сети
> Управление игровым портом (7777), REST API портом (7878), паролями, слотами и путями к файлам.
![06_server_settings](Panel/screenshots/06_server_settings.png)

---

### 7. 📊 Нагрузка — Мониторинг ресурсов
> Высокоточный отслеживатель потребления процессора и оперативной памяти выделенного процесса Terraria/TShock в реальном времени.
![07_performance_metrics](Panel/screenshots/07_performance_metrics.png)

---

### 8. 🛡️ Админка — Управление TShock и правами групп
> Получение одноразового `/setup` кода владельца, редактирование ролей (`owner`, `admin`, `superadmin`, `default`), создание персональных групп и точечная настройка сотен прав доступа TShock.
![08_admin_and_permissions](Panel/screenshots/08_admin_and_permissions.png)

---

## ⚡ Особенности и возможности

- **🎮 Абсолютная автономность**: Для работы не требуется вручную устанавливать Python, базы данных или .NET Runtime — всё упаковано в портативный вид.
- **🌐 Встроенная Web-панель**: Модуль в папке `Panel/Browser` позволяет управлять сервером удалённо с телефона или планшета через браузер.
- **🔄 Серверные профили**: Возможность переключаться между разными мирами и конфигурациями в один клик.
- **🚀 Интеграция с Playit.gg**: Подключение друзей через безопасный туннель без необходимости открывать порты на роутере.
- **🖱️ Удобная навигация**: Поддержка аппаратных боковых кнопок мыши `Mouse4` (Назад) и `Mouse5` (Вперёд).
- **✨ Кибер-дизайн**: Анимированные неоновые лучи, интерактивный Spotlight карточек и стеклянный эффект размытия (Glassmorphism).

---

## 🚀 Быстрый старт

1. Скачайте последний релиз из раздела [Releases](https://github.com/Liebezx/Terraria-Server-Panel/releases).
2. Распакуйте архив в любую папку.
3. Запустите **`Запустить Панель.exe`** (или `Запустить Панель.bat`).
4. Выберите нужный мир во вкладке **Миры** и нажмите **«Запустить сервер»**!

---

## 🛠️ Запуск из исходного кода (для разработчиков)

```bash
# Установка необходимых зависимостей
pip install pywebview pillow requests psutil

# Запуск панели управления
python "Panel/TerrariaPanel.pyw"
```

---

## 👤 Авторство
- **Разработчик:** Liebe
- **Discord:** `liebe213`
