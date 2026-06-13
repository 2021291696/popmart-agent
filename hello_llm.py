# 第1步：导入需要的库
import os                          # os 库：和操作系统打交道（读取环境变量）
from openai import OpenAI          # OpenAI SDK：调用大模型的标准接口
from dotenv import load_dotenv     # dotenv：自动读 .env 文件

# 第2步：加载 .env 文件
load_dotenv()                      # 执行后，.env 里的 DEEPSEEK_API_KEY 就变成环境变量了

# 第3步：读取 API Key
api_key = os.environ.get("DEEPSEEK_API_KEY", "")

# 第4步：创建客户端
client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

# 第5步：调用大模型
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "你是泡泡玛特商业分析助手。"},
        {"role": "user", "content": "你好！用一句话介绍你自己。"}
    ],
    temperature=0.7
)

# 第6步：打印回复
print(response.choices[0].message.content)