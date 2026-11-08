import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { OrderCreateRequest, OrderReceipt } from '../models/order.model';

@Injectable({
  providedIn: 'root',
})
export class OrderService {
  private readonly http = inject(HttpClient);

  createOrder(order: OrderCreateRequest): Observable<OrderReceipt> {
    return this.http.post<OrderReceipt>('/api/v1/orders', order);
  }
}