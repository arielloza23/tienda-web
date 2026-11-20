import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, throwError } from 'rxjs';
import { environment } from '../../environments/environment';
import { Product } from '../models/product.model';
import { AdminAuth } from './auth.service';

export interface ProductCreate {
  name: string; slug: string; description: string | null; price_cents: number; is_active: boolean; image_url: string | null;
  stock_quantity?: number;
  variants: Array<{ stock_quantity?: number; sku: string; size: string | null; color: string | null; price_adjustment_cents: number; bust_cm?: number | null; waist_cm?: number | null; hip_cm?: number | null }>;
  images: Array<{ url: string; alt: string; color: string }>;
}
export interface ProductUpdate extends Omit<ProductCreate, 'variants'> {
  variants: Array<ProductCreate['variants'][number] & { id?: number | null }>;
}
@Injectable({ providedIn: 'root' })
export class AdminApi {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AdminAuth);
  private authorized<T>(request: Observable<T>): Observable<T> {
    return request.pipe(catchError((error: HttpErrorResponse) => {
      if (error.status === 401 || error.status === 403) this.auth.logout();
      return throwError(() => error);
    }));
  }
  list(): Observable<Product[]> {
    return this.authorized(this.http.get<Product[]>(`${environment.apiBaseUrl}/products/admin`, { headers: this.auth.headers() }));
  }
  create(product: ProductCreate): Observable<Product> {
    return this.authorized(this.http.post<Product>(`${environment.apiBaseUrl}/products`, product, { headers: this.auth.headers() }));
  }
  update(id: number, product: ProductUpdate): Observable<Product> {
    return this.authorized(this.http.put<Product>(`${environment.apiBaseUrl}/products/${id}`, product, { headers: this.auth.headers() }));
  }
  updateStock(id: number, variantId: number | null, quantity: number, expectedQuantity: number): Observable<Product> {
    return this.authorized(this.http.patch<Product>(`${environment.apiBaseUrl}/products/${id}/stock`,
      { variant_id: variantId, quantity, expected_quantity: expectedQuantity }, { headers: this.auth.headers() }));
  }
  upload(file: File): Observable<{ url: string }> {
    const body = new FormData(); body.append('file', file);
    return this.authorized(this.http.post<{ url: string }>(`${environment.apiBaseUrl}/products/images`, body, { headers: this.auth.headers() }));
  }
}
