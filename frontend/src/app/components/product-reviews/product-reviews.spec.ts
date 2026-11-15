import { TestBed, ComponentFixture } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { CustomerAuth } from '../../services/customer-auth.service';
import { ProductReviews } from './product-reviews';
describe('Product reviews form', async () => {
  let fixture: ComponentFixture<ProductReviews>; let http: HttpTestingController; let auth: CustomerAuth;
  const page = { items: [], total: 0, average_rating: null, limit: 10, offset: 0 };
  const review = { id: 1, product_id: 7, rating: 5, comment: 'Mi opinión', author_name: 'Cliente', created_at: '2026-11-15T00:00:00Z', updated_at: '2026-11-15T00:00:00Z' };
  function login() {
    auth.login('client@example.test', 'password123').subscribe();
    http.expectOne(r => r.url.endsWith('/auth/login')).flush({ access_token: 'token' });
    http.expectOne(r => r.url.endsWith('/auth/me')).flush({ id: 3, full_name: 'Cliente', email: 'client@example.test', role: 'customer', is_active: true });
  }
  async function load(id = 7) {
    fixture.componentRef.setInput('productId', id); fixture.detectChanges();
    http.expectOne(r => r.url.endsWith(`/products/${id}/reviews`)).flush(page);
    if (auth.user()) http.expectOne(r => r.url.endsWith(`/products/${id}/reviews/me`)).flush(null);
    fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges();
  }
  async function draft(rating = 5, text = 'Mi opinión') {
    const radio: HTMLInputElement = fixture.nativeElement.querySelector(`input[aria-label="${rating} estrellas"]`);
    radio.click();
    const textarea: HTMLTextAreaElement = fixture.nativeElement.querySelector('textarea');
    textarea.value = text; textarea.dispatchEvent(new Event('input')); fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges();
  }
  async function save() { fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges(); }
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [ProductReviews], providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController); auth = TestBed.inject(CustomerAuth); fixture = TestBed.createComponent(ProductReviews);
  });
  afterEach(() => { fixture.destroy(); http.verify({ ignoreCancelled: true }); });
  it('keeps guest purchasing unrestricted and offers login for opinions', async () => {
    await load(); expect(fixture.nativeElement.textContent).toContain('Puedes comprar sin crear una cuenta');
    expect(fixture.nativeElement.querySelector('textarea')).toBeNull();
    fixture.nativeElement.querySelector('.review-form button').click(); expect(auth.dialogOpen()).toBe(true);
  });
  it('cancels old product requests and old saves instead of displaying stale state', async () => {
    login(); await load(); await draft(); await save();
    const pendingSave = http.expectOne(r => r.method === 'PUT');
    await load(8); expect(pendingSave.cancelled).toBe(true);
    expect(fixture.nativeElement.querySelector('textarea').value).toBe('');
    fixture.componentRef.setInput('productId', 9); fixture.detectChanges();
    const oldList = http.expectOne(r => r.url.endsWith('/products/9/reviews'));
    const oldMine = http.expectOne(r => r.url.endsWith('/products/9/reviews/me'));
    await load(10); expect(oldList.cancelled).toBe(true); expect(oldMine.cancelled).toBe(true);
    expect(fixture.nativeElement.textContent).not.toContain('Tu opinión se guardó');
  });
  it('preserves the draft on server error and session expiry, including after signing in again', async () => {
    login(); await load(); await draft(4, 'Conservar este texto'); await save();
    http.expectOne(r => r.method === 'PUT').flush({}, { status: 500, statusText: 'Error' }); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('textarea').value).toBe('Conservar este texto');
    await save(); http.expectOne(r => r.method === 'PUT').flush({}, { status: 401, statusText: 'Unauthorized' }); fixture.detectChanges();
    expect(auth.user()).toBeNull(); expect(fixture.nativeElement.querySelector('textarea')).toBeNull();
    login(); fixture.detectChanges(); http.expectOne(r => r.url.endsWith('/reviews/me')).flush(null); fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('textarea').value).toBe('Conservar este texto');
    expect(fixture.nativeElement.querySelector('input[aria-label="4 estrellas"]').checked).toBe(true);
  });
  it('refreshes public totals after saving and uses update mode for the same opinion', async () => {
    login(); await load(); await draft(); await save(); const request = http.expectOne(r => r.method === 'PUT');
    expect(request.request.body).toEqual({ rating: 5, comment: 'Mi opinión' }); request.flush(review); fixture.detectChanges();
    http.expectOne(r => r.url.endsWith('/products/7/reviews')).flush({ ...page, items: [review], total: 1, average_rating: 5 }); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Actualizar opinión');
    expect(fixture.nativeElement.textContent).toContain('1 opinión');
  });
});
