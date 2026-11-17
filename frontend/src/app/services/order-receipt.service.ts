import { Injectable, signal } from '@angular/core';
import { OrderReceipt } from '../models/order.model';
export const RECEIPT_KEY = 'tienda.receipt.v1';
export const RECEIPT_TTL = 24 * 60 * 60 * 1000;
export type SavedReceipt = Pick<OrderReceipt, 'id' | 'status' | 'subtotal_cents' | 'total_cents' | 'items'>;
@Injectable({ providedIn: 'root' })
export class OrderReceiptService {
  private expiresAt = 0;
  readonly latest = signal<SavedReceipt | null>(this.read());
  save(order: OrderReceipt): void {
    const receipt = this.sanitize(order);
    this.expiresAt = Date.now() + RECEIPT_TTL;
    this.latest.set(receipt);
    try { sessionStorage.setItem(RECEIPT_KEY, JSON.stringify({ version: 1, expires: this.expiresAt, receipt })); } catch { /* Sigue disponible en memoria. */ }
  }
  current(): SavedReceipt | null {
    if (this.expiresAt <= Date.now()) this.forget();
    return this.latest();
  }
  forget(): void {
    this.latest.set(null);
    try { sessionStorage.removeItem(RECEIPT_KEY); } catch { /* Almacenamiento bloqueado. */ }
  }
  private sanitize(order: SavedReceipt): SavedReceipt {
    return { id: order.id, status: order.status, subtotal_cents: order.subtotal_cents, total_cents: order.total_cents,
      items: order.items.map(item => ({ product_name: item.product_name, variant_label: item.variant_label,
        quantity: item.quantity, total_price_cents: item.total_price_cents })) };
  }
  private read(): SavedReceipt | null {
    try {
      const raw = sessionStorage.getItem(RECEIPT_KEY);
      if (!raw || raw.length > 40000) return null;
      const saved = JSON.parse(raw);
      const r = saved.receipt;
      if (saved.version !== 1 || !Number.isFinite(saved.expires) || saved.expires <= Date.now() || saved.expires > Date.now() + RECEIPT_TTL
        || !r || !Number.isSafeInteger(r.id) || r.id < 1 || typeof r.status !== 'string' || r.status.length > 50
        || !Number.isSafeInteger(r.subtotal_cents) || r.subtotal_cents < 0 || !Number.isSafeInteger(r.total_cents) || r.total_cents < 0
        || !Array.isArray(r.items) || !r.items.length || r.items.length > 50
        || r.items.some((i: SavedReceipt['items'][number]) => typeof i.product_name !== 'string' || i.product_name.length > 300
          || !(i.variant_label === null || typeof i.variant_label === 'string' && i.variant_label.length <= 300)
          || !Number.isInteger(i.quantity) || i.quantity < 1 || i.quantity > 100
          || !Number.isSafeInteger(i.total_price_cents) || i.total_price_cents < 0)) {
        sessionStorage.removeItem(RECEIPT_KEY); return null;
      }
      this.expiresAt = saved.expires;
      return this.sanitize(r);
    } catch { return null; }
  }
}
