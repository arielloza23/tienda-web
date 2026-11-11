import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { Product } from '../models/product.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class ProductService {
  private readonly http = inject(HttpClient);

  getProducts(): Observable<Product[]> {
    return this.http.get<Product[]>(`${environment.apiBaseUrl}/products`);
  }
}
