import { Client as NotionClient } from "@notionhq/client";

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response("", { headers: cors() });
    if (req.method !== "POST") {
      return new Response(JSON.stringify({ ok: true, ping: "alive" }), { headers: cors() });
    }

    try {
      const body = await req.json();
      const {
        name = "",
        email = "",
        phone = "",
        product_code = "aga_guide",
        notes = "",
        external_id = crypto.randomUUID(),
      } = body;

      // 1) Notion 登録
      const notion = new NotionClient({ auth: env.NOTION_TOKEN });
      await notion.pages.create({
        parent: { database_id: env.NOTION_DB_ID },
        properties: {
          "名前": { title: [{ text: { content: name || "(no name)" } }] },
          "External_ID": { rich_text: [{ text: { content: String(external_id) } }] },
          "Email": { email },
          "Phone": { phone },
          "Product": { rich_text: [{ text: { content: product_code } }] },
          "Price": { number: product_code === "consult_deposit" ? 3000 : 1480 },
          "CVR": { number: product_code === "consult_deposit" ? 0.12 : 0.05 },
          "Status": { select: { name: "New" } },
          "Payment_Status": { select: { name: "Pending" } },
          "Contacted": { checkbox: false },
          "Notes": { rich_text: [{ text: { content: notes } }] },
        },
      });

      // 2) 支払いリンク
      const paymentLink =
        product_code === "consult_deposit"
          ? env.PAYLINK_CONSULT
          : env.PAYLINK_AGA_GUIDE;

      // 3) LINE通知
      const msg = [
        "【新規リード】",
        `名前: ${name}`,
        `Email: ${email}`,
        `Phone: ${phone}`,
        `商品: ${product_code}`,
        paymentLink ? `支払いリンク: ${paymentLink}` : ""
      ]
        .filter(Boolean)
        .join("\n");

      await fetch("https://api.line.me/v2/bot/message/push", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${env.LINE_CHANNEL_ACCESS_TOKEN}`,
        },
        body: JSON.stringify({
          to: env.LINE_ADMIN_USER_ID,
          messages: [{ type: "text", text: msg }],
        }),
      });

      return json({ ok: true, checkout_url: paymentLink });
    } catch (err) {
      return json({ ok: false, error: String(err?.message || err) }, 500);
    }
  },
};

function cors() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "content-type, authorization",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
  };
}
function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...cors() },
  });
}
