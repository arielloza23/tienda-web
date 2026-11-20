import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { OrderCreateRequest, OrderReceipt } from '../models/order.model';
import { AnalyticsService } from './analytics.service';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class OrderService {
  private readonly http = inject(HttpClient);
  private readonly analytics = inject(AnalyticsService);

  private pending: { body: string; key: string; sessionId?: string } | null = null;

  createOrder(order: OrderCreateRequest): Observable<OrderReceipt> {
    const { analytics_session_id: _ignored, ...commerceOrder } = order;
    const body = JSON.stringify(commerceOrder);
    if (this.pending?.body !== body) {
      this.pending = { body, key: crypto.randomUUID(), sessionId: this.analytics.sessionId() };
    }
    const attempt = this.pending;
    this.analytics.flush();
    const payload = { ...commerceOrder, ...(attempt.sessionId ? { analytics_session_id: attempt.sessionId } : {}) };
    return this.http.post<OrderReceipt>(`${environment.apiBaseUrl}/orders`, payload, {
      headers: { 'Idempotency-Key': attempt.key },
    }).pipe(tap(() => { if (this.pending === attempt) this.pending = null; }));
  }
}
