import { Injectable, computed, signal } from '@angular/core';
import { CartItem, Product, ProductVariant } from '../models/product.model';

export const CART_STORAGE_KEY = 'tienda.cart.v1';
export const MAX_CART_LINES = 50;
export const MAX_ITEM_QUANTITY = 100;
interface SavedLine { product_id: number; variant_id: number | null; quantity: number; }

@Injectable({ providedIn: 'root' })
export class CartService {
  private readonly state = signal<CartItem[]>([]);
  readonly items = this.state.asReadonly();
  readonly count = computed(() => this.items().reduce((sum, item) => sum + item.quantity, 0));
  readonly subtotalCents = computed(() => this.items().reduce((sum, item) =>
    sum + (item.product.price_cents + (item.variant?.price_adjustment_cents ?? 0)) * item.quantity, 0));
  readonly notice = signal('');
  private restored = false;

  reconcile(products: Product[]): void {
    const saved = this.restored ? this.serialize() : this.read();
    this.restored = true;
    const lines: CartItem[] = [];
    for (const line of saved) {
      const product = products.find((entry) => entry.id === line.product_id && entry.is_active);
      if (!product) continue;
      const variant = line.variant_id === null ? null : product.variants.find((entry) => entry.id === line.variant_id);
      if ((line.variant_id !== null && !variant) || (!variant && product.variants.length > 0)) continue;
      const duplicate = lines.find((entry) => entry.product.id === product.id && entry.variant?.id === variant?.id);
      if (duplicate) {
        duplicate.quantity = Math.min(MAX_ITEM_QUANTITY, duplicate.quantity + line.quantity);
      } else {
        lines.push({ product, variant: variant ?? null, quantity: line.quantity });
      }
    }
    this.state.set(lines);
    this.save();
    if (saved.length) this.notice.set('Carrito actualizado con los precios y la disponibilidad del catálogo.');
  }

  add(product: Product, variant: ProductVariant | null = null): boolean {
    const current = this.items().find((item) => this.same(item, product.id, variant?.id));
    if ((current?.quantity ?? 0) >= MAX_ITEM_QUANTITY) {
      this.notice.set('Puedes pedir hasta 100 unidades de la misma talla y color.');
      return false;
    }
    if (!current && this.items().length >= MAX_CART_LINES) {
      this.notice.set('Puedes incluir hasta 50 tallas y colores en un pedido.');
      return false;
    }
    this.notice.set('');
    this.state.update((items) => current
      ? items.map((item) => item === current ? { ...item, quantity: item.quantity + 1 } : item)
      : [...items, { product, variant, quantity: 1 }]);
    this.save();
    return true;
  }

  decrease(target: CartItem): void {
    this.state.update((items) => items.flatMap((item) => !this.same(item, target.product.id, target.variant?.id)
      ? [item] : item.quantity > 1 ? [{ ...item, quantity: item.quantity - 1 }] : []));
    this.save();
  }

  remove(target: CartItem): void {
    this.state.update((items) => items.filter((item) => !this.same(item, target.product.id, target.variant?.id)));
    this.save();
  }

  clear(): void {
    this.state.set([]);
    this.notice.set('');
    this.save();
  }

  private same(item: CartItem, productId: number, variantId: number | undefined): boolean {
    return item.product.id === productId && item.variant?.id === variantId;
  }

  private serialize(): SavedLine[] {
    return this.items().map((item) => ({ product_id: item.product.id, variant_id: item.variant?.id ?? null, quantity: item.quantity }));
  }

  private read(): SavedLine[] {
    try {
      const raw = globalThis.localStorage?.getItem(CART_STORAGE_KEY);
      if (!raw || raw.length > 20000) return [];
      const saved = JSON.parse(raw);
      if (saved?.version !== 1 || !Array.isArray(saved.items) || saved.items.length > MAX_CART_LINES) return [];
      return saved.items.filter((line: SavedLine) => line && Number.isSafeInteger(line.product_id) && line.product_id > 0
        && (line.variant_id === null || (Number.isSafeInteger(line.variant_id) && line.variant_id > 0))
        && Number.isInteger(line.quantity) && line.quantity > 0 && line.quantity <= MAX_ITEM_QUANTITY);
    } catch { return []; }
  }

  private save(): void {
    try {
      globalThis.localStorage?.setItem(CART_STORAGE_KEY, JSON.stringify({ version: 1, items: this.serialize() }));
    } catch { /* El carrito sigue funcionando si el navegador bloquea almacenamiento. */ }
  }
}
