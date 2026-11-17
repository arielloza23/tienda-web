import { TestBed, ComponentFixture } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { CustomerAuth } from '../../services/customer-auth.service';
import { CustomerAccount } from './customer-account';
describe('Customer account dialog', async () => {
  let fixture: ComponentFixture<CustomerAccount>; let auth: CustomerAuth; let http: HttpTestingController;
  beforeEach(async () => {
    HTMLDialogElement.prototype.showModal = function () { this.open = true; };
    HTMLDialogElement.prototype.close = function () { this.open = false; };
    TestBed.configureTestingModule({ imports: [CustomerAccount], providers: [provideHttpClient(), provideHttpClientTesting()] });
    auth = TestBed.inject(CustomerAuth); http = TestBed.inject(HttpTestingController); fixture = TestBed.createComponent(CustomerAccount);
    auth.open(); fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges();
  });
  afterEach(() => { fixture.destroy(); http.verify({ ignoreCancelled: true }); });
  function fill(name: string, value: string) { const input = fixture.nativeElement.querySelector(`input[name="${name}"]`); input.value = value; input.dispatchEvent(new Event('input')); }
  function submit() { fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); fixture.detectChanges(); }
  it('cancels in-flight login on closing and clears the password', async () => {
    fill('email', 'person@example.test'); fill('password', 'secret123');
    const click = new MouseEvent('click', { bubbles: true, cancelable: true });
    fixture.nativeElement.querySelector('button[type="submit"]').dispatchEvent(click); fixture.detectChanges();
    expect(click.defaultPrevented).toBe(false);
    const request = http.expectOne(r => r.url.endsWith('/auth/login'));
    fixture.nativeElement.querySelector('button[aria-label="Cerrar mi cuenta"]').click(); fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges();
    expect(request.cancelled).toBe(true); expect(auth.user()).toBeNull(); expect(auth.dialogOpen()).toBe(false);
    expect(fixture.nativeElement.querySelector('input[name="password"]').value).toBe('');
  });
  it('does not repeat registration when account creation succeeds but auto login fails', async () => {
    fixture.nativeElement.querySelector('button.secondary').click(); fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges();
    fill('full_name', 'Nombre público'); fill('email', 'person@example.test'); fill('password', 'secret123'); submit();
    http.expectOne(r => r.url.endsWith('/users')).flush({ id: 1 });
    http.expectOne(r => r.url.endsWith('/auth/login')).flush({}, { status: 503, statusText: 'Unavailable' }); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Cuenta creada');
    expect(fixture.nativeElement.querySelector('input[name="full_name"]')).toBeNull();
    fill('password', 'secret123'); submit();
    http.expectNone(r => r.url.endsWith('/users'));
    http.expectOne(r => r.url.endsWith('/auth/login')).flush({}, { status: 401, statusText: 'Unauthorized' }); fixture.detectChanges();
  });
  it('requests recovery without a password and shows unavailability honestly', async () => {
    fixture.nativeElement.querySelector('button.forgot-link').click(); fixture.detectChanges(); await fixture.whenStable();
    fill('recovery_email', 'person@example.test'); submit();
    const request = http.expectOne(r => r.url.endsWith('/auth/forgot-password'));
    expect(request.request.body).toEqual({ email: 'person@example.test' });
    request.flush({}, { status: 503, statusText: 'Unavailable' }); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain('todavía no está disponible');
    expect(fixture.nativeElement.querySelector('input[type="password"]')).toBeNull();
    submit();
    http.expectOne(r => r.url.endsWith('/auth/forgot-password')).flush({ message: 'Solicitud recibida.' }); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="status"]').textContent).toContain('Si existe una cuenta activa');
  });

});
