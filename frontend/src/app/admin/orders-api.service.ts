import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { catchError, Observable, throwError } from 'rxjs';
import { environment } from '../../environments/environment';
import { AdminAuth } from './auth.service';

export type OrderStatus = 'pending' | 'paid' | 'shipped' | 'delivered' | 'cancelled';
export interface AdminOrder {
  id: number; user_id: number | null; customer_name: string | null; customer_phone: string | null;
  delivery_address: string | null; delivery_latitude?: number | null; delivery_longitude?: number | null;
  created_at: string; status: OrderStatus; subtotal_cents: number; shipping_total_cents: number;
  tax_total_cents: number; total_cents: number;
  items: Array<{ id: number; product_id: number; variant_id: number | null; product_name: string;
    variant_label: string | null; unit_price_cents: number; quantity: number; total_price_cents: number }>;
}
export const ORDER_LABELS: Record<OrderStatus, string> = {
  pending: 'Pendiente', paid: 'Pagado', shipped: 'Enviado', delivered: 'Entregado', cancelled: 'Cancelado',
};
export const ORDER_TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
  pending: ['paid', 'cancelled'], paid: ['shipped', 'cancelled'], shipped: ['delivered'], delivered: [], cancelled: [],
};
@Injectable({ providedIn: 'root' })
export class OrdersApi {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AdminAuth);
  private authorized<T>(request: Observable<T>): Observable<T> {
    return request.pipe(catchError((error: HttpErrorResponse) => {
      if (error.status === 401 || error.status === 403) this.auth.logout();
      return throwError(() => error);
    }));
  }
  list(): Observable<AdminOrder[]> {
    return this.authorized(this.http.get<AdminOrder[]>(`${environment.apiBaseUrl}/orders`, { headers: this.auth.headers() }));
  }
  updateStatus(id: number, status: OrderStatus): Observable<AdminOrder> {
    return this.authorized(this.http.patch<AdminOrder>(`${environment.apiBaseUrl}/orders/${id}/status`, null,
      { headers: this.auth.headers(), params: { new_status: status } }));
  }
}
