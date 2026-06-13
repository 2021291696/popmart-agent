import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
    base_url="https://api.deepseek.com"
)

# messages 是对话历史——Agent 的"短期记忆"
# 一开始只有 system 规矩，没有任何用户对话
messages = [
    {"role": "system", "content": "你是泡泡玛特商业分析助手。"}
]

print("泡泡玛特 AI 助手 (输入 '退出' 结束)\n")

while True:
    # input() 作用：暂停程序，等用户在终端打字，按回车后把内容给 user_input
    user_input = input("你: ")
    if user_input == "退出":
        break

    # 把用户这条消息追加到对话历史
    messages.append({"role": "user", "content": user_input})

    # 把完整的对话历史发给 LLM——这就是它"记得之前说了什么"的原因
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.7
    )

    reply = response.choices[0].message.content
    print(f"AI: {reply}\n")

    # 把 AI 的回复也追加到对话历史——下一轮它知道自己上一轮说了什么
    messages.append({"role": "assistant", "content": reply})