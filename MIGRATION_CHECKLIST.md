# ✅ Чеклист переноса Plane на Ubuntu Server

## На Windows (перед переносом)

- [ ] Убедитесь, что все изменения сохранены
- [ ] Проверьте, что `.env` файлы в `.gitignore`
- [ ] Сохраните копии `.env` файлов отдельно (они не попадут в Git)
- [ ] Проверьте статус Git: `git status`
- [ ] Закоммитьте изменения: `git add . && git commit -m "feat: добавлена генерация отчетов"`
- [ ] Запушьте в GitHub: `git push origin main`
- [ ] Убедитесь, что пуш прошел успешно

## На Ubuntu Server (развертывание)

### Подготовка системы

- [ ] Обновите систему: `sudo apt update && sudo apt upgrade -y`
- [ ] Установите Docker: `curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh`
- [ ] Добавьте пользователя в группу docker: `sudo usermod -aG docker $USER && newgrp docker`
- [ ] Установите Docker Compose: `sudo apt install docker-compose-plugin -y`
- [ ] Установите Git: `sudo apt install git -y`
- [ ] Проверьте версии: `docker --version && docker compose version && git --version`

### Клонирование проекта

- [ ] Клонируйте репозиторий: `git clone https://github.com/ваш-username/plane.git`
- [ ] Перейдите в папку: `cd plane`
- [ ] Проверьте ветку: `git branch`

### Настройка конфигурации

- [ ] Создайте корневой `.env` файл: `nano .env`
- [ ] Скопируйте содержимое из сохраненной копии
- [ ] Измените пароли на более безопасные
- [ ] Создайте `apps/api/.env`: `nano apps/api/.env`
- [ ] Скопируйте содержимое из сохраненной копии
- [ ] Обновите `CORS_ALLOWED_ORIGINS` на IP/домен сервера
- [ ] Обновите `WEB_URL`, `APP_BASE_URL` на IP/домен сервера
- [ ] Сгенерируйте новый `SECRET_KEY`: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] Добавьте API ключ LLM (DeepSeek или OpenAI)

### Запуск проекта

#### Вариант A: Development (рекомендуется для тестирования)

- [ ] Сделайте скрипт исполняемым: `chmod +x deploy-ubuntu.sh`
- [ ] Запустите скрипт: `./deploy-ubuntu.sh`
- [ ] Выберите режим "1" (Development)
- [ ] Дождитесь завершения установки
- [ ] Проверьте статус: `docker compose -f docker-compose-local.yml ps`
- [ ] Проверьте логи API: `docker logs plane-api-1 --tail 50`

#### Вариант B: Production (для продакшена)

- [ ] Запустите скрипт: `./deploy-ubuntu.sh`
- [ ] Выберите режим "2" (Production)
- [ ] Дождитесь сборки образов (может занять 10-15 минут)
- [ ] Проверьте статус: `docker compose ps`
- [ ] Проверьте логи: `docker compose logs -f api`

### Проверка работоспособности

- [ ] Проверьте API: `curl http://localhost:8000/api/instances/`
- [ ] Откройте Web UI: `http://ваш-сервер:3000`
- [ ] Войдите в систему
- [ ] Проверьте создание workspace
- [ ] Проверьте создание проекта
- [ ] Проверьте создание задачи
- [ ] Проверьте генерацию отчета (если настроен LLM)

### Настройка Nginx (опционально)

- [ ] Установите Nginx: `sudo apt install nginx -y`
- [ ] Создайте конфиг: `sudo nano /etc/nginx/sites-available/plane`
- [ ] Скопируйте конфигурацию из `DEPLOYMENT.md`
- [ ] Активируйте сайт: `sudo ln -s /etc/nginx/sites-available/plane /etc/nginx/sites-enabled/`
- [ ] Проверьте конфиг: `sudo nginx -t`
- [ ] Перезапустите Nginx: `sudo systemctl restart nginx`
- [ ] Проверьте доступ через Nginx: `http://ваш-домен.com`

### Настройка SSL (опционально, для HTTPS)

- [ ] Установите Certbot: `sudo apt install certbot python3-certbot-nginx -y`
- [ ] Получите сертификат: `sudo certbot --nginx -d ваш-домен.com`
- [ ] Проверьте автообновление: `sudo certbot renew --dry-run`
- [ ] Проверьте HTTPS: `https://ваш-домен.com`

### Настройка Firewall

- [ ] Разрешите SSH: `sudo ufw allow 22/tcp`
- [ ] Разрешите HTTP: `sudo ufw allow 80/tcp`
- [ ] Разрешите HTTPS: `sudo ufw allow 443/tcp`
- [ ] Включите firewall: `sudo ufw enable`
- [ ] Проверьте статус: `sudo ufw status`

### Резервное копирование

- [ ] Создайте скрипт backup: `nano backup.sh`
- [ ] Добавьте команды из `DEPLOYMENT.md`
- [ ] Сделайте исполняемым: `chmod +x backup.sh`
- [ ] Настройте cron для автоматического backup: `crontab -e`
- [ ] Добавьте: `0 2 * * * /home/user/plane/backup.sh`
- [ ] Проверьте backup: `./backup.sh`

### Мониторинг

- [ ] Настройте мониторинг логов: `docker compose logs -f api`
- [ ] Проверьте использование ресурсов: `docker stats`
- [ ] Настройте алерты (опционально)

## Финальная проверка

- [ ] Все контейнеры запущены: `docker compose ps`
- [ ] API отвечает: `curl http://localhost:8000/api/instances/`
- [ ] Web UI доступен
- [ ] Можно войти в систему
- [ ] Можно создать workspace
- [ ] Можно создать проект
- [ ] Можно создать задачу
- [ ] Генерация отчетов работает (если настроен LLM)
- [ ] Загрузка файлов работает (MinIO)
- [ ] Email уведомления работают (если настроены)

## Troubleshooting

Если что-то не работает:

1. **Проверьте логи:**

   ```bash
   docker compose logs -f api
   docker compose logs -f worker
   docker logs plane-plane-db-1
   ```

2. **Проверьте переменные окружения:**

   ```bash
   docker exec plane-api-1 printenv | grep LLM
   docker exec plane-api-1 printenv | grep DATABASE
   ```

3. **Перезапустите контейнеры:**

   ```bash
   docker compose down
   docker compose up -d
   ```

4. **Проверьте порты:**

   ```bash
   sudo netstat -tulpn | grep LISTEN
   ```

5. **Проверьте диск:**
   ```bash
   df -h
   docker system df
   ```

## Полезные команды

```bash
# Просмотр логов
docker compose logs -f api

# Перезапуск сервиса
docker compose restart api

# Обновление проекта
git pull origin main
docker compose down
docker compose build
docker compose up -d

# Очистка Docker
docker system prune -a

# Backup БД
docker exec plane-plane-db-1 pg_dump -U plane plane > backup.sql

# Восстановление БД
cat backup.sql | docker exec -i plane-plane-db-1 psql -U plane plane
```

---

## 🎉 Готово!

Если все пункты отмечены, ваш Plane успешно развернут на Ubuntu Server!
