import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AdminAuth } from './auth.service';
import { AdminApi } from './admin-api.service';

describe('Admin access', () => {
  let auth: AdminAuth; let http: HttpTestingController;
  beforeEach(() => { TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] }); auth = TestBed.inject(AdminAuth); http = TestBed.inject(HttpTestingController); });
  afterEach(() => http.verify());
  function authenticate(role = 'admin') {
    auth.login('admin@example.com', 'password123').subscribe({ error: () => {} });
    const login = http.expectOne((r) => r.url.endsWith('/auth/login'));
    expect(login.request.headers.has('Authorization')).toBe(false);
    login.flush({ access_token: 'secret-test-token' });
    const me = http.expectOne((r) => r.url.endsWith('/auth/me'));
    expect(me.request.headers.get('Authorization')).toBe('Bearer secret-test-token');
    me.flush({ id: 1, full_name: 'Admin', email: 'admin@example.com', role, is_active: true });
  }
  it('checks server role and never opens admin access for customers', () => { authenticate('customer'); expect(auth.user()).toBeNull(); expect(() => auth.headers()).toThrow(); });
  it('keeps credentials in memory and clears them on expiry or logout', () => {
    const before = JSON.stringify(localStorage);
    authenticate(); expect(auth.user()?.role).toBe('admin');
    expect(JSON.stringify(localStorage)).toBe(before);
    TestBed.inject(AdminApi).list().subscribe({ error: () => {} });
    const listing = http.expectOne((r) => r.url.endsWith('/products/admin'));
    expect(listing.request.headers.get('Authorization')).toBe('Bearer secret-test-token');
    listing.flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(auth.user()).toBeNull();
    expect(() => auth.headers()).toThrow();
  });
  it('uploads multipart files without setting content type manually', () => {
    authenticate();
    TestBed.inject(AdminApi).upload(new File(['photo'], 'photo.png', { type: 'image/png' })).subscribe();
    const request = http.expectOne((r) => r.url.endsWith('/products/images'));
    expect(request.request.body).toBeInstanceOf(FormData);
    expect(request.request.headers.has('Content-Type')).toBe(false);
    request.flush({ url: 'https://cdn.example/photo.webp' });
  });
});
