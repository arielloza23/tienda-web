import { HttpErrorResponse } from '@angular/common/http';
import { Component, ElementRef, effect, inject, signal, viewChild, DestroyRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription, finalize, switchMap, tap } from 'rxjs';
import { CustomerAuth } from '../../services/customer-auth.service';
@Component({ selector: 'app-customer-account', imports: [FormsModule], templateUrl: './customer-account.html', styleUrl: './customer-account.scss' })
export class CustomerAccount {
  protected readonly auth = inject(CustomerAuth);
  private readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');
  protected readonly signup = signal(false);
  protected readonly busy = signal(false);
  protected readonly error = signal('');
  protected readonly notice = signal('');
  protected fullName = ''; protected email = ''; protected password = '';
  private request?: Subscription;
  constructor() {
    effect(() => { const dialog = this.dialog().nativeElement; if (this.auth.dialogOpen()) { if (!dialog.open) dialog.showModal(); } else if (dialog.open) dialog.close(); });
    inject(DestroyRef).onDestroy(() => this.request?.unsubscribe());
  }
  protected dismissBackdrop(event: MouseEvent): void { if (event.target === event.currentTarget) this.close(); }
  protected close(): void { this.request?.unsubscribe(); this.password = ''; this.error.set(''); this.auth.close(); }
  protected changeMode(): void { this.signup.update(value => !value); this.password = ''; this.error.set(''); this.notice.set(''); }
  protected submit(): void {
    if (this.busy()) return;
    this.busy.set(true); this.error.set(''); this.notice.set('');
    const password = this.password;
    const request = this.signup() ? this.auth.register(this.fullName, this.email, password).pipe(
      tap(() => { this.signup.set(false); this.notice.set('Cuenta creada. Si no se inicia la sesión, ingresa con tu correo y contraseña.'); }),
      switchMap(() => this.auth.login(this.email, password)),
    ) : this.auth.login(this.email, password);
    this.request = request.pipe(finalize(() => { this.password = ''; this.busy.set(false); })).subscribe({
      next: () => { this.notice.set('Sesión iniciada. Ya puedes comentar y calificar productos.'); this.auth.close(); },
      error: (error: HttpErrorResponse) => this.error.set((error.status === 409 || (error.status === 400 && typeof error.error?.detail === 'string' && /email|correo|registr/i.test(error.error.detail))) ? 'Este correo ya tiene una cuenta. Inicia sesión.' : error.status === 401 ? 'Correo o contraseña incorrectos.' : error.status === 422 ? 'Revisa los datos. La contraseña debe tener entre 8 y 128 caracteres.' : 'No se pudo completar la solicitud. Intenta de nuevo.'),
    });
  }
}
