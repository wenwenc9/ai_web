import { createContext, useContext, useMemo, useRef, useState } from "react";
import { findCustomer, visibleOrders } from "./pageData";

const PageContext = createContext(null);

// 模型改页面，改的就是这份状态。handler 必须读 ref，避免闭包里还是上一次的客户。
export function PageProvider({ children }) {
  const [snapshot, setSnapshot] = useState({ customerId: null, days: null });
  const snapshotRef = useRef(snapshot);
  snapshotRef.current = snapshot;

  const value = useMemo(() => {
    const customer = findCustomer(snapshot.customerId);
    const orders = visibleOrders(snapshot.customerId, snapshot.days);

    function openCustomer(customerId) {
      const next = findCustomer(customerId);
      if (!next) return { error: "unknown_customer" };
      const nextSnapshot = { customerId, days: null };
      snapshotRef.current = nextSnapshot;
      setSnapshot(nextSnapshot);
      const nextOrders = visibleOrders(customerId, null);
      return {
        customer_id: next.id,
        customer_name: next.name,
        visible_order_ids: nextOrders.map((row) => row.orderNo),
      };
    }

    function setDateRange(days) {
      const current = snapshotRef.current;
      if (!current.customerId) return { error: "no_customer" };
      if (days !== 7 && days !== 30) return { error: "invalid_days" };
      const nextSnapshot = { customerId: current.customerId, days };
      snapshotRef.current = nextSnapshot;
      setSnapshot(nextSnapshot);
      const nextOrders = visibleOrders(current.customerId, days);
      return {
        customer_id: current.customerId,
        days,
        visible_order_ids: nextOrders.map((row) => row.orderNo),
        abnormal_order_ids: nextOrders.filter((row) => row.status === "异常").map((row) => row.orderNo),
      };
    }

    function setAllDates() {
      const current = snapshotRef.current;
      if (!current.customerId) return;
      const nextSnapshot = { customerId: current.customerId, days: null };
      snapshotRef.current = nextSnapshot;
      setSnapshot(nextSnapshot);
    }

    function getScreenContext() {
      const current = snapshotRef.current;
      const currentCustomer = findCustomer(current.customerId);
      const currentOrders = visibleOrders(current.customerId, current.days);
      return {
        customer_id: current.customerId,
        customer_name: currentCustomer?.name ?? null,
        days: current.days,
        orders: currentOrders.map((row) => ({
          order_no: row.orderNo,
          route: row.route,
          status: row.status,
          reason: row.reason,
        })),
      };
    }

    return {
      customerId: snapshot.customerId,
      customerName: customer?.name ?? null,
      level: customer?.level ?? null,
      contact: customer?.contact ?? null,
      days: snapshot.days,
      orders,
      abnormalOrders: orders.filter((row) => row.status === "异常"),
      openCustomer,
      setDateRange,
      setAllDates,
      getScreenContext,
    };
  }, [snapshot]);

  return <PageContext.Provider value={value}>{children}</PageContext.Provider>;
}

export function usePage() {
  const value = useContext(PageContext);
  if (!value) throw new Error("usePage 必须放在 PageProvider 里面");
  return value;
}
