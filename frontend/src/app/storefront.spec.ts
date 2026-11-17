import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { HttpErrorResponse } from '@angular/common/http';
import { provideHttpClient } from '@angular/common/http';
import { Storefront } from './storefront';
import { CartService } from './services/cart.service';
import { OrderService } from './services/order.service';
import { ProductService } from './services/product.service';
import { OrderReceiptService } from './services/order-receipt.service';
const product = { id: 1, name: 'Body', slug: 'body', is_active: true, price_cents: 1000, variants: [] };
describe('Checkout price reconfirmation and receipt', () => {
  beforeEach(() => { localStorage.clear(); sessionStorage.clear(); });
  it('shows changed unit prices, preserves delivery and requires a second deliberate submit', () => {
    const orders = { createOrder: vi.fn().mockReturnValueOnce(throwError(() => new HttpErrorResponse({ status: 409, error: { detail: {
      code: 'price_changed', items: [{ product_id: 1, variant_id: null, expected_unit_price_cents: 1000, current_unit_price_cents: 1250 }], subtotal_cents: 1250,
    } } }))).mockReturnValueOnce(of({ id: 7, status: 'pending', subtotal_cents: 1250, total_cents: 1250, items: [{ product_name: 'Body', variant_label: null, quantity: 1, total_price_cents: 1250 }] })) };
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), { provide: OrderService, useValue: orders }, { provide: ProductService, useValue: { getProducts: () => of([{ ...product, price_cents: 1250 }]) } }] });
    const app = TestBed.createComponent(Storefront).componentInstance as any;
    const cart = TestBed.inject(CartService); cart.reconcile([product]); cart.add(product);
    const popup = vi.spyOn(window, 'open').mockImplementation(() => { throw new Error('Popup blocked'); });
    try {
      app.customerName.set('Cliente'); app.customerPhone.set('0991234567'); app.deliveryAddress.set('Calle privada 123');
      app.deliveryLocation.set({ latitude: -1, longitude: -79 });
      app.placeOrder();
      expect(orders.createOrder).toHaveBeenCalledTimes(1);
      expect(orders.createOrder.mock.calls[0][0].items[0].expected_unit_price_cents).toBe(1000);
      expect(app.orderConfirmation()).toBeNull(); expect(cart.subtotalCents()).toBe(1250);
      expect(app.priceChanges()[0]).toContain('antes'); expect(app.customerName()).toBe('Cliente');
      expect(app.deliveryLocation()).toEqual({ latitude: -1, longitude: -79 });
      app.placeOrder(); expect(orders.createOrder).toHaveBeenCalledTimes(2);
      expect(orders.createOrder.mock.calls[1][0].items[0].expected_unit_price_cents).toBe(1250);
      expect(app.orderConfirmation().id).toBe(7);
      expect(popup).not.toHaveBeenCalled();
      expect(app.isSubmittingOrder()).toBe(false); expect(cart.count()).toBe(0);
      const url = decodeURIComponent(app.whatsappFollowupUrl());
      expect(url).toContain('Subtotal de productos'); expect(url).not.toContain('Calle privada');
      app.startNewOrder(); expect(app.orderConfirmation()).toBeNull(); expect(TestBed.inject(OrderReceiptService).latest()?.id).toBe(7);
      cart.add(product); app.forgetReceipt(); expect(cart.count()).toBe(1);
    } finally { popup.mockRestore(); }
  });
});
