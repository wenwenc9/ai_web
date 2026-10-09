# 从 0 到 1：页面怎么连上 LangGraph Agent

这份笔记只讲连接。安装和报错表在 [README.md](README.md)。读完应能理解：CopilotKit、Runtime、AG-UI、Deep Agents 各是什么，`/ag-ui` 是什么地址，前端为什么选不中「船期专家」。

## 整体架构

我们用 Python 的 Deep Agents 做了一张图。这张图里有一个主 Agent，下面挂着船期、货踪、运价三个专家。三个专家不是三个网站，也不是前端下拉框里的三个选项。用户在页面上只连这一张图。

页面用的聊天组件是 CopilotKit。它不直接访问 Python。它先访问本机的 Copilot Runtime（9002）。Runtime 再按 AG-UI 协议，把消息 POST 到 `http://127.0.0.1:9001/ag-ui`。`/ag-ui` 是我们在 FastAPI 上挂这张图的路径，不是又一个框架。

前端如果要让模型点击页面，就在 React 里用 `useFrontendTool` 登记函数。函数在浏览器里执行。模型看见的是这次请求带来的名字和说明，Python 不把某个业务系统的按钮名写死。

## 五个词

| 词 | 一句话 | 在本仓库的哪 |
| --- | --- | --- |
| LangGraph | 跑 Agent 的引擎。保存对话状态，按步骤调用模型和工具。 | `create_deep_agent` 内部编出来的那张图 |
| Deep Agents | 在 LangGraph 上包了一层。负责子 Agent、读文件、技能目录。我们不用手写整张流程图。 | `logistics_agent.py` 里的 `create_deep_agent` |
| AG-UI | 浏览器侧和 Agent 之间的报文协议。规定一次运行要带 `threadId`、`runId`、`messages`，并用 SSE 把文字和工具调用流回来。 | Python 的 `POST /ag-ui` |
| CopilotKit | 页面上的聊天组件，以及「把页面函数登记给模型」的 React 库。 | `App.jsx`、`pageTools.jsx` |
| Copilot Runtime | 夹在页面和 Python 之间的 Node 程序。页面问它有哪些 Agent，它再去请求 Python。 | `copilotkit-frontend/runtime.js`，端口 9002 |

官方文档：

- Deep Agents 总览：<https://docs.langchain.com/oss/python/deepagents/overview>
- Deep Agents 子 Agent：<https://docs.langchain.com/oss/python/deepagents/subagents>
- CopilotKit 如何通过 Runtime 使用 AG-UI：<https://docs.copilotkit.ai/langgraph-python/ag-ui>
- 自建 FastAPI 时要用 `HttpAgent`，不能把 FastAPI 当成 LangGraph 云平台地址：<https://docs.copilotkit.ai/langgraph-python/coagent-troubleshooting/common-coagent-issues>
- 前端登记工具：<https://docs.copilotkit.ai/reference/v2/hooks/useFrontendTool>
- 前端工具概念：<https://docs.copilotkit.ai/frontend-tools>

## 两个「Agent」不是同一层

这里最容易混淆。

**第一层：页面可选的连接名。** 写在 `runtime.js`：

```js
agents: {
  default: new HttpAgent({ url: "http://127.0.0.1:9001/ag-ui" }),
  logistics_assistant: new HttpAgent({ url: "http://127.0.0.1:9001/ag-ui" }),
}
```

这是两扇门，门后是同一个 Python 地址。右侧聊天栏用的是 `CopilotChat`，它按 `<CopilotKit agentId="logistics_assistant">` 走第二扇门。`default` 仍留着：有的组件没拿到 agentId 时会找这扇门。少了它，页面可能报 `Agent 'default' not found`。

**第二层：图里面的专家。** 写在 `logistics_agent.py` 的 `subagents`：船期专家、货踪专家、运价专家。它们没有自己的 URL，聊天栏里也没有下拉框。用户说话之后，主 Agent 调用 Deep Agents 的 `task` 工具，把任务交给其中一个专家。用户不能在右侧聊天里「选中船期专家」。这次调用会显示成「交给专家」。

`LangGraphAGUIAgent(..., name="logistics_assistant")` 只是这张图在 Python 侧的说明文字。前端选中的不是这个 `name` 字段，而是 `runtime.js` 里的键。

## 地址分别指什么

| 你看到的字符串 | 它在哪 | 谁来访问 |
| --- | --- | --- |
| `http://localhost:5177/` | 网页 | 人用浏览器打开 |
| `runtimeUrl="/api/copilotkit"` | `App.jsx` | 浏览器里的 CopilotKit。实际请求是 `http://localhost:5177/api/copilotkit/...` |
| `proxy: { "/api/copilotkit": "http://127.0.0.1:9002" }` | `vite.config.js` | Vite。把上面的请求转到本机 9002 |
| `basePath: "/api/copilotkit"` | `runtime.js` | Runtime 自己约定：信息接口是这个路径加 `/info` |
| `http://127.0.0.1:9001/ag-ui` | `runtime.js` 的 `agentUrl` | 只有 Runtime 访问。浏览器不要直接填这个 |
| `path="/ag-ui"` | `logistics_agent.py` 的 `add_langgraph_fastapi_endpoint` | 把「整段 URL 的路径部分」定成 `/ag-ui`。端口 9001 是 `uvicorn` 的 `port=9001` |

所以 `http://127.0.0.1:9001/ag-ui` = 本机 + 9001 端口 + 路径 `/ag-ui`。路径是我们起的名字，协议才叫 AG-UI。

页面刚打开时的探活是：

```text
GET http://localhost:5177/api/copilotkit/info
```

