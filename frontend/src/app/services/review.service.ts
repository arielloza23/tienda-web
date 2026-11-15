import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { environment } from '../../environments/environment';
import { ReviewPage, ReviewRead } from '../models/review.model';
import { CustomerAuth } from './customer-auth.service';
@Injectable({ providedIn: 'root' })
export class ReviewService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(CustomerAuth);
  list(id: number, offset = 0) {
    return this.http.get<ReviewPage>(`${environment.apiBaseUrl}/products/${id}/reviews`, { params: { limit: 10, offset } });
  }
  mine(id: number) { return this.http.get<ReviewRead | null>(`${environment.apiBaseUrl}/products/${id}/reviews/me`, { headers: this.auth.headers() }).pipe(this.expiry()); }
  save(id: number, rating: number, comment: string) {
    return this.http.put<ReviewRead>(`${environment.apiBaseUrl}/products/${id}/reviews/me`, { rating, comment: comment.trim() || null }, { headers: this.auth.headers() }).pipe(this.expiry());
  }
  private expiry<T>() { return catchError<T, ReturnType<typeof throwError>>((error: HttpErrorResponse) => { if (error.status === 401) this.auth.logout(); return throwError(() => error); }); }
}
