import { describe, expect, it } from 'vitest';
import { emptyProductDraft, priceToCents, productRequest, productToDraft, productUpdateRequest, measurement } from './product-form';

describe('Product form', () => {
  it('validates optional garment measurements without rounding and preserves them on update', () => {
    expect(measurement('')).toBeNull(); expect(measurement(undefined)).toBeNull();
    expect(measurement(' 86,5 ')).toBe(86.5); expect(measurement('300')).toBe(300);
    for (const value of ['0', '-2', '300.1', '85.55', '1e2', 'Infinity']) expect(() => measurement(value)).toThrow();
    const product = { id: 7, name: 'Body', slug: 'body-vino', price_cents: 1500, is_active: true,
      variants: [{ id: 23, sku: 'BODY-M', size: 'M', color: 'Vino', price_adjustment_cents: 0, bust_cm: 86.5, waist_cm: null, hip_cm: 98 }] };
    const draft = productToDraft(product);
    expect(draft.variants[0].bust_cm).toBe('86.5');
    expect(productUpdateRequest(draft).variants[0]).toMatchObject({ id: 23, bust_cm: 86.5, waist_cm: null, hip_cm: 98 });
    draft.variants[0].bust_cm = '';
    expect(productUpdateRequest(draft).variants[0].bust_cm).toBeNull();
    expect(product.variants[0].bust_cm).toBe(86.5);
  });
  it('copies editable products without mutating them and retains IDs only for updates', () => {
    const product = { id: 7, name: 'Body', slug: 'body-vino', price_cents: 2147483647, is_active: false,
      image_url: 'https://cdn.example/cover.webp',
      variants: [{ id: 23, sku: 'BODY-M', size: 'M', color: 'Vino', price_adjustment_cents: 0 }],
      images: [{ id: 8, url: 'https://cdn.example/front.webp', alt: 'Vista frontal', color: 'Vino' }] };
    const draft = productToDraft(product);
    expect(draft.price).toBe('21474836.47');
    expect(draft.variants[0].adjustment).toBe('0.00');
    expect(productUpdateRequest(draft).variants[0].id).toBe(23);
    expect(productRequest(draft).variants[0]).not.toHaveProperty('id');
    draft.variants.push({ sku: 'BODY-L', size: 'L', color: 'Vino', adjustment: '0.00' });
    expect(productUpdateRequest(draft).variants[1]).not.toHaveProperty('id');
    draft.variants[0].sku = 'BODY-NEW'; draft.images[0].alt = 'Detalle';
    expect(product.variants[0].sku).toBe('BODY-M'); expect(product.images[0].alt).toBe('Vista frontal');
  });
  it('converts dollars exactly without rounding invalid precision', () => {
    expect(priceToCents('15,29')).toBe(1529);
    expect(priceToCents('0.10')).toBe(10);
    expect(priceToCents('21474836.47')).toBe(2147483647);
    for (const value of ['1.999', '-1', 'NaN', '1e3', '21474836.48']) expect(() => priceToCents(value)).toThrow();
  });
  it('includes all attributes and preserves gallery order and variant prices', () => {
    const draft = { ...emptyProductDraft(), name: ' Body ', slug: 'body-vino', price: '15.00', description: ' Encaje ', is_active: false, coverUrl: 'https://cdn.example/cover.webp',
      variants: [{ sku: 'BODY-M', size: 'M', color: 'Vino', adjustment: '1,50' }],
      images: [{ url: 'https://cdn.example/back.webp', alt: 'Vista posterior', color: 'vino' }, { url: 'https://cdn.example/front.webp', alt: 'Vista frontal', color: 'Vino' }] };
    const request = productRequest(draft);
    expect(request).toMatchObject({ name: 'Body', slug: 'body-vino', description: 'Encaje', price_cents: 1500, is_active: false, image_url: draft.coverUrl });
    expect(request.variants[0].price_adjustment_cents).toBe(150);
    expect(request.images.map((image) => image.url)).toEqual(draft.images.map((image) => image.url));
    expect(request.images[0].color).toBe('Vino');
  });
  it('rejects unfinished uploads, repeated SKUs and mismatched gallery colors', () => {
    const draft = { ...emptyProductDraft(), name: 'Body', slug: 'body-vino', price: '15', variants: [{ sku: 'BODY-M', size: 'M', color: 'Vino', adjustment: '0' }] };
    expect(() => productRequest({ ...draft, images: [{ url: '', alt: 'Foto frontal', color: 'Vino' }] })).toThrow();
    expect(() => productRequest({ ...draft, variants: [...draft.variants, ...draft.variants] })).toThrow();
    expect(() => productRequest({ ...draft, images: [{ url: 'https://example.com/a.webp', alt: 'Foto frontal', color: 'Negro' }] })).toThrow();
  });
  it('sets initial stock and never overwrites existing inventory during a general edit', () => {
    const product = { id: 7, name: 'Body', slug: 'body', price_cents: 1200, is_active: true, stock_quantity: 6,
      variants: [{ id: 9, sku: 'BODY-M', size: 'M', price_adjustment_cents: 0, stock_quantity: 6 }] };
    const draft = productToDraft(product);
    draft.variants.push({ sku: 'BODY-L', size: 'L', color: '', adjustment: '0', stock_quantity: 2 });
    const update = productUpdateRequest(draft);
    expect(update).not.toHaveProperty('stock_quantity');
    expect(update.variants[0]).not.toHaveProperty('stock_quantity');
    expect(update.variants[1].stock_quantity).toBe(2);
    const creation = productRequest({ ...emptyProductDraft(), name: 'Body', slug: 'body', price: '12' });
    expect(creation.stock_quantity).toBe(1);
    expect(() => productRequest({ ...draft, stock_quantity: -1 })).toThrow();
  });

  it('does not validate aggregate or existing stock when saving product details', () => {
    const draft = productToDraft({ id: 7, name: 'Body', slug: 'body', price_cents: 1200, is_active: true,
      stock_quantity: 2 * 2147483647, variants: [
        { id: 1, sku: 'BODY-M', size: 'M', stock_quantity: 2147483647, price_adjustment_cents: 0 },
        { id: 2, sku: 'BODY-L', size: 'L', stock_quantity: 2147483647, price_adjustment_cents: 0 },
      ] });
    draft.name = 'Body actualizado';
    // Incluso un valor obsoleto inválido del editor no participa en este guardado.
    draft.variants[0].stock_quantity = -1;
    const update = productUpdateRequest(draft);
    expect(update.name).toBe('Body actualizado'); expect(update).not.toHaveProperty('stock_quantity');
    expect(update.variants.every(variant => !('stock_quantity' in variant))).toBe(true);
    draft.variants.push({ sku: 'BODY-S', size: 'S', color: '', adjustment: '0', stock_quantity: -1 });
    expect(() => productUpdateRequest(draft)).toThrow();
  });

});
