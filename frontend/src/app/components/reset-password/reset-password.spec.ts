import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { ResetPassword } from './reset-password';

describe('Password reset flow', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  beforeEach(async () => {
    TestBed.configureTestingModule({ providers: [provideRouter([{ path: 'reset-password', component: ResetPassword }]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    harness = await RouterTestingHarness.create();
  });
  afterEach(() => http.verify());
  async function open(token = 'test-secret-token') {
    await harness.navigateByUrl(`/reset-password${token ? '?token=' + token : ''}`, ResetPassword);
    await harness.fixture.whenStable(); harness.detectChanges();
    return harness.routeNativeElement!;
  }
  function fill(host: HTMLElement, name: string, value: string) {
    const input = host.querySelector<HTMLInputElement>(`input[name="${name}"]`)!;
    input.value = value; input.dispatchEvent(new Event('input'));
  }
  function submit(host: HTMLElement) {
    host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); harness.detectChanges();
  }
  it('removes the secret from the URL and requires matching passwords before sending', async () => {
    const host = await open();
    expect(TestBed.inject(Router).url).toBe('/reset-password');
    fill(host, 'password', 'new-password-123'); fill(host, 'confirmation', 'different-password'); submit(host);
    expect(host.textContent).toContain('no coinciden');
    http.expectNone(r => r.url.endsWith('/auth/reset-password'));
    fill(host, 'confirmation', 'new-password-123'); submit(host);
    const request = http.expectOne(r => r.url.endsWith('/auth/reset-password'));
    expect(request.request.body).toEqual({ token: 'test-secret-token', password: 'new-password-123' });
    request.flush({ message: 'Contraseña actualizada.' }); harness.detectChanges();
    expect(host.textContent).toContain('Tu contraseña fue actualizada');
    expect(host.querySelector('input')).toBeNull();
  });
  it('does not allow reusing an expired link', async () => {
    const host = await open();
    fill(host, 'password', 'new-password-123'); fill(host, 'confirmation', 'new-password-123'); submit(host);
    http.expectOne(r => r.url.endsWith('/auth/reset-password')).flush({}, { status: 400, statusText: 'Bad Request' }); harness.detectChanges();
    expect(host.textContent).toContain('ya venció');
    expect(host.querySelector('form')).toBeNull();
  });
  it('asks for a fresh link instead of presenting a form when no token is provided', async () => {
    const host = await open('');
    expect(host.querySelector('form')).toBeNull();
    expect(host.textContent).toContain('Solicita un nuevo enlace');
  });
  it('opens another reset link in the same tab after a successful reset', async () => {
    const host = await open();
    fill(host, 'password', 'new-password-123'); fill(host, 'confirmation', 'new-password-123'); submit(host);
    http.expectOne(r => r.url.endsWith('/auth/reset-password')).flush({ message: 'Actualizada.' }); harness.detectChanges();
    expect(host.querySelector('form')).toBeNull();
    const reopened = await open('another-secret-token');
    fill(reopened, 'password', 'another-password-456'); fill(reopened, 'confirmation', 'another-password-456'); submit(reopened);
    const request = http.expectOne(r => r.url.endsWith('/auth/reset-password'));
    expect(request.request.body.token).toBe('another-secret-token');
    request.flush({}, { status: 400, statusText: 'Bad Request' }); harness.detectChanges();
    expect(reopened.textContent).toContain('ya venció');
  });

});
