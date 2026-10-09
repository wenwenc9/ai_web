import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime } from "@copilotkit/runtime/v2";
import { createCopilotNodeListener } from "@copilotkit/runtime/v2/node";

// 上一次 npm run dev 留下的 Runtime 还占着端口时，再 listen 会抛 EADDRINUSE。
// 先关掉那个进程，这次启动才能接上 Vite 的代理。
function freePort(port) {
  if (process.platform !== "win32") return;
  const output = execFileSync("netstat", ["-ano"], { encoding: "utf8" });
  for (const line of output.split(/\r?\n/)) {
    const parts = line.trim().split(/\s+/);
    if (parts.length < 5 || parts[0] !== "TCP" || parts[3] !== "LISTENING") continue;
    if (!parts[1].endsWith(`:${port}`)) continue;
    const pid = Number(parts[4]);
    if (!pid || pid === process.pid) continue;
    console.log(`端口 ${port} 被 PID ${pid} 占用，关闭上一次的 Runtime`);
    execFileSync("taskkill", ["/F", "/PID", String(pid)], { stdio: "ignore" });
  }
}

const agentUrl = process.env.LANGGRAPH_DEPLOYMENT_URL || "http://127.0.0.1:9001/ag-ui";
const port = Number(process.env.COPILOT_RUNTIME_PORT || 9002);

process.on("unhandledRejection", (error) => {
  console.error("Copilot Runtime kept running after an agent stream error:", error);
});

const runtime = new CopilotRuntime({
  // CopilotPopup 找不到自己的 agentId 时固定找 default。两个名字各用一个实例，避免共用一份会话状态。
  agents: {
    default: new HttpAgent({ url: agentUrl }),
    logistics_assistant: new HttpAgent({ url: agentUrl }),
  },
});

const listener = createCopilotNodeListener({
  runtime,
  basePath: "/api/copilotkit",
  cors: true,
});

freePort(port);
const server = createServer(listener);
server.on("error", (error) => {
  if (error.code === "EADDRINUSE") {
    console.error(`端口 ${port} 仍被占用。先在运行 npm run dev 的终端按 Ctrl+C，再重新执行。`);
    process.exit(1);
  }
  throw error;
});
server.listen(port, "127.0.0.1", () => {
  console.log(`Copilot Runtime listening at http://127.0.0.1:${port}/api/copilotkit`);
  console.log(`AG-UI agent: ${agentUrl}`);
});
