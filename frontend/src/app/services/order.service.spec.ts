import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { OrderService } from './order.service';
import { OrderCreateRequest } from '../models/order.model';

const body: OrderCreateRequest = { customer_name: 'Cliente', customer_phone: '0991234567',
  delivery_address: 'Calle Principal 123', items: [{ product_id: 1, quantity: 1 }] };

describe('OrderService checkout retries', () => {
  let service: OrderService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(OrderService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('retains key after a lost response and clears it after success', () => {
    service.createOrder(body).subscribe({ error: () => {} });
    const first = http.expectOne((req) => req.url.endsWith('/orders'));
    const key = first.request.headers.get('Idempotency-Key');
    expect(key).toMatch(/^[a-f0-9-]{36}$/);
    first.error(new ProgressEvent('error'));
    service.createOrder(body).subscribe();
    const retry = http.expectOne((req) => req.url.endsWith('/orders'));
    expect(retry.request.headers.get('Idempotency-Key')).toBe(key);
    retry.flush({ id: 1 });
    service.createOrder(body).subscribe();
    const next = http.expectOne((req) => req.url.endsWith('/orders'));
    expect(next.request.headers.get('Idempotency-Key')).not.toBe(key);
    next.flush({ id: 2 });
  });

  it('uses a new key if delivery or cart changes after a failed request', () => {
    service.createOrder(body).subscribe({ error: () => {} });
    const first = http.expectOne((req) => req.url.endsWith('/orders'));
    const key = first.request.headers.get('Idempotency-Key');
    first.error(new ProgressEvent('error'));
    service.createOrder({ ...body, delivery_address: 'Otra dirección 456' }).subscribe();
    const changed = http.expectOne((req) => req.url.endsWith('/orders'));
    expect(changed.request.headers.get('Idempotency-Key')).not.toBe(key);
    changed.flush({ id: 2 });
  });
});
