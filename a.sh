 curl http://127.0.0.1:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2-vision",
    "messages": [{"role": "user", "content": "你好，你能看见什么？"}],
    "max_tokens": 50
  }'