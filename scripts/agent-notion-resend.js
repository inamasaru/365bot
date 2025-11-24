const { Client } = require('@notionhq/client');
const { Resend } = require('resend');
const dayjs = require('dayjs');

const NOTION_TOKEN = process.env.NOTION_TOKEN;
const NOTION_DATABASE_ID = process.env.NOTION_DATABASE_ID || process.env.NOTION_DB_ID;
const RESEND_API_KEY = process.env.RESEND_API_KEY;
const FROM_EMAIL = process.env.RESEND_FROM || 'onboarding@resend.dev';
const SUBJECT = 'ご登録ありがとうございます';

const makeHtml = (name) => `
  <p>${name || 'お客様'} 様</p>
  <p>お問い合わせありがとうございます。担当より順次ご案内いたします。</p>
  <p>本メールは自動送信（エージェント）です。</p>
`;

async function fetchUncontactedPages(notionClient) {
  const pages = [];
  let cursor;

  do {
    const response = await notionClient.databases.query({
      database_id: NOTION_DATABASE_ID,
      start_cursor: cursor,
      filter: {
        property: 'Contacted',
        checkbox: { equals: false },
      },
      sorts: [{ property: 'Created time', direction: 'ascending' }],
    });

    pages.push(...response.results);
    cursor = response.has_more ? response.next_cursor : undefined;
  } while (cursor);

  return pages;
}

async function sendEmail(resendClient, { email, name }) {
  const { error } = await resendClient.emails.send({
    from: FROM_EMAIL,
    to: email,
    subject: SUBJECT,
    html: makeHtml(name),
  });

  if (error) {
    throw error;
  }
}

async function markAsContacted(notionClient, pageId) {
  await notionClient.pages.update({
    page_id: pageId,
    properties: {
      Contacted: { checkbox: true },
      ContactedAt: { date: { start: dayjs().toISOString() } },
    },
  });
}

async function main() {
  const missing = [
    ['NOTION_TOKEN', NOTION_TOKEN],
    ['NOTION_DATABASE_ID', NOTION_DATABASE_ID],
    ['RESEND_API_KEY', RESEND_API_KEY],
    ['RESEND_FROM', FROM_EMAIL],
  ]
    .filter(([, value]) => !value)
    .map(([key]) => key);

  if (missing.length) {
    console.error(`Missing required environment variables: ${missing.join(', ')}`);
    process.exit(1);
  }

  const notion = new Client({ auth: NOTION_TOKEN });
  const resend = new Resend(RESEND_API_KEY);

  const pages = await fetchUncontactedPages(notion);
  console.log(`Found ${pages.length} new leads`);

  for (const page of pages) {
    const props = page.properties;
    const name = props?.Name?.title?.[0]?.plain_text || '';
    const email = props?.Email?.email || '';

    if (!email) {
      console.log(`Skip page ${page.id} (no email)`);
      continue;
    }

    try {
      await sendEmail(resend, { email, name });
      await markAsContacted(notion, page.id);
      console.log(`Sent to ${email}`);
    } catch (error) {
      console.error('Error handling page', page.id, error?.message || error);
    }
  }
}

main().catch((error) => {
  console.error('Unhandled error', error?.message || error);
  process.exit(1);
});
