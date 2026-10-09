// 演示数据只活在浏览器里。Python 没有订单接口，模型不能自己编票号。

export const CUSTOMERS = [
  { id: "C001", name: "华运", level: "A", contact: "王敏" },
  { id: "C002", name: "远达", level: "B", contact: "李强" },
  { id: "C003", name: "海联", level: "A", contact: "陈洁" },
];

// offsetDays 是相对今天的开航日。筛选「近 N 天」时用它，不把写死的日期交给模型。
const ORDERS = [
  { orderNo: "HY2401", customerId: "C001", offsetDays: -3, route: "上海 → 洛杉矶", status: "正常", reason: "" },
  { orderNo: "HY2402", customerId: "C001", offsetDays: -10, route: "上海 → 汉堡", status: "异常", reason: "箱量与订舱不符" },
  { orderNo: "HY2403", customerId: "C001", offsetDays: -20, route: "宁波 → 洛杉矶", status: "异常", reason: "截关时间已过" },
  { orderNo: "HY2404", customerId: "C001", offsetDays: -45, route: "上海 → 新加坡", status: "异常", reason: "费用未确认" },
  { orderNo: "YD2401", customerId: "C002", offsetDays: -5, route: "青岛 → 纽约", status: "正常", reason: "" },
  { orderNo: "YD2402", customerId: "C002", offsetDays: -12, route: "青岛 → 鹿特丹", status: "异常", reason: "舱位被取消" },
  { orderNo: "HL2401", customerId: "C003", offsetDays: -8, route: "深圳 → 洛杉矶", status: "正常", reason: "" },
];

export function findCustomer(customerId) {
  return CUSTOMERS.find((item) => item.id === customerId) ?? null;
}

function formatDate(date) {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export function visibleOrders(customerId, days) {
  if (!customerId) return [];
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return ORDERS.filter((row) => row.customerId === customerId)
    .filter((row) => days === null || row.offsetDays >= -days)
    .map((row) => {
      const sailing = new Date(today);
      sailing.setDate(today.getDate() + row.offsetDays);
      return {
        orderNo: row.orderNo,
        sailingDate: formatDate(sailing),
        route: row.route,
        status: row.status,
        reason: row.reason,
      };
    });
}
