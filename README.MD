# 物流助手学习仓库

这份说明给第一次接触本仓库的同事。目标是：自己把环境装好，把页面上的一句话送到 Python 里的 Agent，再看懂这条链路为什么要拆成三截。

先看代码，再看学问。概念和绑定关系以 [learn.md](learn.md) 为准。不要从 `BASE.MD` 或 `base2.md` 学，那两份是旧笔记，端口和接法已经过时。

## 你将得到什么

页面右侧嵌入聊天栏。你输入「你好」，模型会回复。你问船期、货踪或运价，主 Agent 把问题交给对应专家，专家再按技能夹里的 `SKILL.md` 去跑脚本。调用了哪个工具，会显示在这条回复下面。

聊天窗的外观是组件库自带的，不是手写的页面。我们自己写的是：中间两行标题，以及「消息交给谁」。

## 先记住这张图

浏览器不能直接调用 Python 的 `/ag-ui`。中间有一个 Node 程序，叫 Copilot Runtime。

```text
你在浏览器打开 http://localhost:5177
        |
        |  App.jsx 写的是 runtimeUrl="/api/copilotkit"
        v
Vite 开发服务器（5177）
  把以 /api/copilotkit 开头的请求，转到 127.0.0.1:9002
        |
        v
runtime.js（9002）
  页面刚打开：回答 GET /api/copilotkit/info
  你按下发送：把消息转成 POST http://127.0.0.1:9001/ag-ui
        |
        v
logistics_agent.py（9001）
  主 Agent 决定自己答，还是交给船期 / 货踪 / 运价专家
  专家通过 run_skill 运行 skills 目录里的脚本
```

三个端口：

| 程序 | 端口 | 你怎么启动 |
| --- | --- | --- |
| Python Agent | 9001 | 仓库根目录运行 `logistics_agent.py` |
| Copilot Runtime | 9002 | 不用单独开。`npm run dev` 会拉起 `runtime.js` |
| 网页 | 5177 | 在 `copilotkit-frontend` 里执行 `npm run dev` |

顺序固定：先看到 9001 的启动成功，再开前端。Runtime 连接的是 `127.0.0.1:9001`。Python 没起来时，页面上会显示 `fetch failed`。

## 1. 安装环境

需要三样已经装在电脑上的工具：

