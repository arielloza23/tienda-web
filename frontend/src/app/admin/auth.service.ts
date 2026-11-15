import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, map, switchMap } from 'rxjs';
import { environment } from '../../environments/environment';

export interface AdminUser { id: number; full_name: string; email: string; role: string; is_active: boolean; }
@Injectable({ providedIn: 'root' })
export class AdminAuth {
  private readonly http = inject(HttpClient);
  private readonly identity = signal<AdminUser | null>(null);
  readonly user = this.identity.asReadonly();
  private token: string | null = null;

  login(email: string, password: string): Observable<AdminUser> {
    this.logout();
    return this.http.post<{ access_token: string }>(`${environment.apiBaseUrl}/auth/login`, { email: email.trim(), password }).pipe(
      switchMap(({ access_token }) => this.http.get<AdminUser>(`${environment.apiBaseUrl}/auth/me`, {
        headers: new HttpHeaders({ Authorization: `Bearer ${access_token}` }),
      }).pipe(map((user) => {
        if (!user.is_active || user.role !== 'admin') throw new Error('Esta cuenta no tiene permisos de administración.');
        this.token = access_token;
        this.identity.set(user);
        return user;
      }))),
    );
  }

  headers(): HttpHeaders {
    if (!this.token || !this.user()) throw new Error('Inicia sesión para continuar.');
    return new HttpHeaders({ Authorization: `Bearer ${this.token}` });
  }

  logout(): void { this.token = null; this.identity.set(null); }
}
