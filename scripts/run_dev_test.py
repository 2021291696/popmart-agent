"""本地测试启动器:设置 ALLOW_LOCAL_DEV 后启动 Streamlit。"""
import os
import sys

os.environ["ALLOW_LOCAL_DEV"] = "1"

# 让 uv run 找到项目根
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

# 调用 streamlit 模块入口
sys.argv = [
    "streamlit",
    "run",
    "app.py",
    "--server.headless", "true",
    "--server.port", "8501",
]

from streamlit.web.cli import main
main()
