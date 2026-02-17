# Исправление редиректа на localhost при использовании ngrok

## Проблема

В `apps/api/.env` на сервере указаны localhost-URL, из‑за чего редиректы идут на localhost вместо ngrok.

## Решение

На сервере в `~/plane-server` выполните:

```bash
# 1. Обновить apps/api/.env — заменить localhost на ngrok URL
NGROK="https://e7b2-147-30-78-171.ngrok-free.app"

sed -i "s|WEB_URL=.*|WEB_URL=\"$NGROK\"|" apps/api/.env
sed -i "s|ADMIN_BASE_URL=.*|ADMIN_BASE_URL=\"$NGROK\"|" apps/api/.env
sed -i "s|SPACE_BASE_URL=.*|SPACE_BASE_URL=\"$NGROK\"|" apps/api/.env
sed -i "s|APP_BASE_URL=.*|APP_BASE_URL=\"$NGROK\"|" apps/api/.env
sed -i "s|LIVE_BASE_URL=.*|LIVE_BASE_URL=\"$NGROK\"|" apps/api/.env

# 2. Убрать trailing slash из WEB_URL в корневом .env (если есть)
sed -i 's|WEB_URL=https://\(.*\)/$|WEB_URL=https://\1|' .env

# 3. Перезапустить контейнеры
docker compose down && docker compose up -d
```

При смене ngrok URL замените `NGROK` на новый адрес.
