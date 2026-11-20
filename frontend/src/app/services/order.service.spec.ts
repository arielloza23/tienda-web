import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AnalyticsService } from './analytics.service';
import { OrderService } from './order.service';
import { OrderCreateRequest } from '../models/order.model';

const body: OrderCreateRequest = { customer_name: 'Cliente', customer_phone: '0991234567',
  delivery_address: 'Calle Principal 123', items: [{ product_id: 1, quantity: 1 }] };

describe('OrderService checkout retries', () => {
  let service: OrderService;
  let http: HttpTestingController;
  beforeEach(() => {
    sessionStorage.clear();
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

  it('freezes analytics attribution on retries without changing commerce idempotency', () => {
    const analytics = TestBed.inject(AnalyticsService);
    const session = vi.spyOn(analytics, 'sessionId').mockReturnValue('11111111-1111-4111-8111-111111111111');
    service.createOrder(body).subscribe({ error: () => {} });
    const first = http.expectOne(req => req.url.endsWith('/orders'));
    const key = first.request.headers.get('Idempotency-Key');
    expect(first.request.body.analytics_session_id).toBe('11111111-1111-4111-8111-111111111111');
    first.error(new ProgressEvent('error'));
    session.mockReturnValue('22222222-2222-4222-8222-222222222222');
    service.createOrder({ ...body, analytics_session_id: 'changed-client-value' }).subscribe();
    const retry = http.expectOne(req => req.url.endsWith('/orders'));
    expect(retry.request.headers.get('Idempotency-Key')).toBe(key);
    expect(retry.request.body.analytics_session_id).toBe('11111111-1111-4111-8111-111111111111');
    retry.flush({ id: 1 });
    session.mockRestore();
  });

  it('still posts a purchase when optional analytics UUID generation fails', () => {
    const uuid = vi.spyOn(crypto, 'randomUUID')
      .mockReturnValueOnce('11111111-1111-4111-8111-111111111111')
      .mockImplementation(() => { throw new Error('Analytics crypto unavailable'); });
    try {
      service.createOrder(body).subscribe();
      const request = http.expectOne(req => req.url.endsWith('/orders'));
      expect(request.request.body.analytics_session_id).toBeUndefined();
      request.flush({ id: 1 });
    } finally { uuid.mockRestore(); }
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