Runtime 返回 `default` 和 `logistics_assistant`。这一步不进 Python，也不跑模型。

用户按下发送之后：

```text
Runtime  POST http://127.0.0.1:9001/ag-ui
正文至少有 threadId、runId、messages
Python 用 SSE 把 RUN_STARTED、文字、工具调用流回来
```

如果把 `App.jsx` 的 `runtimeUrl` 写成 `http://localhost:9001/ag-ui`，浏览器会自己去要 `GET /ag-ui/info`。Python 没有这个路径。接着浏览器再 POST `{"method":"info"}`，而 `/ag-ui` 要的是 `threadId`、`runId`、`messages`，于是 422。

## 一条「你好」经过哪些文件

1. 人在右侧 `CopilotChat` 里输入。组件来自 `@copilotkit/react-core/v2`，放在 `App.jsx`。
2. `App.jsx` 的 `<CopilotKit runtimeUrl="/api/copilotkit">` 决定请求打到网页的 `/api/copilotkit`。
3. `vite.config.js` 把该路径转到 `127.0.0.1:9002`。
4. `runtime.js` 看到要找的名字是 `default` 或 `logistics_assistant`，用对应的 `HttpAgent` 请求 `http://127.0.0.1:9001/ag-ui`。
5. `logistics_agent.py` 里 `add_langgraph_fastapi_endpoint(..., path="/ag-ui")` 接到请求，交给 `create_deep_agent` 编出来的那张图。
6. 主 Agent 发现只是打招呼，自己回答。不叫船期专家，也不跑 `run_skill`。
7. 文字沿原路流回右侧聊天栏。模型若带了思考事件，栏里显示「思考过程」。调用了哪个函数，由 `App.jsx` 里的 `ToolTrace` 画出来。

问船期时，第 6 步改成：主 Agent 用 `task` 把任务交给「船期专家」。专家读 `skills/sofreight-sailing-schedule/SKILL.md`，再调用 `run_skill`。这一步仍然只有一张图、一个 URL。

## 前端两处绑定

**绑定聊天窗。** 在 `App.jsx` 里把 `CopilotChat` 放进右侧栏，外面仍是 `<CopilotKit>`。栏宽和颜色在 `page.css`。文案用 `labels`。工具调用的卡片是 `useDefaultRenderTool`，也在 `App.jsx`。

**绑定页面上的按钮和表格。** 在 `pageTools.jsx` 里 `useFrontendTool`。例如 `name: "open_customer"`，`handler` 调用 `pageState.jsx` 里的 `openCustomer`。表格在 `PageBoard.jsx`。数据在 `pageData.js`。

这四个文件必须渲染在 `<CopilotKit>` 里面。`PageTools` 在 `App.jsx` 中已经放在里面。用户发消息时，这三个工具的名字和参数说明会跟消息一起走第 4 步，进入同一次 `POST /ag-ui`。`CopilotKitMiddleware()` 让主 Agent 能调用它们。Python 源码里没有 `def open_customer`。

换一个业务系统时，那个系统自己写自己的 `useFrontendTool`。主 Agent 提示词不写死函数名，只要求：要改页面或解释屏幕时，必须调用这次请求里说明相符的前端工具。

官方字段说明见 <https://docs.copilotkit.ai/reference/v2/hooks/useFrontendTool>。本仓库 README 的「页面控制」一节按 1.77.1 列了每个字段。

## 从 0 到 1 实际写过的步骤

1. 用 Deep Agents 的 `create_deep_agent` 做出主 Agent，并用 `subagents` 挂上三个专家。检查点用 `AsyncSqliteSaver`，因为这条链路是异步的。
2. 用 FastAPI 的 `add_langgraph_fastapi_endpoint` 把这张图挂到路径 `/ag-ui`，进程听 `9001`。至此只有后端，浏览器还打不开聊天。
3. 新建 React 工程 `copilotkit-frontend`，安装 `@copilotkit/react-core`、`@copilotkit/react-ui`、`@copilotkit/runtime`，版本都是 1.77.1。
4. 写 `runtime.js`：`CopilotRuntime` 的 `agents` 里用 `HttpAgent` 指向 `http://127.0.0.1:9001/ag-ui`。至少要有键 `default`。Runtime 自己听 `9002`，`basePath` 设为 `/api/copilotkit`。
5. 在 `vite.config.js` 把页面端口定为 `5177`，并把 `/api/copilotkit` 代理到 `9002`。`npm run dev` 时顺便启动 `runtime.js`。
6. 在 `App.jsx` 写 `<CopilotKit runtimeUrl="/api/copilotkit">`，里面放右侧的 `<CopilotChat>`。
7. 需要模型改表格时，再加 `pageData.js`、`pageState.jsx`、`pageTools.jsx`、`PageBoard.jsx`，并用 `useFrontendTool` 登记。

先启动 `logistics_agent.py`，看到 `Uvicorn running on http://0.0.0.0:9001`，再在 `copilotkit-frontend` 执行 `npm run dev`。打开 `http://localhost:5177/`，发「你好」。有流式回复，就说明页面、Runtime、Python 三截都接上了。

## 常见误解

- 「前端有三个 Agent 要选。」没有。前端只选连接名 `default`。三个专家在一张图内部。
- 「浏览器应该请求 `http://127.0.0.1:9001/ag-ui`。」不应该。浏览器请求 `/api/copilotkit`，由 Runtime 去请求那个地址。
- 「`/ag-ui/info` 是后端健康检查。」不是。探活是 Runtime 的 `GET /api/copilotkit/info`。`/ag-ui` 只接收一次对话运行。
