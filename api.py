from openai import OpenAI
# Set OpenAI's API key and API base to use vLLM's API server.
openai_api_key = "ollama"
openai_api_base = "http://localhost:11434/v1/"

client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)

chat_response = client.chat.completions.create(
    model="/home/ps/zz/qwen2.5vl",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "praise me"},
    ]
)
print("Chat response:", chat_response)