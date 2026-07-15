# 排障：改了代码但接口行为没变（reload 漏检 + 孤儿进程占端口）

> 2026-07-15 数据中心化重构收尾时实录。现象：改了 `src/pipeline/sources.py` 的抓取源 URL，连续两次刷新跑出的还是旧 URL。

## 症状

1. 编辑 `src/pipeline/sources.py`（官网源 `popmart.com/cn` → `popmart.com.cn/`）
2. `POST /api/data/refresh` 跑完，抓取的仍是旧 URL 的内容
3. `GET /api/data/overview` 返回的 `sources[].url` 也是旧值——**服务端在跑旧代码**

## 根因（两个叠加）

1. **uvicorn --reload 的 WatchFiles 漏检**：此前对 `api.py`、`src/api_*.py` 的改动都正常触发重载（日志有 `Reloading...`），但这次对 `sources.py` 的编辑静默漏掉，日志无任何重载记录。
2. **孤儿 server 子进程占端口**：手动重启时 `taskkill` 只杀了 reloader 父进程，它 spawn 的 server 子进程成为孤儿继续存活。Windows 允许同一端口双绑定（SO_REUSEADDR），新旧进程同时 LISTEN 8000，请求被随机路由到旧进程。

## 排查路径（按此顺序最快）

```bash
# 1. 确认磁盘文件确实是新代码（排除"编辑没保存"）
grep -n "popmart.com" src/pipeline/sources.py

# 2. 查 uvicorn 日志有没有 Reloading 记录（没有 = reload 漏检）
grep -n "Reloading" logs/uvicorn-restart.log | tail -5

# 3. 查 8000 端口是不是多个进程在听（出现多行 = 有孤儿）
netstat -ano | grep ":8000" | grep LISTENING

# 4. 按启动时间找出旧的 uvicorn server 子进程（multiprocessing.spawn 那条）
#    Git Bash 里 $_ 会被吞，PowerShell 脚本要写成 .ps1 文件再执行
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |  # 见下「工具坑」
  Select ProcessId, CreationDate, CommandLine

# 5. 精确杀旧子进程（别碰 scrapling/kimi runtime 的 python）
taskkill //F //PID <旧子进程PID>

# 6. 用接口返回值验证新代码生效（overview 的 sources[].url 直接反映代码）
curl -s http://localhost:8000/api/data/overview
```

## 预防规则

- **接口行为与代码不符时，第一反应查端口占用者是不是旧进程**，不要怀疑代码
- 杀 uvicorn 要杀整棵树：reloader（父）+ server 子进程（`python -c "from multiprocessing.spawn..."`，启动时间与 reloader 相差 1 秒内）
- 杀完必须 `netstat` 复查只剩一个 LISTENING，再用接口返回值（而非"没报错"）确认新代码生效
- 改了 `src/` 下文件后如果 10 秒内日志没有 `Reloading...`，手动重启并走上面第 3-6 步

## 工具坑

- Git Bash 执行 PowerShell 单行命令时 `$_` 会被 bash 抢先展开（变成当前路径）——PowerShell 脚本一律写 `.ps1` 文件再 `powershell.exe -File` 执行
- `ps -ef` 显示的 PID 是 Git Bash 视图，`taskkill` 要用 Windows PID（`netstat -ano` 第 5 列 / `tasklist` 查）
- Git Bash 直接调 `powershell` 找不到，用全路径 `/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe`
