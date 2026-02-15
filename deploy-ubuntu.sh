#!/bin/bash
# Скрипт быстрого развертывания Plane на Ubuntu Server

set -e

echo "🚀 Развертывание Plane на Ubuntu Server"
echo "========================================"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Проверка, что скрипт запущен на Ubuntu
if [ ! -f /etc/lsb-release ]; then
    error "Этот скрипт предназначен для Ubuntu"
fi

info "Проверка установленных пакетов..."

# Проверка Docker
if ! command -v docker &> /dev/null; then
    warn "Docker не установлен. Устанавливаю..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    info "Docker установлен. Перезайдите в систему для применения изменений."
fi

# Проверка Docker Compose
if ! docker compose version &> /dev/null; then
    warn "Docker Compose не установлен. Устанавливаю..."
    sudo apt update
    sudo apt install -y docker-compose-plugin
fi

# Проверка Git
if ! command -v git &> /dev/null; then
    warn "Git не установлен. Устанавливаю..."
    sudo apt update
    sudo apt install -y git
fi

info "Все необходимые пакеты установлены ✓"

# Проверка наличия .env файлов
if [ ! -f .env ]; then
    error ".env файл не найден! Создайте его из .env.example"
fi

if [ ! -f apps/api/.env ]; then
    error "apps/api/.env файл не найден! Создайте его из apps/api/.env.example"
fi

info "Конфигурационные файлы найдены ✓"

# Выбор режима запуска
echo ""
echo "Выберите режим запуска:"
echo "1) Development (локальная разработка с hot-reload)"
echo "2) Production (все в Docker)"
read -p "Введите номер (1 или 2): " mode

if [ "$mode" == "1" ]; then
    info "Запуск в режиме Development..."
    
    # Проверка Node.js
    if ! command -v node &> /dev/null; then
        warn "Node.js не установлен. Устанавливаю..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt install -y nodejs
    fi
    
    # Проверка pnpm
    if ! command -v pnpm &> /dev/null; then
        warn "pnpm не установлен. Устанавливаю..."
        npm install -g pnpm
    fi
    
    info "Установка зависимостей..."
    pnpm install
    
    info "Запуск инфраструктуры (БД, Redis, MinIO, RabbitMQ)..."
    docker compose -f docker-compose-local.yml up -d plane-db plane-redis plane-minio plane-mq
    
    info "Ожидание запуска БД..."
    sleep 10
    
    info "Запуск API, Worker, Beat Worker..."
    docker compose -f docker-compose-local.yml up -d api worker beat-worker migrator
    
    info "Ожидание миграций..."
    sleep 5
    
    echo ""
    info "✓ Инфраструктура запущена!"
    echo ""
    echo "Для запуска фронтенда выполните:"
    echo "  pnpm --filter=web dev"
    echo ""
    echo "Доступ:"
    echo "  - API: http://localhost:8000"
    echo "  - Web: http://localhost:3000 (после запуска pnpm dev)"
    echo "  - MinIO Console: http://localhost:9090"
    
elif [ "$mode" == "2" ]; then
    info "Запуск в режиме Production..."
    
    info "Сборка Docker образов..."
    docker compose build
    
    info "Запуск всех сервисов..."
    docker compose up -d
    
    info "Ожидание запуска сервисов..."
    sleep 15
    
    echo ""
    info "✓ Все сервисы запущены!"
    echo ""
    echo "Доступ:"
    echo "  - Web: http://localhost:3000"
    echo "  - Admin: http://localhost:3001"
    echo "  - API: http://localhost:8000"
    echo "  - MinIO Console: http://localhost:9090"
    
else
    error "Неверный выбор. Введите 1 или 2."
fi

echo ""
info "Проверка статуса контейнеров:"
docker compose ps

echo ""
info "Для просмотра логов используйте:"
echo "  docker compose logs -f api"
echo "  docker compose logs -f worker"

echo ""
info "Развертывание завершено! 🎉"
