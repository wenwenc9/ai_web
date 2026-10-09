from __future__ import annotations
import os
import sys
import socket
import time
import subprocess
import asyncio
from dotenv import load_dotenv, find_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
# 备选：内存版快速验证
# from langgraph.checkpoint.memory import MemorySaver

from deepagents import create_deep_agent, FilesystemPermission
from deepagents.backends import CompositeBackend, FilesystemBackend
from copilotkit import CopilotKitMiddleware, LangGraphAGUIAgent
from ag_ui_langgraph import add_langgraph_fastapi_endpoint

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# 加载环境变量
load_dotenv(find_dotenv())
llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL"),
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)


# 项目根目录（本文件所在目录），避免依赖启动时的工作目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(PROJECT_ROOT, "skills")
# 参数按空格切开后直接交给脚本。这些符号会变成 shell 拼接，这里直接拒绝。
_SHELL_CHARS = set(";|&$`<>\n\r")


def _plain_name(value: str, label: str) -> str:
    name = value or ""
    if name != name.strip() or not name or "/" in name or "\\" in name or ".." in name:
        raise ValueError(f"{label} 只能是 skills 目录下的名字，不能带路径")
    return name


@tool
def run_skill(skill_name: str, script_name: str, command_args: str = "") -> str:
    """运行 skills 目录里已经放好的脚本。

    skill_name 是 skills 下的文件夹名，例如 sofreight-sailing-schedule。
    script_name 是该文件夹 scripts 目录下的文件名，例如 schedule.py。
    command_args 是空格分隔的参数，例如 "--pol 上海 --dest 雅加达"。
    新技能整夹放进 skills 即可，这里不用再登记名字。
    """
    if not isinstance(command_args, str):
        command_args = " ".join(str(item) for item in command_args)
    if any(char in command_args for char in _SHELL_CHARS):
        return "command_args 不能包含 shell 符号"

    try:
        skill_name = _plain_name(skill_name, "skill_name")
        script_name = _plain_name(script_name, "script_name")
    except ValueError as exc:
        return str(exc)
    if not script_name.endswith(".py"):
        script_name = f"{script_name}.py"

    script_path = os.path.abspath(os.path.join(SKILLS_DIR, skill_name, "scripts", script_name))
    scripts_root = os.path.abspath(os.path.join(SKILLS_DIR, skill_name, "scripts"))
    if os.path.commonpath([scripts_root, script_path]) != scripts_root or not os.path.isfile(script_path):
        return f"没有这个技能脚本: {skill_name}/scripts/{script_name}"

    cmd = [sys.executable, script_path] + (command_args.split() if command_args else [])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode != 0:
        return f"执行失败（退出码 {result.returncode}）：{err or output}"
    return output if output else "执行成功（退出码 0），无输出"


# ==============================================
# 2. 端口占用检查：启动前释放端口，避免 socket 冲突
# ==============================================
def _port_in_use(port: int) -> bool:
    """探测端口是否已被占用。

    优先用 netstat 查 LISTENING 记录（可靠且能拿到 PID）；
    兜底用不带 SO_REUSEADDR 的 bind 探测——Windows 上 SO_REUSEADDR
    允许重复绑定已被监听的端口，会误判为“空闲”。
    """
    if _find_pid_by_port(port) is not None:
        return True
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return False
        except OSError:
            return True


def _find_pid_by_port(port: int):
    """通过 netstat 找到监听指定端口的进程 PID"""
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, errors="replace"
        ).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] == "TCP":
                addr, state, pid = parts[1], parts[3], parts[4]
                if state == "LISTENING" and addr.endswith(f":{port}") and pid.isdigit():
                    return int(pid)
    except Exception:
        pass
    return None


def _kill_process(pid: int) -> None:
    """终止占用端口的进程"""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, 9)
    except Exception as e:
        print(f"[警告] 终止进程 {pid} 失败：{e}")


def ensure_port_free(port: int, timeout: float = 5.0) -> None:
    """启动前检查端口；若被占用，自动关闭占用该端口的进程并等待释放"""
    if not _port_in_use(port):
        print(f"[端口检查] 端口 {port} 空闲，可直接启动")
        return

    pid = _find_pid_by_port(port)
    if pid is None:
        print(f"[端口检查] 端口 {port} 被占用但未找到监听进程，请手动排查")
        return

    print(f"[端口检查] 端口 {port} 被 PID {pid} 占用，正在自动关闭...")
    _kill_process(pid)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _port_in_use(port):
            print(f"[端口检查] 端口 {port} 已释放")
            return
        time.sleep(0.3)
    print(f"[端口检查] 等待 {timeout}s 后端口 {port} 仍未释放，继续启动（可能由 TIME_WAIT 引起）")


# ==============================================
# 3. 文件系统与权限
# ==============================================
file_backend = CompositeBackend(
    default=FilesystemBackend(root_dir="./workspace", virtual_mode=True),
    routes={
        "/skills/": FilesystemBackend(root_dir="./skills", virtual_mode=True),
    }
)

# 规则按声明顺序，第一条命中的生效。没写到的路径默认允许写入。
# 默认根是 ./workspace，虚拟路径是 /文件名，不是 /work/文件名。
permissions = [
    FilesystemPermission(
        operations=["write"],
        paths=["/skills/**"],
        mode="deny",
    ),
]

