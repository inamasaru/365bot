const { Client } = require('@notionhq/client');
const { Resend } = require('resend');
const dayjs = require('dayjs');

const NOTION_TOKEN = process.env.NOTION_TOKEN;
const NOTION_DATABASE_ID = process.env.NOTION_DATABASE_ID;
const RESEND_API_KEY = process.env.RESEND_API_KEY;
const FROM_EMAIL = process.env.FROM_EMAIL;
const TO_EMAIL = process.env.TO_EMAIL;

const SUBJECT = 'ご登録ありがとうございます';

const makeHtml = (name) => `
  <p>${name || 'お客様'} 様</p>
  <p>お問い合わせありがとうございます。担当より順次ご案内いたします。</p>
  <p>本メールは自動送信（エージェント）です。</p>
`;

function validateEnv() {
  const required = [
    ['NOTION_TOKEN', NOTION_TOKEN],
    ['NOTION_DATABASE_ID', NOTION_DATABASE_ID],
    ['RESEND_API_KEY', RESEND_API_KEY],
    ['FROM_EMAIL', FROM_EMAIL],
    ['TO_EMAIL', TO_EMAIL],
  ];

  const missing = required.filter(([, value]) => !value).map(([key]) => key);

  if (missing.length) {
    throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
  }
}

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
  const recipients = [...new Set([email, TO_EMAIL].filter(Boolean))];

  if (recipients.length === 0) {
    throw new Error('No recipients provided');
  }

  const { error } = await resendClient.emails.send({
    from: FROM_EMAIL,
    to: recipients,
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
  validateEnv();

  const notion = new Client({ auth: NOTION_TOKEN });
  const resend = new Resend(RESEND_API_KEY);

  const pages = await fetchUncontactedPages(notion);
  console.log(`Found ${pages.length} new leads`);

  for (const page of pages) {
    const props = page.properties || {};
    const name = props?.Name?.title?.[0]?.plain_text || '';
    const email = props?.Email?.email || '';

    if (!email) {
      console.log(`Page ${page.id} has no lead email; sending to fallback only.`);
    }

    try {
      await sendEmail(resend, { email, name });
      await markAsContacted(notion, page.id);
      console.log(`Processed page ${page.id} for ${email || 'fallback recipient'}`);
    } catch (error) {
      console.error('Error handling page', page.id, error?.message || error);
    }
  }
}

main()
  .then(() => {
    process.exit(0);
  })
  .catch((error) => {
    console.error('Unhandled error', error?.message || error);
    process.exit(1);
  });
