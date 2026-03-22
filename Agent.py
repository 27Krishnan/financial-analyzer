import requests

# 🔑 உங்கள் NVIDIA API key (இங்க மட்டும் paste பண்ணு)
API_KEY = "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"

# 🌐 Endpoint
URL = "https://integrate.api.nvidia.com/v1/chat/completions"

print("🤖 AI Ready (type 'exit' to stop)\n")

while True:
    user_input = input("You: ")

    if user_input.lower() == "exit":
        print("👋 Exiting...")
        break

    headers = {
        "Authorization": f"Bearer {API_KEY}",   # ❗ இங்க மீண்டும் paste பண்ண வேண்டாம்
        "Content-Type": "application/json"
    }

    data = {
        "model": "deepseek-ai/deepseek-v3_1-terminus",
        "messages": [
            {"role": "user", "content": user_input}
        ],
        "temperature": 0.3,
        "max_tokens": 500
    }

    try:
        response = requests.post(URL, headers=headers, json=data)

        # 🔍 Debug (important)
        print("RAW:", response.text)

        result = response.json()

        if "choices" in result:
            reply = result["choices"][0]["message"]["content"]
            print("\nAI:", reply, "\n")
        else:
            print("⚠️ API Error:", result)

    except Exception as e:
        print("❌ Error:", e)