# ==============================================
# 4. 领域子 Agent
# ==============================================
ship_schedule_expert = {
    "name": "船期专家",
    "description": "负责船期查询、航线规划、截关时间",
    "system_prompt": """
    你是船期专家，只处理船期相关问题。
    使用 /skills/sofreight-sailing-schedule/ 技能包处理请求，严格遵守技能包里的规则。
    先读取 /skills/sofreight-sailing-schedule/SKILL.md 了解调用方式和参数，
    再用 run_skill 执行：skill_name 为 sofreight-sailing-schedule，script_name 为 schedule.py。
    把 SKILL.md 中的命令行参数（如 --pol、--dest、--pol-code、--dest-code）拼进 command_args。
    结果清晰整理后返回。
    """,
    "tools": [run_skill],
    # isolated 子 Agent 不会继承主 Agent 的 skills 参数，所以这里自己声明。
    "skills": ["/skills/"],
}

cargo_tracking_expert = {
    "name": "货踪专家",
    "description": "负责货物跟踪、提单查询、订阅管理",
    "system_prompt": """
    你是货踪专家，只处理货物跟踪相关问题。
    使用 /skills/sofreight-cargo-tracking/ 技能包处理请求，严格遵守技能包里的所有铁律。
    先读取 /skills/sofreight-cargo-tracking/SKILL.md 了解规则、参数、退出码，
    再用 run_skill 执行：skill_name 为 sofreight-cargo-tracking，script_name 为 tracking.py。
    把 SKILL.md 中的命令行参数（如 --numbers、--carrier、--confirmed、--subscribe、--list）拼进 command_args。
    缺Key引导用户配置，多船司让用户选择，订阅必须用户确认。
    """,
    "tools": [run_skill],
    "skills": ["/skills/"],
}

freight_expert = {
    "name": "运价专家",
    "description": "负责海运运价、费用计算、航线报价",
    "system_prompt": """
    你是运价专家，只处理运价报价相关问题。
    使用 /skills/sofreight-sea-freight-price/ 技能包处理请求，严格遵守技能包里的规则。
    先读取 /skills/sofreight-sea-freight-price/SKILL.md 了解调用方式和参数，
    再用 run_skill 执行：skill_name 为 sofreight-sea-freight-price，script_name 为 price.py。
    把 SKILL.md 中的命令行参数拼进 command_args。
    对比多家运价，给出建议。
    """,
    "tools": [run_skill],
    "skills": ["/skills/"],
}


# ==============================================
# 5. 异步主程序：AsyncSqliteSaver + 服务启动
# ==============================================
async def main():
    # ===== SQLite 异步持久化（生产用）=====
    async with AsyncSqliteSaver.from_conn_string("logistics_sessions.db") as checkpointer:
        # ===== 备选：内存版（快速验证，注释上面两行，取消下面注释即可）=====
        # checkpointer = MemorySaver()

        main_agent = create_deep_agent(
            model=llm,
            # 这里不写 open_customer 这类名字。换一个业务系统时，页面会登记另一套函数。
            # 函数名和参数随这次 /ag-ui 请求带来，CopilotKitMiddleware 让主 Agent 能看见。
            system_prompt="""
            你是智能物流助手，用中文回复。你负责分发和页面操作，不要自己调用 run_skill，也不要自己读技能脚本。

            这次请求可能带有一组前端工具。它们的名字、说明和参数以请求里的工具清单为准，不要假设固定叫某个名字。
            用户要改页面、打开某条数据或筛选时，必须调用说明相符的前端工具，不能只在聊天里说已经完成。
            用户要解释屏幕上的票号、状态或原因时，必须先调用说明为「读取当前屏幕」的那个前端工具，只引用它的返回值，禁止编造。
            请求里没有这类工具时，直接说明当前页面没有这项操作。

            船期、航线、截关、开船交给「船期专家」。
            货踪、货物位置、提单、订阅交给「货踪专家」。
            运价、费用、报价、海运费交给「运价专家」。
            复杂问题可协同多个专家，再由你汇总。闲聊直接回答。
            """,
            subagents=[
                ship_schedule_expert,
                cargo_tracking_expert,
                freight_expert,
            ],
            middleware=[CopilotKitMiddleware()],
            backend=file_backend,
            permissions=permissions,
            checkpointer=checkpointer,
        )

        # ==============================================
        # 5. FastAPI + AG-UI 标准接口
        # ==============================================
        app = FastAPI(title="智能物流Agent服务")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        add_langgraph_fastapi_endpoint(
            app=app,
            agent=LangGraphAGUIAgent(
                name="logistics_assistant",
                description="智能物流助手：船期、货踪、运价",
                graph=main_agent,
                # 多轮子 Agent + 读技能文档 + 执行脚本的流程步数多，
                # 默认 recursion_limit=25 必然超限，这里放宽
                config={"recursion_limit": 200},
            ),
            path="/ag-ui",
        )

        # 异步启动服务
        # 启动前检查端口占用，若被占用自动关闭占用进程，避免 socket 冲突
        ensure_port_free(9001)
        config = uvicorn.Config(app, host="0.0.0.0", port=9001)
        server = uvicorn.Server(config)
        await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
