import { useState } from "react";
import { CopilotChat, CopilotKit, useDefaultRenderTool } from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";
import { PageBoard } from "./PageBoard";
import { PageProvider } from "./pageState";
import { PageTools } from "./pageTools";
import "./page.css";

const CHAT_WIDTH_KEY = "v2-chat-dock-width";
const CHAT_MIN = 360;
const CHAT_DEFAULT = 480;

function readChatWidth() {
  const raw = localStorage.getItem(CHAT_WIDTH_KEY);
  const saved = Number(raw);
  // 没有存过时 getItem 是 null，Number(null) 会变成 0，栏会被收成一条缝。
  if (!raw || !Number.isFinite(saved) || saved < CHAT_MIN) return CHAT_DEFAULT;
  return saved;
}

const labels = {
  modalHeaderTitle: "物流助手",
  welcomeMessageText: "可以说「打开华运，看近 30 天异常」，也可以问船期、货踪、运价。",
  chatInputPlaceholder: "输入消息",
  chatDisclaimerText: "请核对票号和船期，不要直接当成最终结果。",
};

const toolNames = {
  open_customer: "打开客户",
  set_date_range: "设置日期",
  get_screen_context: "读取屏幕",
  run_skill: "运行技能",
  task: "交给专家",
};

// 工具事件已经在回复流里。这里只决定聊天里怎么画，不增加后端接口。
function ToolTrace() {
  useDefaultRenderTool({
    render: ({ name, status, parameters, result }) => (
      <details className="tool-trace" open={status !== "complete"}>
        <summary>
          {status === "complete" ? "已调用" : "正在调用"} {toolNames[name] || name}
        </summary>
        <p>参数：{JSON.stringify(parameters ?? {}, null, 2)}</p>
        {status === "complete" ? <p>结果：{result || "（无文本结果）"}</p> : null}
      </details>
    ),
  });
  return null;
}

function ChatDock() {
  const [width, setWidth] = useState(readChatWidth);

  // 往左拖变宽。宽度写在变量上，窄屏样式才能改回 100%。
  function onPointerDown(event) {
    event.preventDefault();
    const handle = event.currentTarget;
    // 捕获失败时仍监听这次拖动，避免指针一离开细条就断掉。
    try {
      handle.setPointerCapture(event.pointerId);
    } catch {
      // 没有真实指针时捕获会失败，后面的监听仍然有效。
    }
    const startX = event.clientX;
    const startWidth = width;
    let next = startWidth;

    function move(moveEvent) {
      const max = Math.max(CHAT_MIN, Math.round(window.innerWidth * 0.72));
      next = Math.min(max, Math.max(CHAT_MIN, Math.round(startWidth + (startX - moveEvent.clientX))));
      setWidth(next);
    }

    function up() {
      localStorage.setItem(CHAT_WIDTH_KEY, String(next));
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", up);
    }

    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", up);
  }

  return (
    <aside className="chat-dock" style={{ "--chat-width": `${width}px` }}>
      <div
        className="chat-resizer"
        role="separator"
        tabIndex={0}
        aria-orientation="vertical"
        aria-label="拖动调整聊天栏宽度"
        aria-valuenow={width}
        onPointerDown={onPointerDown}
      />
      <header className="chat-header">物流助手</header>
      <div className="chat-body">
        <CopilotChat
          labels={labels}
          messageView={{
            reasoningMessage: {
              header: { label: "思考过程" },
            },
          }}
        />
      </div>
    </aside>
  );
}

function App() {
  return (
    // runtimeUrl 指向 Copilot Runtime，不是 Python 的 /ag-ui。
    // 调试浮标在开发环境默认出现。要关掉时写 enableInspector={false}。
    <CopilotKit runtimeUrl="/api/copilotkit" agentId="logistics_assistant">
      <PageProvider>
        <PageTools />
        <ToolTrace />
        <div className="app-shell">
          <div className="app-main">
            <header className="page-title">
              <h1>智能物流助手</h1>
              <p>对右侧说「打开华运，看近 30 天异常」。页面变化来自前端函数，不来自 Python 接口。</p>
            </header>
            <PageBoard />
          </div>
          <ChatDock />
        </div>
      </PageProvider>
    </CopilotKit>
  );
}

export default App;
