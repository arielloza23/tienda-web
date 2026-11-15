import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { OrderCreateRequest, OrderReceipt } from '../models/order.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class OrderService {
  private readonly http = inject(HttpClient);

  private pending: { body: string; key: string } | null = null;

  createOrder(order: OrderCreateRequest): Observable<OrderReceipt> {
    const body = JSON.stringify(order);
    if (this.pending?.body !== body) {
      this.pending = { body, key: crypto.randomUUID() };
    }
    const attempt = this.pending;
    return this.http.post<OrderReceipt>(`${environment.apiBaseUrl}/orders`, order, {
      headers: { 'Idempotency-Key': attempt.key },
    }).pipe(tap(() => { if (this.pending === attempt) this.pending = null; }));
  }
}
