const stripeSecretKey = process.env.STRIPE_SECRET_KEY;
const agaPrice = process.env.AGA_PRICE || '1480';
const consultPrice = process.env.CONSULT_PRICE || '3000';

if (!stripeSecretKey) {
  console.error('STRIPE_SECRET_KEY is not set');
  process.exit(1);
}

async function createProduct(name, description) {
  const params = new URLSearchParams();
  params.append('name', name);
  if (description) params.append('description', description);
  const res = await fetch('https://api.stripe.com/v1/products', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${stripeSecretKey}`,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: params.toString(),
  });
  return await res.json();
}

async function createPrice(unitAmount, productId) {
  const params = new URLSearchParams();
  params.append('unit_amount', unitAmount);
  params.append('currency', 'jpy');
  params.append('product', productId);
  const res = await fetch('https://api.stripe.com/v1/prices', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${stripeSecretKey}`,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: params.toString(),
  });
  return await res.json();
}

async function createPaymentLink(priceId) {
  const params = new URLSearchParams();
  params.append('line_items[0][price]', priceId);
  params.append('line_items[0][quantity]', '1');
  const res = await fetch('https://api.stripe.com/v1/payment_links', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${stripeSecretKey}`,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: params.toString(),
  });
  return await res.json();
}

async function main() {
  try {
    const agaProduct = await createProduct('AGA完全ロードマップ', '薄毛改善のための完全ガイド');
    const agaPriceObj = await createPrice(agaPrice, agaProduct.id);
    const agaLinkObj = await createPaymentLink(agaPriceObj.id);
    console.log('AGA payment link:', agaLinkObj.url);

    const consultProduct = await createProduct('初回相談デポジット', '初回相談の予約金');
    const consultPriceObj = await createPrice(consultPrice, consultProduct.id);
    const consultLinkObj = await createPaymentLink(consultPriceObj.id);
    console.log('Consultation deposit link:', consultLinkObj.url);
  } catch (err) {
    console.error(err);
    process.exit(1);
  }
}

main();
