const { Client } = require('@notionhq/client');
const { Resend } = require('resend');
const dayjs = require('dayjs');

const NOTION_TOKEN = process.env.NOTION_TOKEN;
const NOTION_DB_ID = process.env.NOTION_DB_ID;
const RESEND_API_KEY = process.env.RESEND_API_KEY;
const FROM_EMAIL = process.env.RESEND_FROM || 'onboarding@resend.dev';
const SUBJECT = 'ご登録ありがとうございます';
const makeHtml = (name) => `
  <p>${name || 'お客様'} 様</p>
  <p>お問い合わせありがとうございます。担当より順次ご案内いたします。</p>
  <p>本メールは自動送信（エージェント）です。</p>
`;

(async () => {
  const notion = new Client({ auth: NOTION_TOKEN });
  const resend = new Resend(RESEND_API_KEY);

  const pages = [];
  let cursor = undefined;
  while (true) {
    const resp = await notion.databases.query({
      database_id: NOTION_DB_ID,
      start_cursor: cursor,
      filter: {
        property: 'Contacted',
        checkbox: { equals: false },
      },
      sorts: [{ property: 'Created time', direction: 'ascending' }],
    });
    pages.push(...resp.results);
    if (!resp.has_more) break;
    cursor = resp.next_cursor;
  }

  console.log(`Found ${pages.length} new leads`);

  for (const page of pages) {
    try {
      const props = page.properties;
      const name = props.Name?.title?.[0]?.plain_text || '';
      const email = props.Email?.email || '';
      if (!email) {
        console.log(`Skip page ${page.id} (no email)`);
        continue;
      }

      const { error } = await resend.emails.send({
        from: FROM_EMAIL,
        to: email,
        subject: SUBJECT,
        html: makeHtml(name),
      });
      if (error) throw error;

      console.log(`Sent to ${email}`);
      await notion.pages.update({
        page_id: page.id,
        properties: {
          Contacted: { checkbox: true },
          ContactedAt: { date: { start: dayjs().toISOString() } },
        },
      });
    } catch (e) {
      console.error('Error handling page', page.id, e.message || e);
    }
  }
})();
