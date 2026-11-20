import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { HttpErrorResponse } from '@angular/common/http';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Storefront } from './storefront';
import { AnalyticsService } from './services/analytics.service';
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

describe('Checkout availability conflict', () => {
  it('keeps delivery details and shows the refreshed stock without a false confirmation', () => {
    localStorage.clear(); sessionStorage.clear();
    const orders = { createOrder: vi.fn(() => throwError(() => new HttpErrorResponse({ status: 409,
      error: { detail: { code: 'insufficient_stock', message: 'No hay unidades suficientes.' } } }))) };
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), { provide: OrderService, useValue: orders },
      { provide: ProductService, useValue: { getProducts: () => of([{ ...product, stock_quantity: 1 }]) } }] });
    const app = TestBed.createComponent(Storefront).componentInstance as any;
    const cart = TestBed.inject(CartService); cart.reconcile([product]); cart.add(product); cart.add(product);
    app.customerName.set('Cliente'); app.deliveryAddress.set('Dirección guardada'); app.deliveryLocation.set({ latitude: -1, longitude: -79 });
    app.placeOrder();
    expect(app.orderConfirmation()).toBeNull(); expect(cart.count()).toBe(1);
    expect(app.customerName()).toBe('Cliente'); expect(app.deliveryAddress()).toBe('Dirección guardada');
    expect(app.checkoutError()).toContain('suficientes'); expect(cart.notice()).toContain('Ajustamos');
    expect(orders.createOrder).toHaveBeenCalledTimes(1);
  });
});


describe('Store interaction measurement', () => {
  it('counts only successful cart additions and distinct products when opening checkout', () => {
    localStorage.clear(); sessionStorage.clear();
    const analytics = { track: vi.fn(), flush: vi.fn(), setFeaturedProduct: vi.fn() };
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(),
      { provide: AnalyticsService, useValue: analytics }] });
    const app = TestBed.createComponent(Storefront).componentInstance as any;
    const cart = TestBed.inject(CartService);
    const variantProduct = { ...product, stock_quantity: 2, variants: [
      { id: 10, sku: 'M', size: 'M', price_adjustment_cents: 0, stock_quantity: 1 },
      { id: 11, sku: 'S', size: 'S', price_adjustment_cents: 0, stock_quantity: 1 },
    ] };
    cart.reconcile([variantProduct]);
    app.addToCart(variantProduct, variantProduct.variants[0]);
    app.addToCart(variantProduct, variantProduct.variants[0]);
    app.addToCart(variantProduct, variantProduct.variants[1]);
    expect(analytics.track.mock.calls.filter(call => call[0] === 'add_to_cart')).toHaveLength(2);
    // The UI opens a native dialog; the measurement itself must not duplicate product lines.
    app.cartDialog = () => ({ nativeElement: { showModal: vi.fn() } });
    app.openCart();
    expect(analytics.track.mock.calls.filter(call => call[0] === 'checkout_start')).toEqual([['checkout_start', 1]]);
    app.orderConfirmation.set({ items: [{ product_id: 1 }, { product_id: 1 }, { product_id: 2 }] });
    app.trackWhatsApp();
    expect(analytics.track.mock.calls.filter(call => call[0] === 'whatsapp_click')).toEqual([['whatsapp_click', 1], ['whatsapp_click', 2]]);
    expect(analytics.flush).toHaveBeenCalledOnce();
  });
});


describe('WhatsApp measurement payload contract', () => {
  it('emits a valid product event per distinct confirmed receipt product, never contact information', () => {
    sessionStorage.clear();
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    const app = TestBed.createComponent(Storefront).componentInstance as any;
    const receipts = TestBed.inject(OrderReceiptService);
    const item = { product_name: 'Body', variant_label: null, quantity: 1, total_price_cents: 1000 };
    receipts.save({ id: 9, status: 'pending', customer_name: 'Private name', customer_phone: '0991234567',
      delivery_address: 'Private address', delivery_latitude: -1, delivery_longitude: -79,
      subtotal_cents: 3000, total_cents: 3000,
      items: [{ ...item, product_id: 1 }, { ...item, product_id: 1 }, { ...item, product_id: 2 }] });
    app.orderConfirmation.set(receipts.latest());
    app.trackWhatsApp();
    const http = TestBed.inject(HttpTestingController);
    const request = http.expectOne(req => req.url.endsWith('/analytics/events'));
    const events = request.request.body.events;
    expect(events.map((event: any) => [event.event_type, event.product_id])).toEqual([
      ['whatsapp_click', 1], ['whatsapp_click', 2],
    ]);
    expect(JSON.stringify(request.request.body)).not.toMatch(/Private|0991234567|customer_|address|product_name/);
    request.flush({ accepted: 2 });
    http.verify();
  });
});
