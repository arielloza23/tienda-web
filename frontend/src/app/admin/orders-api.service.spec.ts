import { HttpHeaders, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { environment } from '../../environments/environment';
import { AdminAuth } from './auth.service';
import { OrdersApi } from './orders-api.service';

describe('OrdersApi', () => {
  let http: HttpTestingController; let api: OrdersApi;
  const auth = { headers: () => new HttpHeaders({ Authorization: 'Bearer temporary-test-token' }), logout: vi.fn() };
  beforeEach(() => {
    auth.logout.mockClear();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), { provide: AdminAuth, useValue: auth }] });
    http = TestBed.inject(HttpTestingController); api = TestBed.inject(OrdersApi);
  });
  afterEach(() => http.verify());
  it('authenticates listing and sends status through the API query parameter', () => {
    api.list().subscribe();
    const list = http.expectOne(`${environment.apiBaseUrl}/orders`);
    expect(list.request.headers.get('Authorization')).toBe('Bearer temporary-test-token'); list.flush([]);
    api.updateStatus(12, 'paid').subscribe();
    const update = http.expectOne(`${environment.apiBaseUrl}/orders/12/status?new_status=paid`);
    expect(update.request.method).toBe('PATCH'); expect(update.request.body).toBeNull();
    expect(update.request.headers.get('Authorization')).toBe('Bearer temporary-test-token'); update.flush({ id: 12, status: 'paid' });
  });
  it('invalidates administrative access on expired or forbidden sessions', () => {
    for (const status of [401, 403]) {
      api.list().subscribe({ error: () => undefined });
      http.expectOne(`${environment.apiBaseUrl}/orders`).flush({}, { status, statusText: 'Unauthorized' });
    }
    expect(auth.logout).toHaveBeenCalledTimes(2);
  });
});
