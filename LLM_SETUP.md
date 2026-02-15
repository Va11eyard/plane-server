# LLM Setup for Report Generation

## Quick Setup

To enable AI-powered report generation, you need to configure an LLM provider.

### Option 1: DeepSeek (Recommended for Development)

1. Get API key from https://platform.deepseek.com/api_keys
2. Add to `apps/api/.env`:
   ```bash
   LLM_PROVIDER="deepseek"
   LLM_MODEL="deepseek-chat"
   LLM_API_KEY="sk-your-key-here"
   ```
3. Restart API:
   ```bash
   docker compose -f docker-compose-local.yml restart api
   ```

### Option 2: OpenAI

1. Get API key from https://platform.openai.com/api-keys
2. Add to `apps/api/.env`:
   ```bash
   LLM_PROVIDER="openai"
   LLM_MODEL="gpt-4o-mini"
   LLM_API_KEY="sk-your-key-here"
   ```
3. Restart API

## Supported Providers

- **DeepSeek**: `deepseek-chat`, `deepseek-reasoner`
- **OpenAI**: `gpt-4o-mini`, `gpt-4o`, `gpt-3.5-turbo`, `o1-mini`, `o1-preview`
- **Anthropic**: `claude-3-sonnet-20240229`, `claude-3-5-sonnet-20240620`, etc.
- **Gemini**: `gemini-pro`, `gemini-1.5-pro-latest`, `gemini-pro-vision`

## Cost Comparison (approximate)

- DeepSeek: ~$0.14 per 1M tokens (cheapest)
- OpenAI GPT-4o-mini: ~$0.15 per 1M input tokens
- OpenAI GPT-4o: ~$2.50 per 1M input tokens
- Claude 3 Sonnet: ~$3.00 per 1M input tokens

For local development, DeepSeek or GPT-4o-mini are recommended.
