import { CUSTOMERS } from "./pageData";
import { usePage } from "./pageState";

// 这块区域给人看。模型不读 DOM，它只看三个登记函数的返回值。
export function PageBoard() {
  const page = usePage();

  return (
    <main className="board">
      <section className="panel">
        <h2>客户列表</h2>
        <table>
          <thead>
            <tr>
              <th>id</th>
              <th>名称</th>
              <th>等级</th>
            </tr>
          </thead>
          <tbody>
            {CUSTOMERS.map((customer) => (
              <tr
                key={customer.id}
                className={customer.id === page.customerId ? "selected" : ""}
                onClick={() => page.openCustomer(customer.id)}
              >
                <td>{customer.id}</td>
                <td>{customer.name}</td>
                <td>{customer.level}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <h2>客户详情</h2>
        {page.customerId ? (
          <dl>
            <dt>id</dt>
            <dd>{page.customerId}</dd>
            <dt>名称</dt>
            <dd>{page.customerName}</dd>
            <dt>等级</dt>
            <dd>{page.level}</dd>
            <dt>联系人</dt>
            <dd>{page.contact}</dd>
          </dl>
        ) : (
          <p>未选择客户</p>
        )}
      </section>

      <section className="panel orders">
        <h2>订单表</h2>
        <label>
          日期范围
          <select
            value={page.days === null ? "all" : String(page.days)}
            onChange={(event) => {
              const value = event.target.value;
              if (value === "all") {
                page.setAllDates();
                return;
              }
              page.setDateRange(Number(value));
            }}
          >
            <option value="all">全部</option>
            <option value="7">近7天</option>
            <option value="30">近30天</option>
          </select>
        </label>
        {page.customerId ? (
          <table>
            <thead>
              <tr>
                <th>票号</th>
                <th>开航日</th>
                <th>航线</th>
                <th>状态</th>
                <th>异常原因</th>
              </tr>
            </thead>
            <tbody>
              {page.orders.map((order) => (
                <tr key={order.orderNo}>
                  <td>{order.orderNo}</td>
                  <td>{order.sailingDate}</td>
                  <td>{order.route}</td>
                  <td>{order.status}</td>
                  <td>{order.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>请先选择客户</p>
        )}
      </section>

      <section className="panel">
        <h2>异常摘要</h2>
        {page.abnormalOrders.length === 0 ? (
          <p>当前筛选下无异常票</p>
        ) : (
          <ul>
            {page.abnormalOrders.map((order) => (
              <li key={order.orderNo}>
                {order.orderNo}：{order.reason}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
