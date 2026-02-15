# 🚀 Развертывание Plane на Ubuntu Server

## Подготовка на Windows (текущая машина)

### 1. Проверка перед коммитом

```bash
# Проверьте, что .env файлы не будут закоммичены
git status

# Убедитесь, что .env в .gitignore
cat .gitignore | grep ".env"
```

### 2. Коммит и пуш изменений

```bash
# Добавить все изменения
git add .

# Создать коммит
git commit -m "feat: добавлена генерация отчетов через LLM (DeepSeek/OpenAI)"

# Запушить в GitHub
git push origin main
```

---

## Развертывание на Ubuntu Server

### 1. Установка необходимых пакетов

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Установка Docker Compose
sudo apt install docker-compose-plugin -y

# Установка Git
sudo apt install git -y

# Установка Node.js и pnpm (для фронтенда)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
npm install -g pnpm
```

### 2. Клонирование проекта

```bash
# Клонировать репозиторий
cd ~
git clone https://github.com/ваш-username/plane.git
cd plane
```

### 3. Настройка переменных окружения

#### Корневой .env файл

```bash
nano .env
```

Вставьте (замените значения на свои):

```env
# Database Settings
POSTGRES_USER="plane"
POSTGRES_PASSWORD="ваш-безопасный-пароль"
POSTGRES_DB="plane"
PGDATA="/var/lib/postgresql/data"

# Redis Settings
REDIS_HOST="plane-redis"
REDIS_PORT="6379"

# RabbitMQ Settings
RABBITMQ_HOST="plane-mq"
RABBITMQ_PORT="5672"
RABBITMQ_USER="plane"
RABBITMQ_PASSWORD="ваш-безопасный-пароль"
RABBITMQ_VHOST="plane"

LISTEN_HTTP_PORT=80
LISTEN_HTTPS_PORT=443

# AWS Settings (MinIO)
AWS_REGION=""
AWS_ACCESS_KEY_ID="access-key"
AWS_SECRET_ACCESS_KEY="secret-key"
AWS_S3_ENDPOINT_URL="http://plane-minio:9000"
AWS_S3_BUCKET_NAME="uploads"
FILE_SIZE_LIMIT=5242880

# LLM для отчётов
SKIP_ENV_VAR=0
LLM_API_KEY=ваш-deepseek-или-openai-ключ
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat

# Settings related to Docker
DOCKERIZED=1
USE_MINIO=1

# Force HTTPS for handling SSL Termination
MINIO_ENDPOINT_SSL=0

# API key rate limit
API_KEY_RATE_LIMIT="60/minute"
```

#### API .env файл

```bash
nano apps/api/.env
```

Вставьте:

```env
# Backend
DEBUG=0
CORS_ALLOWED_ORIGINS="http://localhost:3000,http://localhost:3001,http://ваш-домен.com"
PASSWORD_STRENGTH_MIN_SCORE=0

# Database Settings
POSTGRES_USER="plane"
POSTGRES_PASSWORD="ваш-безопасный-пароль"
POSTGRES_HOST="plane-db"
POSTGRES_DB="plane"
POSTGRES_PORT=5432
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}

# Redis Settings
REDIS_HOST="plane-redis"
REDIS_PORT="6379"
REDIS_URL="redis://${REDIS_HOST}:6379/"

# RabbitMQ Settings
RABBITMQ_HOST="plane-mq"
RABBITMQ_PORT="5672"
RABBITMQ_USER="plane"
RABBITMQ_PASSWORD="ваш-безопасный-пароль"
RABBITMQ_VHOST="plane"

# AWS Settings
AWS_REGION=""
AWS_ACCESS_KEY_ID="access-key"
AWS_SECRET_ACCESS_KEY="secret-key"
AWS_S3_ENDPOINT_URL="http://plane-minio:9000"
AWS_S3_BUCKET_NAME="uploads"
FILE_SIZE_LIMIT=5242880
SIGNED_URL_EXPIRATION=3600

DOCKERIZED=1
USE_MINIO=1

