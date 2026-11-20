import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OrderReceiptService, RECEIPT_KEY, RECEIPT_TTL } from './order-receipt.service';
import { OrderReceipt } from '../models/order.model';
const order: OrderReceipt = { id: 42, status: 'pending', customer_name: 'Private name', customer_phone: '0991234567',
  delivery_address: 'Private address', delivery_latitude: -1, delivery_longitude: -79,
  subtotal_cents: 1500, total_cents: 1500, items: [{ product_name: 'Body', variant_label: 'M / Negro', quantity: 1, total_price_cents: 1500 }] };
describe('Order receipt privacy and expiry', () => {
  beforeEach(() => { sessionStorage.clear(); vi.useRealTimers(); });
  it('restores only receipt fields and never stores contact, map or WhatsApp URLs', () => {
    const service = new OrderReceiptService(); service.save(order);
    const raw = sessionStorage.getItem(RECEIPT_KEY)!;
    for (const privateValue of ['Private name', '0991234567', 'Private address', 'latitude', 'longitude', 'customer_', 'wa.me']) expect(raw).not.toContain(privateValue);
    expect(new OrderReceiptService().latest()).toEqual({ id: 42, status: 'pending', subtotal_cents: 1500, total_cents: 1500, items: order.items });
    service.forget(); expect(new OrderReceiptService().latest()).toBeNull();
  });
  it('preserves valid product identifiers for WhatsApp measurement without attributing legacy receipts', () => {
    const service = new OrderReceiptService();
    service.save({ ...order, items: [{ ...order.items[0], product_id: 7 }] });
    expect(new OrderReceiptService().latest()?.items[0].product_id).toBe(7);
    service.save(order);
    expect(new OrderReceiptService().latest()?.items[0].product_id).toBeUndefined();
  });

  it('rejects expired and malformed saved receipts', () => {
    vi.useFakeTimers();
    new OrderReceiptService().save(order);
    vi.advanceTimersByTime(RECEIPT_TTL + 1);
    expect(new OrderReceiptService().latest()).toBeNull();
    sessionStorage.setItem(RECEIPT_KEY, '{broken');
    expect(new OrderReceiptService().latest()).toBeNull();
    vi.useRealTimers();
  });
  it('works in memory when storage is unavailable', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw Error('blocked'); });
    try { const service = new OrderReceiptService(); service.save(order); expect(service.latest()?.id).toBe(42); }
    finally { spy.mockRestore(); }
  });
});
