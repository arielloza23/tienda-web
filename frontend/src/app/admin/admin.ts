import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DestroyRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { Product } from '../models/product.model';
import { AdminAuth } from './auth.service';
import { AdminApi } from './admin-api.service';
import { emptyProductDraft, productRequest } from './product-form';

@Component({ imports: [CommonModule, FormsModule, RouterLink], templateUrl: './admin.html', styleUrl: './admin.scss' })
export class Admin implements OnInit {
  protected readonly auth = inject(AdminAuth);
  private readonly api = inject(AdminApi);
  private readonly destroyRef = inject(DestroyRef);
  protected loginEmail = '';
  protected loginPassword = '';
  protected readonly loggingIn = signal(false);
  protected readonly saving = signal(false);
  protected readonly uploading = signal(false);
  protected readonly loadingProducts = signal(false);
  protected readonly error = signal('');
  protected readonly success = signal('');
  protected readonly products = signal<Product[]>([]);
  protected draft = emptyProductDraft();

  ngOnInit(): void { if (this.auth.user()) this.loadProducts(); }
  protected login(): void {
    if (this.loggingIn()) return;
    this.error.set(''); this.success.set(''); this.loggingIn.set(true);
    this.auth.login(this.loginEmail, this.loginPassword).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
      this.loggingIn.set(false); this.loginPassword = '';
    })).subscribe({ next: () => this.loadProducts(), error: (error) => this.showError(error) });
  }
  protected logout(): void {
    if (this.saving() || this.uploading()) return;
    this.auth.logout(); this.products.set([]); this.draft = emptyProductDraft(); this.error.set(''); this.success.set('');
  }
  protected loadProducts(): void {
    if (!this.auth.user() || this.loadingProducts() || this.saving()) return;
    this.loadingProducts.set(true);
    this.api.list().pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.loadingProducts.set(false))).subscribe({
      next: (products) => this.products.set(products), error: (error) => this.showError(error),
    });
  }
  protected suggestSlug(): void {
    if (!this.draft.slug) this.draft.slug = this.draft.name.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 200);
  }
  protected galleryColors(): string[] { return [...new Set(this.draft.variants.map((variant) => variant.color.trim()).filter(Boolean))]; }
  protected addVariant(): void { if (this.draft.variants.length < 100) this.draft.variants.push({ sku: '', size: '', color: '', adjustment: '0.00' }); }
  protected removeVariant(index: number): void { this.draft.variants.splice(index, 1); }
  protected addImage(): void {
    if (this.draft.images.length < 12) this.draft.images.push({ url: '', alt: this.draft.name.slice(0, 200), color: this.galleryColors()[0] || 'Único' });
  }
  protected removeImage(index: number): void { this.draft.images.splice(index, 1); }
  protected moveImage(index: number, delta: number): void {
    const next = index + delta;
    if (next >= 0 && next < this.draft.images.length) [this.draft.images[index], this.draft.images[next]] = [this.draft.images[next], this.draft.images[index]];
  }
  protected clearCover(): void { this.draft.coverUrl = ''; }
  protected uploadCover(event: Event): void { this.upload(event, (url) => this.draft.coverUrl = url); }
  protected uploadGallery(event: Event, index: number): void {
    const entry = this.draft.images[index]; this.upload(event, (url) => entry.url = url);
  }
  private upload(event: Event, accept: (url: string) => void): void {
    const input = event.target as HTMLInputElement; const file = input.files?.[0]; input.value = '';
    if (!file || this.uploading() || this.saving() || !this.auth.user()) return;
    if (file.size > 8 * 1024 * 1024) { this.error.set('La foto debe pesar como máximo 8 MiB.'); return; }
    this.error.set(''); this.success.set(''); this.uploading.set(true);
    this.api.upload(file).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.uploading.set(false))).subscribe({
      next: ({ url }) => accept(url), error: (error) => this.showError(error),
    });
  }
  protected saveProduct(): void {
    if (this.saving() || this.uploading() || this.loadingProducts() || !this.auth.user()) return;
    this.error.set(''); this.success.set('');
    try {
      const request = productRequest(this.draft);
      this.saving.set(true);
      this.api.create(request).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.saving.set(false))).subscribe({
        next: (product) => { this.products.update((products) => [product, ...products]); this.draft = emptyProductDraft(); this.success.set(`Producto «${product.name}» creado como ${product.is_active ? 'activo' : 'borrador'}.`); },
        error: (error) => this.showError(error),
      });
    } catch (error) { this.showError(error); }
  }
  private showError(error: unknown): void {
    let message = 'No se pudo completar la operación. Inténtalo nuevamente.';
    if (error instanceof HttpErrorResponse) {
      if (error.status === 401) message = 'La sesión venció o los datos de acceso son incorrectos. Inicia sesión nuevamente.';
      else if (error.status === 403) message = 'Esta cuenta no tiene permisos de administración.';
      else if (typeof error.error?.detail === 'string') message = error.error.detail;
      else if (Array.isArray(error.error?.detail)) message = 'Revisa los campos del formulario y los límites indicados.';
      else if (error.status === 0) message = 'No se pudo conectar con la tienda. Comprueba tu conexión.';
    } else if (error instanceof Error) message = error.message;
    this.error.set(message);
  }
}
