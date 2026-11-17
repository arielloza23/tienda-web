import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subscription, finalize } from 'rxjs';
import { PasswordRecovery } from '../../services/password-recovery.service';
import { CustomerAuth } from '../../services/customer-auth.service';

@Component({ selector: 'app-reset-password', imports: [FormsModule, RouterLink], templateUrl: './reset-password.html', styleUrl: './reset-password.scss' })
export class ResetPassword implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly recovery = inject(PasswordRecovery);
  private readonly auth = inject(CustomerAuth);
  private readonly destroyRef = inject(DestroyRef);
  private token = '';
  private request?: Subscription;
  protected readonly hasToken = signal(false);
  protected readonly busy = signal(false);
  protected readonly complete = signal(false);
  protected readonly error = signal('');
  protected password = '';
  protected confirmation = '';
  ngOnInit(): void {
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      const token = params.get('token');
      // Ignorar el evento provocado por retirar la clave de la URL.
      if (token === null) return;
      this.request?.unsubscribe();
      this.busy.set(false); this.complete.set(false); this.error.set('');
      this.password = ''; this.confirmation = '';
      this.token = token.length <= 512 ? token : '';
      this.hasToken.set(!!this.token);
      // El enlace secreto deja de estar visible en la URL y en el historial.
      void this.router.navigate([], { relativeTo: this.route, queryParams: {}, replaceUrl: true });
    });
  }
  protected submit(): void {
    if (this.busy() || !this.token || this.complete()) return;
    this.error.set('');
    if (this.password.length < 8 || this.password.length > 128) {
      this.error.set('La contraseña debe tener entre 8 y 128 caracteres.'); return;
    }
    if (this.password !== this.confirmation) { this.error.set('Las contraseñas no coinciden.'); return; }
    this.busy.set(true);
    this.request = this.recovery.reset(this.token, this.password).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.busy.set(false))).subscribe({
      next: () => {
        this.token = ''; this.password = ''; this.confirmation = '';
        this.auth.logout(); this.complete.set(true);
      },
      error: (error: HttpErrorResponse) => {
        this.password = ''; this.confirmation = '';
        if (error.status === 400) {
          this.error.set('Este enlace no es válido o ya venció. Solicita uno nuevo desde Mi cuenta.');
          this.token = ''; this.hasToken.set(false);
        } else this.error.set('No se pudo cambiar la contraseña. Inténtalo de nuevo.');
      },
    });
  }
}
