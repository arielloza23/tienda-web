import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { map, switchMap } from 'rxjs';
import { environment } from '../../environments/environment';
import { CustomerUser } from '../models/review.model';
@Injectable({ providedIn: 'root' })
export class CustomerAuth {
  private readonly http = inject(HttpClient);
  private token: string | null = null;
  private readonly identity = signal<CustomerUser | null>(null);
  readonly user = this.identity.asReadonly();
  readonly dialogOpen = signal(false);
  open(): void { this.dialogOpen.set(true); }
  close(): void { this.dialogOpen.set(false); }
  register(full_name: string, email: string, password: string) {
    return this.http.post<CustomerUser>(`${environment.apiBaseUrl}/users`, { full_name: full_name.trim(), email: email.trim(), password });
  }
  login(email: string, password: string) {
    this.logout();
    return this.http.post<{ access_token: string }>(`${environment.apiBaseUrl}/auth/login`, { email: email.trim(), password }).pipe(
      switchMap(({ access_token }) => this.http.get<CustomerUser>(`${environment.apiBaseUrl}/auth/me`, {
        headers: new HttpHeaders({ Authorization: `Bearer ${access_token}` }),
      }).pipe(map(user => {
        if (!user.is_active) throw new Error('Esta cuenta no está activa.');
        this.token = access_token; this.identity.set(user); return user;
      }))),
    );
  }
  headers(): HttpHeaders {
    if (!this.token || !this.user()) throw new Error('Inicia sesión para opinar.');
    return new HttpHeaders({ Authorization: `Bearer ${this.token}` });
  }
  logout(): void { this.token = null; this.identity.set(null); }
}