# URLs
WEB_URL="http://ваш-домен.com"
ADMIN_BASE_URL="http://ваш-домен.com:3001"
ADMIN_BASE_PATH="/god-mode"
SPACE_BASE_URL="http://ваш-домен.com:3002"
SPACE_BASE_PATH="/spaces"
APP_BASE_URL="http://ваш-домен.com"
APP_BASE_PATH=""
LIVE_BASE_URL="http://ваш-домен.com:3100"
LIVE_BASE_PATH="/live"
LIVE_SERVER_SECRET_KEY="secret-key"

# Hard delete files after days
HARD_DELETE_AFTER_DAYS=60
MINIO_ENDPOINT_SSL=0
API_KEY_RATE_LIMIT="60/minute"
SECRET_KEY="сгенерируйте-случайную-строку"

# LLM Settings
SKIP_ENV_VAR=0
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
LLM_API_KEY=ваш-deepseek-или-openai-ключ
```

### 4. Запуск проекта

#### Вариант A: Локальная разработка (с hot-reload)

```bash
# Запустить только инфраструктуру (БД, Redis, MinIO, RabbitMQ)
docker compose -f docker-compose-local.yml up -d plane-db plane-redis plane-minio plane-mq

# Запустить API в Docker
docker compose -f docker-compose-local.yml up -d api worker beat-worker

# Запустить фронтенд локально (нужен Node.js)
pnpm install
pnpm --filter=web dev
```

#### Вариант B: Production (все в Docker)

```bash
# Собрать образы
docker compose build

# Запустить все сервисы
docker compose up -d

# Проверить статус
docker compose ps
```

### 5. Проверка работы

```bash
# Проверить логи API
docker logs plane-api-1 --tail 50

# Проверить логи worker
docker logs plane-worker-1 --tail 50

# Проверить доступность
curl http://localhost:8000/api/instances/
```

### 6. Доступ к приложению

- **Web UI**: http://ваш-сервер:3000
- **Admin**: http://ваш-сервер:3001
- **API**: http://ваш-сервер:8000
- **MinIO Console**: http://ваш-сервер:9090

---

## Настройка Nginx (опционально, для production)

### 1. Установка Nginx

```bash
sudo apt install nginx -y
```

### 2. Конфигурация

```bash
sudo nano /etc/nginx/sites-available/plane
```

Вставьте:

```nginx
server {
    listen 80;
    server_name ваш-домен.com;

    client_max_body_size 10M;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Auth
    location /auth/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. Активация

```bash
sudo ln -s /etc/nginx/sites-available/plane /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## Обновление проекта

```bash
# На сервере
cd ~/plane
git pull origin main

# Пересобрать и перезапустить
docker compose down
docker compose build
docker compose up -d
```

---

## Резервное копирование

### Backup базы данных

```bash
# Создать backup
docker exec plane-plane-db-1 pg_dump -U plane plane > backup_$(date +%Y%m%d).sql

# Восстановить backup
cat backup_20260214.sql | docker exec -i plane-plane-db-1 psql -U plane plane
```

### Backup файлов (MinIO)

```bash
# Скопировать volume
docker run --rm -v plane_uploads:/data -v $(pwd):/backup alpine tar czf /backup/uploads_backup.tar.gz /data
```

---

## Troubleshooting

### Проблема: API не запускается

```bash
# Проверить логи
docker logs plane-api-1 --tail 100

# Проверить переменные окружения
docker exec plane-api-1 printenv | grep LLM
```

### Проблема: Нет подключения к БД

```bash
# Проверить, что БД запущена
docker ps | grep plane-db

# Проверить логи БД
docker logs plane-plane-db-1 --tail 50
```

### Проблема: Порты заняты

```bash
# Проверить занятые порты
sudo netstat -tulpn | grep LISTEN

# Изменить порты в docker-compose-local.yml
```

---

## Безопасность

1. **Измените все пароли** в .env файлах
2. **Сгенерируйте новый SECRET_KEY**:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
3. **Настройте firewall**:
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```
4. **Используйте HTTPS** (Let's Encrypt):
   ```bash
   sudo apt install certbot python3-certbot-nginx -y
   sudo certbot --nginx -d ваш-домен.com
   ```

---

## Мониторинг

```bash
# Просмотр логов в реальном времени
docker compose logs -f api

# Использование ресурсов
docker stats

# Проверка здоровья контейнеров
docker compose ps
```
