import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class PasswordRecovery {
  private readonly http = inject(HttpClient);
  request(email: string) {
    return this.http.post<{ message: string }>(`${environment.apiBaseUrl}/auth/forgot-password`, { email: email.trim() });
  }
  reset(token: string, password: string) {
    return this.http.post<{ message: string }>(`${environment.apiBaseUrl}/auth/reset-password`, { token, password });
  }
}
