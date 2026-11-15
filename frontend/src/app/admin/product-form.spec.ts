import { describe, expect, it } from 'vitest';
import { emptyProductDraft, priceToCents, productRequest } from './product-form';

describe('Product form', () => {
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
});
