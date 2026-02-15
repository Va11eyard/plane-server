# Настройка LLM для генерации отчетов

## Проблема

При попытке сгенерировать отчет появляется ошибка:

```
LLM не настроен (нужен API-ключ и провайдер). Настройте DeepSeek или другого провайдера в настройках инстанса.
```

## Решение

### Вариант 1: DeepSeek (Рекомендуется для разработки)

DeepSeek - это дешевая альтернатива OpenAI с хорошим качеством для русского языка.

1. **Получите API ключ:**
   - Зарегистрируйтесь на https://platform.deepseek.com/
   - Перейдите в раздел API Keys: https://platform.deepseek.com/api_keys
   - Создайте новый ключ и скопируйте его

2. **Добавьте в `.env` файл:**

   ```bash
   # В файле apps/api/.env добавьте:
   LLM_PROVIDER="deepseek"
   LLM_MODEL="deepseek-chat"
   LLM_API_KEY="sk-ваш-ключ-здесь"
   ```

3. **Перезапустите API:**
   ```bash
   docker compose -f docker-compose-local.yml restart api
   ```

### Вариант 2: OpenAI

1. **Получите API ключ:**
   - Зарегистрируйтесь на https://platform.openai.com/
   - Перейдите в API Keys: https://platform.openai.com/api-keys
   - Создайте новый ключ

2. **Добавьте в `.env` файл:**

   ```bash
   LLM_PROVIDER="openai"
   LLM_MODEL="gpt-4o-mini"
   LLM_API_KEY="sk-ваш-ключ-здесь"
   ```

3. **Перезапустите API:**
   ```bash
   docker compose -f docker-compose-local.yml restart api
   ```

### Вариант 3: Другие провайдеры

Система также поддерживает:

**Anthropic (Claude):**

```bash
LLM_PROVIDER="anthropic"
LLM_MODEL="claude-3-sonnet-20240229"
LLM_API_KEY="sk-ant-ваш-ключ"
```

**Google Gemini:**

```bash
LLM_PROVIDER="gemini"
LLM_MODEL="gemini-pro"
LLM_API_KEY="ваш-ключ"
```

## Доступные модели

### DeepSeek

- `deepseek-chat` (по умолчанию, рекомендуется)
- `deepseek-reasoner`

### OpenAI

- `gpt-4o-mini` (по умолчанию, дешевле)
- `gpt-3.5-turbo`
- `gpt-4o`
- `o1-mini`
- `o1-preview`

### Anthropic

- `claude-3-sonnet-20240229` (по умолчанию)
- `claude-3-5-sonnet-20240620`
- `claude-3-haiku-20240307`
- `claude-3-opus-20240229`

### Gemini

- `gemini-pro` (по умолчанию)
- `gemini-1.5-pro-latest`
- `gemini-pro-vision`

## Проверка настройки

После настройки попробуйте сгенерировать отчет:

1. Откройте проект в Plane
2. Перейдите в раздел "Отчеты"
3. Выберите период и нажмите "Сгенерировать отчет"

Если всё настроено правильно, система сгенерирует отчет на русском языке.

## Стоимость (примерно)

- **DeepSeek**: ~$0.14 за 1M токенов (очень дешево)
- **OpenAI GPT-4o-mini**: ~$0.15 за 1M входных токенов
- **OpenAI GPT-4o**: ~$2.50 за 1M входных токенов
- **Claude 3 Sonnet**: ~$3.00 за 1M входных токенов

Для локальной разработки рекомендуется DeepSeek или GPT-4o-mini.
