# ⚡ Быстрый старт на Ubuntu Server

## 1️⃣ На Windows (подготовка)

```bash
# Сохраните копии .env файлов (они не попадут в Git!)
# Скопируйте содержимое .env и apps/api/.env в безопасное место

# Закоммитьте и запушьте изменения
git add .
git commit -m "feat: добавлена генерация отчетов через LLM"
git push origin main
```

## 2️⃣ На Ubuntu Server (развертывание)

### Автоматическая установка (рекомендуется)

```bash
# Клонируйте проект
git clone https://github.com/ваш-username/plane.git
cd plane

# Создайте .env файлы (скопируйте из сохраненных копий)
nano .env
nano apps/api/.env

# Запустите автоматическую установку
chmod +x deploy-ubuntu.sh
./deploy-ubuntu.sh
```

### Ручная установка

```bash
# 1. Установите Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# 2. Установите Docker Compose
sudo apt install docker-compose-plugin -y

# 3. Клонируйте проект
git clone https://github.com/ваш-username/plane.git
cd plane

# 4. Создайте .env файлы
nano .env
nano apps/api/.env

# 5. Запустите проект
docker compose -f docker-compose-local.yml up -d
```

## 3️⃣ Проверка

```bash
# Проверьте статус
docker compose ps

# Проверьте API
curl http://localhost:8000/api/instances/

# Откройте в браузере
http://ваш-сервер:3000
```

## 🔧 Важные настройки в .env

### Корневой .env

```env
POSTGRES_PASSWORD="измените-на-безопасный"
RABBITMQ_PASSWORD="измените-на-безопасный"
LLM_API_KEY=ваш-deepseek-или-openai-ключ
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
SKIP_ENV_VAR=0
```

### apps/api/.env

```env
SECRET_KEY="сгенерируйте-новый"
CORS_ALLOWED_ORIGINS="http://ваш-сервер:3000,http://ваш-домен.com"
WEB_URL="http://ваш-домен.com"
APP_BASE_URL="http://ваш-домен.com"
LLM_API_KEY=ваш-deepseek-или-openai-ключ
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
SKIP_ENV_VAR=0
```

## 🔐 Генерация SECRET_KEY

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 📊 Получение LLM API ключа

### DeepSeek (дешевле)

1. Зарегистрируйтесь: https://platform.deepseek.com/
2. Пополните баланс ($5-10)
3. Создайте API ключ: https://platform.deepseek.com/api_keys

### OpenAI

1. Зарегистрируйтесь: https://platform.openai.com/
2. Пополните баланс
3. Создайте API ключ: https://platform.openai.com/api-keys

## 🚀 Полезные команды

```bash
# Просмотр логов
docker compose logs -f api

# Перезапуск
docker compose restart api

# Остановка
docker compose down

# Обновление
git pull origin main
docker compose down
docker compose build
docker compose up -d

# Backup БД
docker exec plane-plane-db-1 pg_dump -U plane plane > backup_$(date +%Y%m%d).sql
```

## 🆘 Если что-то не работает

```bash
# 1. Проверьте логи
docker compose logs -f api

# 2. Проверьте переменные окружения
docker exec plane-api-1 printenv | grep LLM

# 3. Перезапустите контейнеры
docker compose down
docker compose up -d

# 4. Проверьте порты
sudo netstat -tulpn | grep LISTEN
```

## 📚 Подробная документация

- `DEPLOYMENT.md` - полная инструкция по развертыванию
- `MIGRATION_CHECKLIST.md` - чеклист для переноса
- `LLM_SETUP_RU.md` - настройка LLM для отчетов

---

**Готово!** Ваш Plane работает на Ubuntu Server 🎉