- Python 3.13 或更高。`pyproject.toml` 写了 `requires-python = ">=3.13"`。
- [uv](https://docs.astral.sh/uv/)。用来按 `uv.lock` 安装 Python 依赖。
- Node.js 20 或更高，自带 `npm`。用来跑前端和 Runtime。

在仓库根目录 `V2-test` 执行：

```text
uv sync
```

这会按 `uv.lock` 创建 `.venv`，并装上代码里会 import 的包。和启动直接相关的是：`deepagents`、`copilotkit`、`ag-ui-langgraph`、`langchain-openai`、`python-dotenv`、`fastapi`、`uvicorn`、`langgraph-checkpoint-sqlite`、`aiosqlite`。会话库用的就是最后两个，已经写在 `pyproject.toml` 里，`uv sync` 会一起装上，不用再补一条安装命令。

前端依赖装一次即可：

```text
cd copilotkit-frontend
npm install
```

`package.json` 里已经写了这三个包，版本都是 1.77.1：

- `@copilotkit/react-core`：提供 `<CopilotKit>` 和右侧用的 `<CopilotChat>`。
- `@copilotkit/react-ui`：还装着弹窗组件。当前页面没有用它。
- `@copilotkit/runtime`：提供 `runtime.js` 用的服务端。

不要把它们改成 `@2`。那不是本仓库安装到的版本。

## 2. 准备密钥

在仓库根目录放 `.env`。程序只读取下面三个名字，值换成你自己的：

```text
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
```

`logistics_agent.py` 开头用它们创建 `ChatOpenAI`。没有这三个，模型调用会失败。

查船期、货踪、运价时，技能脚本还要搜航的 Key，名字是 `SOF_API_KEY`。只问「你好」时用不到。

`.env` 里如果还有数据库地址，当前这份 `logistics_agent.py` 不会读它。对话写在运行后生成的 `logistics_sessions.db`。

不要把填了密钥的 `.env` 提交到 git，也不要贴到聊天里。每位同事用自己的 Key。

## 打包给同事时带什么

不要把安装出来的依赖目录打进压缩包。那些文件又大，又和对方的系统绑在一起。对方按上面的 `uv sync` 和 `npm install` 自己生成。

不要打进去：

- `node_modules`（在 `copilotkit-frontend` 里）
- `.venv`
- `__pycache__`、`.pyc`
- `.env`（里面是密钥）
- `logistics_sessions.db`（本机对话记录）
- `copilotkit-frontend/dist`

必须打进去，否则对方装出来的版本会对不上：

- `pyproject.toml` 和 `uv.lock`
- `copilotkit-frontend/package.json` 和 `copilotkit-frontend/package-lock.json`
- `logistics_agent.py`、`runtime.js`、`vite.config.js`、`src/`、`skills/`

对方解压后，在根目录 `uv sync`，再进入 `copilotkit-frontend` 执行 `npm install`。这两步会按锁文件把上面列出的包装齐。

## 3. 启动，并确认第一次成功

开两个终端，都先进入仓库。

终端 A，根目录：

```text
.venv\Scripts\python.exe logistics_agent.py
```

等到这一行：

```text
Uvicorn running on http://0.0.0.0:9001
```

这个脚本启动前会检查 9001。端口上如果已有旧进程，它会把那个进程关掉再听端口。所以不要同时开两份后端。

终端 B：

```text
cd copilotkit-frontend
npm run dev
```

要同时看到两类输出：

- Vite：`Local: http://localhost:5177/`
- Runtime：`Copilot Runtime listening at http://127.0.0.1:9002/api/copilotkit`

浏览器打开 `http://localhost:5177/`。左侧是业务页，右侧是嵌入的聊天栏。输入「你好」并发送。

成功的样子：

- 回复是逐段出现的，不是整段突然冒出来。
- 浏览器里没有 `422`，也没有 `Agent default not found`。
- 终端 A 出现这次请求的访问日志。

「你好」不会去查船期。主 Agent 直接回答。这一步只证明三截链路是通的。

然后再发一句真正的业务问题，例如上海到洛杉矶的船期。这时专家才会去读 `skills/sofreight-sailing-schedule/SKILL.md`，并调用 `run_skill`。缺 `SOF_API_KEY` 时，技能脚本会停下来让你配置，这是技能规则，不是页面断了。

## 4. 页面上要填的只有这一处

打开 `copilotkit-frontend/src/App.jsx`。和后端有关的只有：

```jsx
<CopilotKit runtimeUrl="/api/copilotkit" agentId="logistics_assistant">
  <CopilotChat />
</CopilotKit>
```

`runtimeUrl="/api/copilotkit"` 是网页上的路径，不是 Python 地址。浏览器实际请求的是 `http://localhost:5177/api/copilotkit/...`。

`vite.config.js` 里有：

```js
proxy: {
  "/api/copilotkit": "http://127.0.0.1:9002",
}
```

所以这条请求被转到 Runtime。Python 的地址写在 `runtime.js`：

```js
const agentUrl = "http://127.0.0.1:9001/ag-ui";
```

三处不要混：

| 写在哪 | 写什么 | 错误写法 |
| --- | --- | --- |
| `App.jsx` 的 `runtimeUrl` | `/api/copilotkit` | `http://localhost:9001/ag-ui` |
| `vite.config.js` 的 proxy | `http://127.0.0.1:9002` | 指向 9001 |
| `runtime.js` 的 `agentUrl` | `http://127.0.0.1:9001/ag-ui` | 写成 `/info` |

## 5. `/info` 和 `/ag-ui` 各是什么

页面刚打开，CopilotKit 先问 Runtime：「你这里登记了哪些 Agent？」

```text
GET http://localhost:5177/api/copilotkit/info
```

Runtime 读 `runtime.js` 里的 `agents`，返回 JSON，里面有 `default` 和 `logistics_assistant`。这一步不调用模型，也不进入 `logistics_agent.py`。

你按下发送之后，Runtime 才请求：

```text
POST http://127.0.0.1:9001/ag-ui
```

正文是 AG-UI 规定的 `RunAgentInput`。至少要有：

- `threadId`：这段对话的编号。相同编号会接上 `logistics_sessions.db` 里的历史。
- `runId`：这一次点击发送的编号。
- `messages`：到目前为止的消息。

Python 用 SSE 把事件流回来，例如 `RUN_STARTED`、模型输出的文字、工具调用。Runtime 再交给页面画出来。

因此：

- `/api/copilotkit/info` 是页面问 Runtime。
- `/ag-ui` 是 Runtime 请 Python 跑一轮。

`logistics_agent.py` 里不需要、也没有 `/ag-ui/info`。那个路径不是这个 FastAPI 的职责。

## 6. 右侧聊天栏怎么改

聊天栏在 `copilotkit-frontend/src/App.jsx`，用 `@copilotkit/react-core/v2` 的 `CopilotChat` 嵌在页面右侧，不是右下角弹窗。拖标题左侧的竖条可以改宽度，松手后记在浏览器里。颜色在 `src/page.css` 的 `.chat-dock`。

文案用 `labels`：

```jsx
<CopilotChat
  labels={{
    modalHeaderTitle: "物流助手",
    welcomeMessageText: "可以问船期、货踪或运价。",
    chatInputPlaceholder: "输入消息",
  }}
/>
```

模型若把思考过程发回来，聊天里会出现「思考过程」。调用了哪个函数，由同文件的 `ToolTrace` 画出来。它用 `useDefaultRenderTool`，只改前端展示，不改 Python。

外面的 `<CopilotKit runtimeUrl=...>` 不要动。

## 页面控制：前端怎么把自己的函数登记给模型

客户列表和订单表在浏览器里。Python 没有「打开华运」这种接口。模型要改页面，调用的是前端用 `useFrontendTool` 登记的函数。登记代码在 `copilotkit-frontend/src/pageTools.jsx`。

官方说明（本仓库用的是 v2，参数用 Zod，不要看 v1 那种参数数组）：

- 概念：[Frontend Tools](https://docs.copilotkit.ai/frontend-tools)
- 字段和示例：[useFrontendTool（v2）](https://docs.copilotkit.ai/reference/v2/hooks/useFrontendTool)
- 和别的 hook 怎么选：[Which Hook for Which Job](https://docs.copilotkit.ai/concepts/which-hook)

本仓库安装的是 `@copilotkit/react-core@1.77.1`。下面字段以这个版本的类型为准。官方页面若和类型不一致，以 `node_modules/@copilotkit/core` 里的 `FrontendTool` 为准。

### 名词

| 名词 | 意思 |
| --- | --- |
| 前端工具 | 在浏览器里执行的函数。模型只看见名字、说明和参数，执行发生在用户当前这个页面。 |
| `useFrontendTool` | 登记一个前端工具的 React hook。组件挂上时登记，卸下时取消。它没有返回值。 |
| `name` | 模型用来点名的函数名。同一次页面里每个名字只能有一个。 |
| `description` | 告诉模型什么时候该调用。模型靠这段话做选择，不是靠函数名猜。 |
| `parameters` | 参数的形状。v2 用 Zod（一种 Standard Schema）。每个字段再写 `.describe()`，那句话也会给模型看。 |
| `handler` | 模型决定调用之后，在浏览器里跑的异步函数。参数就是模型填的那一份。返回值会回到模型，供它写下一句。 |
| 工具清单 | 当前页面登记的全部前端工具。用户每次发消息，CopilotKit 把清单放进请求，Runtime 再放进 `POST /ag-ui`。 |
| `CopilotKitMiddleware` | Python 里的中间件。它不定义这些函数，只让当次请求带来的清单变成主 Agent 可以调用的工具。 |

`run_skill` 是后端工具：脚本在服务器上跑。`open_customer` 是前端工具：表格在浏览器里改。不要在 Python 里再写一个同名的 `open_customer`。

### 一次调用怎么走完

1. `PageTools` 渲染在 `<CopilotKit>` 里面，三个 `useFrontendTool` 完成登记。写在外面则这次请求里没有这些函数，模型只会用文字说「已经打开」。
2. 用户发送「打开华运，看近 30 天异常」。
3. 浏览器把消息和工具清单发给 `/api/copilotkit`，Runtime 转发到 `9001/ag-ui`。
4. 主 Agent 读到清单，也读到 `logistics_agent.py` 里的系统提示。系统提示规定必须按顺序调用，不能只在聊天里声称已经打开。
5. 模型发出 `open_customer`。Runtime 把这次调用送回浏览器，`handler` 执行 `page.openCustomer("C001")`，表格更新。
6. `handler` 的返回值回到模型。模型再调用 `set_date_range`，然后 `get_screen_context`。
7. 模型只用 `get_screen_context` 返回的票号和原因写回复。

主 Agent 的系统提示不写 `open_customer` 这种名字。换一个业务系统时，页面会登记另一套函数，Python 不用跟着改。模型每次从请求里的工具清单看到名字和 `description`。提示词只规定：要改页面或解释屏幕时，必须调用说明相符的前端工具，不许口头说已经完成。华运对应 `C001` 写在 `pageTools.jsx` 的 `description` 里。

### 登记时可以写的字段

调用形式：

```ts
useFrontendTool(tool, deps?)
```

`deps` 和 `useEffect` 的依赖数组一样。handler 用到的状态变了、需要重新登记时才传。本仓库的三个工具不传，因为它们通过 `usePage()` 读到的是最新状态。

`tool` 对象：

| 字段 | 必填 | 模型能否看见 | 做什么 |
| --- | --- | --- | --- |
| `name` | 是 | 能 | 工具名。用小写加下划线，例如 `open_customer`。不要和 `run_skill` 重名。 |
| `description` | 建议必填 | 能 | 何时调用、调用后页面会怎样、不该调用的情况。 |
| `parameters` | 无参数可省略 | 能 | Zod 对象。字段名就是模型要填的参数名。 |
| `handler` | 要执行就必填 | 不能看见函数体 | `async (args, context) => 返回值`。返回值请用普通对象或字符串，方便序列化。 |
| `render` | 否 | 不能 | 在聊天里画这次调用的过程。不写就用弹窗默认样式。 |
| `followUp` | 否 | 不能 | 不写或 `true`：返回值回到模型，模型继续说。`false`：执行完不再要求模型接话。 |
| `agentId` | 否 | 不能 | 只让这个 id 的 Agent 使用。不写则当前对话能看见。 |
| `available` | 否 | 不能 | 本仓库类型是布尔值，默认 `true`。`false` 表示先留着登记，但不给模型调用。 |
| `reconnectBehavior` | 否 | 不能 | 刷新页面后，上次没跑完的调用要不要再跑一遍 handler。默认 `"passive"`：只显示，不重跑。`"resume-pending"` 会再跑，只用于重复执行也安全的操作。 |
| `type` | 否 | 不能 | 不写就是普通前端工具。`"human-in-the-loop"` 表示先等用户确认。本仓库的三个工具都不写。 |
| `webmcp` | 否 | 不能 | 额外暴露给浏览器自己的智能体。本仓库不需要。 |

`handler` 的第二个参数 `context` 一般不用。里面有：

- `toolCall`：这次调用的 id 和参数。
- `agent`：发出调用的 Agent。不是浏览器智能体调用时才有。
- `signal`：用户停止生成时会中止。请求自己的接口时可以传给 `fetch`。
- `isReplay`：只有按上面的 `"resume-pending"` 重放时才是 `true`。

`render` 收到的状态是三种：`InProgress`（参数还在往外冒）、`Executing`（handler 正在跑）、`Complete`（已有 `result` 字符串）。要从 `@copilotkit/core` 引入 `ToolCallStatus` 来比较。本仓库没写 `render`。

Zod 里模型能看见的是对象形状和 `.describe()` 的文字。本仓库的写法：

```jsx
parameters: z.object({
  customer_id: z.enum(["C001", "C002", "C003"]).describe("客户 id。华运 C001，远达 C002，海联 C003。"),
}),
```

没有参数时写 `z.object({})`，例如 `get_screen_context`。不要省略成「模型自己看 DOM」。

### 本仓库的三个工具

| name | 何时调用 | handler 做的事 | 返回给模型的内容 |
| --- | --- | --- | --- |
| `open_customer` | 用户要打开华运、远达或海联 | 选中客户，日期改回全部 | `customer_id`、`customer_name`、当前可见票号。未知客户返回 `{ error: "unknown_customer" }` |
| `set_date_range` | 用户要近 7 天或近 30 天 | 只改筛选，不换客户 | 可见票号和其中的异常票号。还没选客户返回 `{ error: "no_customer" }` |
| `get_screen_context` | 要解释屏幕上的异常之前 | 不改页面，只读当前状态 | 客户、`days`（`null` 表示全部）、可见订单的票号、航线、状态、原因 |

页面上的点击和日期下拉走的是同一套 `pageState.jsx`。人和模型改的是同一块状态。

系统提示规定的顺序是：`open_customer`（华运为 `C001`）→ `set_date_range`（近 30 天为 `30`）→ `get_screen_context`。回复只引用最后一步返回的票号和原因。

### 业务页自己加一个工具

1. 在已有的页面状态或请求封装上写一个函数。不要在 handler 里新造一套数据。
2. 在 `<CopilotKit>` 内的组件里调用 `useFrontendTool`。`name` 用业务动词，`description` 写清触发条件，`parameters` 用 Zod 把每个字段说明白。
3. `handler` 调用第 1 步的函数，返回模型下一步需要的字段。不要返回整页 HTML，也不要把 Java 的 URL、令牌交给模型。
4. `description` 写清何时必须调用、参数怎么填。框架提示词不会出现你们的函数名。若模型只用文字说已经完成，把「必须调用、不能口头完成」写进这条工具的 `description`，不要去改 Python 里的客户编号。
5. 刷新页面，发一句应该触发它的话。表格或按钮要先变，聊天里的数字再和返回值一致。

验收本仓库：对弹窗说「打开华运，看近 30 天异常」。客户列表应选中华运，订单表只剩近 30 天，异常摘要出现 HY2402、HY2403。聊天里的票号必须和摘要一致。

## 7. 后端代码按什么顺序读

打开根目录 `logistics_agent.py`，从上往下是五块。

**模型。** 读取 `.env`，创建 `ChatOpenAI`。后面的主 Agent 和专家都用这一个模型。

**`run_skill`。** 唯一允许执行技能脚本的入口。参数是：

- `skill_name`：`skills` 下面的文件夹名，例如 `sofreight-sailing-schedule`。
- `script_name`：该文件夹 `scripts` 里的文件名，例如 `schedule.py`。
- `command_args`：按空格切开后交给脚本，例如 `--pol 上海 --dest 洛杉矶`。

没有技能别名表。新技能是把整夹放进 `skills/`。名字里不能带 `../` 或斜杠，参数里不能带 `; | &` 这类符号，避免被拼成一条系统命令。

**文件系统。** `CompositeBackend` 把虚拟路径 `/skills/` 对到磁盘上的 `./skills`，其它路径对到 `./workspace`。`permissions` 只写了一条：禁止写入 `/skills/**`。没被规则点名的路径默认允许写，所以工作目录可以落临时文件。不要再写一条「允许 `/work/**`」：默认根已经是 `workspace`，模型看到的路径是 `/文件名`，不是 `/work/文件名`。

**三个专家。** 每个是一个字典：`name`、`description`、`system_prompt`、`tools`、`skills`。主 Agent 靠 `description` 决定把问题交给谁。`description` 要写清「什么问题来找我」。

`skills=["/skills/"]` 写在专家身上，不写在主 Agent 身上。原因：这种子 Agent 是 isolated 的，不会继承主 Agent 上的 `skills` 参数。写在主 Agent 上，技能清单会进调度提示，主 Agent 就会自己去读脚本。专家仍然共用主 Agent 传下来的那份文件系统，所以它们读到的 `/skills/...` 是同一批夹。

**主程序。** `async with AsyncSqliteSaver.from_conn_string("logistics_sessions.db")` 包住建图和启动。这个函数是异步上下文管理器，不能写成普通赋值，否则拿到的是生成器，检查点类型不对。同步版 `SqliteSaver` 也不可用：AG-UI 会调用异步的 `aget_tuple`，同步实现会抛 `NotImplementedError`。

`create_deep_agent` 之后，`add_langgraph_fastapi_endpoint(..., path="/ag-ui")` 把编好的图挂出去。`LangGraphAGUIAgent` 从 `copilotkit` 导入。`config={"recursion_limit": 200}` 是因为读一份 `SKILL.md` 再跑脚本，步数很容易超过 LangGraph 默认的 25。

## 8. 前端三个文件按什么顺序读

1. `copilotkit-frontend/src/App.jsx`：页面上放什么，`runtimeUrl` 填什么。
2. `copilotkit-frontend/runtime.js`：向页面公布哪些 Agent 名字，以及这些名字背后的 Python 地址。
3. `copilotkit-frontend/vite.config.js`：5177 和「把 `/api/copilotkit` 转到 9002」。

`runtime.js` 里有两个键，值都是 `9001/ag-ui`：

- `logistics_assistant`：和 `App.jsx` 的 `agentId` 一致。右侧 `CopilotChat` 走这扇门。
- `default`：组件没拿到 agentId 时的后备名字。

只登记后者时，有的请求仍找 `default`，页面报 `Agent 'default' not found`。两个键都留着。

两个键各 `new HttpAgent` 一次。共用同一个对象时，两路对话会抢一份请求状态。

## 9. 建议的学习顺序

每一项都改很小，并看到现象，再进下一项。

1. 按第 3 节跑通「你好」。先不要改代码。
2. 在 `App.jsx` 里用 `labels.title` 把弹窗标题改成你的名字，保存。页面会热更新，标题变了，但不用重启 Python。
3. 停掉终端 A。再发一句。页面应出现 `fetch failed`。看终端 B，Runtime 会写 `ECONNREFUSED 127.0.0.1:9001`。然后重新启动 Python，再发一句，恢复。
4. 打开 `logistics_agent.py` 里主 Agent 的 `system_prompt`，加一句「回答开头先说：学习笔记」。重启 Python。再发「你好」，回复里应出现这句。这证明改的是 9001，不是弹窗。
5. 读 `skills/sofreight-sailing-schedule/SKILL.md` 的前半，尤其是铁律和命令示例。再在页面上问一句船期，对照专家提示里写的 `skill_name` 和 `script_name`。
6. 最后看 `runtime.js` 的 `agents`。暂时删掉 `default` 那个键并重启前端，刷新页面，你会看到 `Agent default not found`。看完把键加回去。这个错误是登记名和弹窗查找名不一致，不是模型坏了。

## 10. 改完要重启谁

| 你改了 | 重启 |
| --- | --- |
| `logistics_agent.py`、`.env`、`skills/` 里的规则 | 只重启 Python |
| `runtime.js`、`vite.config.js` | 重新执行 `npm run dev` |
| `App.jsx` 的文案、弹窗或侧栏 | 一般不用重启，保存后刷新页面 |

Python 重启时会释放 9001 上的旧进程。前端重新执行 `npm run dev` 时，`runtime.js` 会先关掉占用 9002 的上一次 Runtime，再自己监听。若仍看到 `EADDRINUSE`，在该终端按 Ctrl+C 后重新执行 `npm run dev`。页面那一行 `Local: http://localhost:5177/` 表示网页已经起来，后面的报错只说明 Runtime 没听上 9002。

## 11. 报错对照

浏览器插件、`Download the React DevTools`、`Lit is in dev mode` 可以忽略。下面几条才和本仓库有关。

**422，`runtime_info_fetch_failed`。**  
`runtimeUrl` 指到了 `http://localhost:9001/ag-ui`。页面先请求 `GET /ag-ui/info`，Python 没有这个路径，返回 404。页面再 `POST /ag-ui`，正文是 `{"method":"info"}`。`/ag-ui` 要求 `threadId`、`runId`、`messages`，FastAPI 校验失败，返回 422。  
改回 `runtimeUrl="/api/copilotkit"`。不要在 Python 里手写 `/ag-ui/info`，也不要在前端写一个自定义的 `streamAgentMessages`。这版 CopilotKit 不是那样接的。

**`Agent 'default' not found`，并写着 Known agents。**  
`/info` 已经通了。弹窗要的名字不在 Runtime 的登记表里。对照 `runtime.js` 的 `agents`，把 `default` 加回去，然后重启前端。

**`fetch failed`，代码 `INCOMPLETE_STREAM`。**  
看 Runtime 终端。若是 `ECONNREFUSED 127.0.0.1:9001`，就是 Python 没在听 9001。页面和 9002 可以是好的。先启动 `logistics_agent.py`。

**`NotImplementedError`，内容里有 SqliteSaver 或 async。**  
用了同步的检查点。必须是 `AsyncSqliteSaver`，并且放在 `async with` 里。

**回复里让你去配置 API Key，或脚本说缺少 Key。**  
链路是通的。这是技能夹的规则：查业务数据前要有 `SOF_API_KEY`。按该夹 `SKILL.md` 里的说明配置，不要把完整 Key 打进聊天。

## 12. 目录

```text
V2-test/
  README.md                 本说明
  logistics_agent.py        Python：模型、run_skill、三个专家、/ag-ui
  pyproject.toml            Python 依赖
  uv.lock                   依赖锁定
  .env                      本地密钥，不要外发
  logistics_sessions.db     运行后出现的会话库
  skills/
    sofreight-sailing-schedule/   船期，脚本 schedule.py
    sofreight-cargo-tracking/     货踪，脚本 tracking.py
    sofreight-sea-freight-price/  运价，脚本 price.py
  copilotkit-frontend/
    src/App.jsx             把 Runtime、页面状态、登记函数和弹窗套在一起
    src/pageData.js         演示客户和订单，只在浏览器里
    src/pageState.jsx       当前选中的客户和日期，模型改的是这里
    src/pageTools.jsx       useFrontendTool：三个页面函数
    src/PageBoard.jsx       给人看的四块表格
    runtime.js              登记 Agent，转发到 9001/ag-ui
    vite.config.js          5177，以及转到 9002 的代理
```

每个技能夹里，步骤和禁止事项以该夹的 `SKILL.md` 为准。`logistics_agent.py` 只负责找到文件夹和脚本，不把船期规则再抄一份。
