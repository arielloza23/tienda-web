import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CartService, CART_STORAGE_KEY } from './cart.service';
import { Product } from '../models/product.model';

const product: Product = { id: 1, name: 'Body', slug: 'body', price_cents: 1500, is_active: true,
  variants: [{ id: 2, sku: 'BODY-M', size: 'M', color: 'Vino', price_adjustment_cents: 500 }] };

describe('CartService', () => {
  beforeEach(() => { localStorage.clear(); });

  it('restores only identifiers and quantities using fresh catalog prices', () => {
    const cart = new CartService();
    cart.reconcile([product]);
    cart.add(product, product.variants[0]);
    cart.add(product, product.variants[0]);
    expect(JSON.parse(localStorage.getItem(CART_STORAGE_KEY)!)).toEqual({ version: 1,
      items: [{ product_id: 1, variant_id: 2, quantity: 2 }] });
    const restored = new CartService();
    restored.reconcile([{ ...product, price_cents: 2500 }]);
    expect(restored.count()).toBe(2);
    expect(restored.subtotalCents()).toBe(6000);
  });

  it('drops unavailable variants and malformed storage without breaking checkout', () => {
    localStorage.setItem(CART_STORAGE_KEY, JSON.stringify({ version: 1, items: [
      { product_id: 1, variant_id: 999, quantity: 1 },
      { product_id: 1, variant_id: 2, quantity: -1 },
      { product_id: 1, variant_id: 2, quantity: 1.5 },
    ] }));
    const cart = new CartService();
    cart.reconcile([product]);
    expect(cart.count()).toBe(0);
    localStorage.setItem(CART_STORAGE_KEY, 'invalid json');
    const broken = new CartService();
    expect(() => broken.reconcile([product])).not.toThrow();
    expect(broken.items()).toEqual([]);
  });

  it('enforces quantity and line limits, including duplicate restored lines', () => {
    const cart = new CartService();
    cart.reconcile([product]);
    for (let i = 0; i < 100; i++) cart.add(product, product.variants[0]);
    expect(cart.add(product, product.variants[0])).toBe(false);
    expect(cart.count()).toBe(100);
    cart.clear();
    for (let i = 1; i <= 50; i++) cart.add({ ...product, id: i, variants: [] });
    expect(cart.add({ ...product, id: 51, variants: [] })).toBe(false);
    expect(cart.items()).toHaveLength(50);
    localStorage.setItem(CART_STORAGE_KEY, JSON.stringify({ version: 1, items: [
      { product_id: 1, variant_id: 2, quantity: 80 },
      { product_id: 1, variant_id: 2, quantity: 80 },
    ] }));
    const restored = new CartService();
    restored.reconcile([product]);
    expect(restored.count()).toBe(100);
  });

  it('works when local storage is blocked', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    try {
      const cart = new CartService();
      cart.reconcile([product]);
      expect(cart.add(product, product.variants[0])).toBe(true);
      expect(cart.count()).toBe(1);
    } finally { spy.mockRestore(); }
  });
});

// Reabrir la tienda debe reflejar también las reducciones, eliminaciones y el vaciado.
describe('Cart persistence across visits', () => {
  beforeEach(() => localStorage.clear());

  it('keeps quantity edits and removals after reopening, and never restores a cleared order', () => {
    const cart = new CartService();
    cart.reconcile([product]);
    cart.add(product, product.variants[0]);
    cart.add(product, product.variants[0]);
    cart.decrease(cart.items()[0]);
    const reopened = new CartService();
    reopened.reconcile([product]);
    expect(reopened.count()).toBe(1);
    reopened.remove(reopened.items()[0]);
    const removed = new CartService();
    removed.reconcile([product]);
    expect(removed.items()).toEqual([]);
    removed.add(product, product.variants[0]);
    removed.clear();
    const cleared = new CartService();
    cleared.reconcile([product]);
    expect(cleared.items()).toEqual([]);
  });

  it('removes inactive products when reopening the store', () => {
    const cart = new CartService();
    cart.reconcile([product]);
    cart.add(product, product.variants[0]);
    const reopened = new CartService();
    reopened.reconcile([{ ...product, is_active: false }]);
    expect(reopened.count()).toBe(0);
    expect(JSON.parse(localStorage.getItem(CART_STORAGE_KEY)!).items).toEqual([]);
  });
});

describe('Stock availability in cart', () => {
  beforeEach(() => localStorage.clear());
  it('caps a variant at its available units and refuses sold-out choices', () => {
    const stocked = { ...product, stock_quantity: 1, variants: [{ ...product.variants[0], stock_quantity: 1 }] };
    const cart = new CartService(); cart.reconcile([stocked]);
    expect(cart.add(stocked, stocked.variants[0])).toBe(true);
    expect(cart.add(stocked, stocked.variants[0])).toBe(false); expect(cart.count()).toBe(1);
    const empty = { ...product, variants: [], stock_quantity: 0 };
    expect(cart.add(empty)).toBe(false); expect(cart.notice()).toContain('agotado');
  });
  it('refreshes reduced stock and tells the customer before resubmitting', () => {
    const cart = new CartService(); cart.reconcile([product]);
    cart.add(product, product.variants[0]); cart.add(product, product.variants[0]);
    cart.reconcile([{ ...product, variants: [{ ...product.variants[0], stock_quantity: 1 }] }]);
    expect(cart.count()).toBe(1); expect(cart.notice()).toContain('Ajustamos');
    cart.reconcile([{ ...product, variants: [{ ...product.variants[0], stock_quantity: 0 }] }]);
    expect(cart.count()).toBe(0); expect(cart.notice()).toContain('agotadas');
  });
});
