import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { HttpClient, provideHttpClient } from '@angular/common/http';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { CustomerAuth } from './customer-auth.service';
import { ReviewService } from './review.service';
import { AdminAuth } from '../admin/auth.service';
describe('Customer session privacy', () => {
  let auth: CustomerAuth; let http: HttpTestingController;
  beforeEach(() => { TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] }); auth = TestBed.inject(CustomerAuth); http = TestBed.inject(HttpTestingController); });
  afterEach(() => http.verify());
  function login(service: CustomerAuth | AdminAuth, token: string, role = 'customer') {
    service.login('person@example.test', 'private-password').subscribe();
    const request = http.expectOne(r => r.url.endsWith('/auth/login'));
    expect(request.request.headers.has('Authorization')).toBe(false);
    request.flush({ access_token: token });
    const me = http.expectOne(r => r.url.endsWith('/auth/me'));
    expect(me.request.headers.get('Authorization')).toBe(`Bearer ${token}`);
    me.flush({ id: 1, full_name: 'Persona', email: 'person@example.test', role, is_active: true });
  }
  it('sends tokens only for private reviews; never persists credentials or leaks them to orders', () => {
    const before = [JSON.stringify(localStorage), JSON.stringify(sessionStorage)];
    login(auth, 'customer-test-token');
    expect(auth.user()?.role).toBe('customer');
    TestBed.inject(ReviewService).list(7).subscribe();
    const list = http.expectOne(r => r.url.endsWith('/products/7/reviews'));
    expect(list.request.headers.has('Authorization')).toBe(false);
    list.flush({ items: [], total: 0, average_rating: null, limit: 10, offset: 0 });
    TestBed.inject(HttpClient).post('/api/v1/orders', { customer_name: 'Invitado' }).subscribe();
    const order = http.expectOne('/api/v1/orders');
    expect(order.request.headers.has('Authorization')).toBe(false); order.flush({ id: 8 });
    TestBed.inject(ReviewService).save(7, 4, '  Excelente  ').subscribe();
    const save = http.expectOne(r => r.url.endsWith('/products/7/reviews/me'));
    expect(save.request.headers.get('Authorization')).toBe('Bearer customer-test-token');
    expect(save.request.body).toEqual({ rating: 4, comment: 'Excelente' }); save.flush({ id: 4 });
    expect([JSON.stringify(localStorage), JSON.stringify(sessionStorage)]).toEqual(before);
  });
  it('expires only the customer identity and preserves the independent admin session', () => {
    const admin = TestBed.inject(AdminAuth); login(admin, 'admin-test-token', 'admin'); login(auth, 'customer-test-token');
    TestBed.inject(ReviewService).mine(7).subscribe({ error: () => {} });
    http.expectOne(r => r.url.endsWith('/reviews/me')).flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(auth.user()).toBeNull(); expect(() => auth.headers()).toThrow();
    expect(admin.headers().get('Authorization')).toBe('Bearer admin-test-token');
  });
});
