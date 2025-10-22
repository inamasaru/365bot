const Stripe = require('stripe');
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: '2023-10-16' });

const THANKS_URL = process.env.THANKS_URL; // e.g. https://<your-worker-url>/thanks
const AGA_PRICE = parseInt(process.env.AGA_PRICE || '1480', 10);
const CONSULT_PRICE = parseInt(process.env.CONSULT_PRICE || '3000', 10);

async function upsertProductAndPrice({ name, sku, unitAmountJpy }) {
  // Search (metadata.sku ensures uniqueness)
  let product;
  const search = await stripe.products.search({ query: `active:'true' AND metadata['sku']:'${sku}'` }).catch(() => ({ data: [] }));
  if (search.data && search.data.length) {
    product = search.data[0];
  } else {
    product = await stripe.products.create({ name, metadata: { sku } });
  }

  // Find existing price with same unit amount
  const prices = await stripe.prices.list({ product: product.id, active: true, limit: 50 });
  let price = prices.data.find(p => p.currency === 'jpy' && p.unit_amount === unitAmountJpy && !p.recurring);
  if (!price) {
    price = await stripe.prices.create({
      currency: 'jpy',
      unit_amount: unitAmountJpy,
      product: product.id
    });
  }

  // Payment link with redirect
  const link = await stripe.paymentLinks.create({
    line_items: [{ price: price.id, quantity: 1 }],
    after_completion: {
      type: 'redirect',
      redirect: { url: `${THANKS_URL}?session_id={CHECKOUT_SESSION_ID}&sku=${encodeURIComponent(sku)}` }
    },
    metadata: { sku }
  });

  return { product, price, link };
}

(async () => {
  const aga = await upsertProductAndPrice({ name: 'AGA完全ロードマップ PDF', sku: 'AGA_PDF', unitAmountJpy: AGA_PRICE });
  const consult = await upsertProductAndPrice({ name: 'AGAオンライン相談デポジット', sku: 'CONSULT_DEPOSIT', unitAmountJpy: CONSULT_PRICE });

  console.log('PAYMENT_LINKS:');
  console.log(`AGA_PDF=${aga.link.url}`);
  console.log(`CONSULT_DEPOSIT=${consult.link.url}`);
})().catch(e => {
  console.error(e);
  process.exit(1);
});
