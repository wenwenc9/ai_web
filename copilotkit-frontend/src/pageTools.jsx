import { useFrontendTool } from "@copilotkit/react-core/v2";
import { z } from "zod";
import { usePage } from "./pageState";

// 第 1 步：这些函数只存在于浏览器。Python 里没有同名工具。
// 第 2 步：useFrontendTool 把名字、参数和 handler 登记到当前这次对话。
// 第 3 步：用户发消息时，CopilotKit 把这份清单带给 Runtime，再放进 POST /ag-ui。
// 第 4 步：模型决定调用后，handler 在这台浏览器里执行，返回值再送回模型。
// 组件必须渲染在 <CopilotKit> 里面，否则登记不上。
export function PageTools() {
  const page = usePage();

  useFrontendTool({
    name: "open_customer",
    description: "打开客户并显示该客户全部订单，日期范围重置为全部。用户说「华运」时用 C001，「远达」用 C002，「海联」用 C003。",
    parameters: z.object({
      customer_id: z.enum(["C001", "C002", "C003"]).describe("客户 id。华运 C001，远达 C002，海联 C003。"),
    }),
    handler: async ({ customer_id }) => page.openCustomer(customer_id),
  });

  useFrontendTool({
    name: "set_date_range",
    description: "按开航日筛选当前客户的订单。近 30 天传 30，近 7 天传 7。未选客户时不改页面。",
    parameters: z.object({
      days: z.union([z.literal(7), z.literal(30)]).describe("近 7 天传 7，近 30 天传 30。"),
    }),
    handler: async ({ days }) => page.setDateRange(days),
  });

  useFrontendTool({
    name: "get_screen_context",
    description: "读取当前屏幕上已选客户和订单表可见行。days 为 null 表示全部。不要根据 DOM 猜测。",
    parameters: z.object({}),
    handler: async () => page.getScreenContext(),
  });

  return null;
}
