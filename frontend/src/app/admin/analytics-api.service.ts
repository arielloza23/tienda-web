import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, throwError } from 'rxjs';
import { environment } from '../../environments/environment';
import { AdminAuth } from './auth.service';

export interface RankingProduct { product_id: number; product_name: string; comments: number; ratings: number; average_rating: number | null; }
export interface ConversionProduct { product_id: number; product_name: string; view_sessions: number; cart_sessions: number; checkout_sessions: number; order_sessions: number; paid_sessions: number; order_conversion: number | null; payment_conversion: number | null; }
export interface DashboardData {
  days: number; generated_at: string; period_start: string; period_end: string; timezone: string; measurement_started_at: string | null;
  users: { customers: number; active_customers: number; inactive_customers: number; administrators: number };
  orders: { total: number; reserved: number; paid: number; cancelled: number; unattributed: number };
  interactions: { event_type: string; events: number; sessions: number }[];
  most_commented: RankingProduct[]; top_rated: RankingProduct[]; products: ConversionProduct[];
}
@Injectable({ providedIn: 'root' })
export class AnalyticsApi {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AdminAuth);
  dashboard(days: number): Observable<DashboardData> {
    return this.http.get<DashboardData>(`${environment.apiBaseUrl}/analytics/dashboard`, {
      headers: this.auth.headers(), params: { days },
    }).pipe(catchError((error: HttpErrorResponse) => {
      if (error.status === 401 || error.status === 403) this.auth.logout();
      return throwError(() => error);
    }));
  }
}
