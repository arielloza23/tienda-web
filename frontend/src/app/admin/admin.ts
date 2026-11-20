import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, ElementRef, Injector, OnInit, afterNextRender, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DestroyRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { Product } from '../models/product.model';
import { AdminAuth } from './auth.service';
import { AdminOrders } from './orders';
import { AdminDashboard } from './dashboard';
import { AdminApi } from './admin-api.service';
import { emptyProductDraft, productRequest, productToDraft, productUpdateRequest, stockQuantity } from './product-form';

@Component({ imports: [CommonModule, FormsModule, RouterLink, AdminOrders, AdminDashboard], templateUrl: './admin.html', styleUrl: './admin.scss' })
export class Admin implements OnInit {
  protected readonly auth = inject(AdminAuth);
  private readonly api = inject(AdminApi);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly section = signal<'products' | 'orders' | 'dashboard'>('products');
  protected readonly measurementFields = [{ key: 'bust_cm', label: 'Busto' }, { key: 'waist_cm', label: 'Cintura' }, { key: 'hip_cm', label: 'Cadera' }] as const;
  protected loginEmail = '';
  protected loginPassword = '';
  protected readonly loggingIn = signal(false);
  protected readonly saving = signal(false);
  protected readonly savingStock = signal(false);
  protected readonly stockEditor = signal<{ productId: number; variantId: number | null; expected: number; label: string } | null>(null);
  protected stockInput = 1;
  protected readonly stockError = signal('');
  protected readonly stockSuccess = signal('');
  protected openStock(product: Product, variantId: number | null): void {
    if (this.busy()) return;
    const quantity = variantId === null ? product.stock_quantity : product.variants.find(v => v.id === variantId)?.stock_quantity;
    if (quantity === undefined) { this.stockError.set('Actualiza el catálogo para cargar el stock.'); return; }
    const variant = product.variants.find(v => v.id === variantId);
    this.stockEditor.set({ productId: product.id, variantId, expected: quantity, label: [product.name, variant?.size, variant?.color].filter(Boolean).join(' · ') });
    this.stockInput = quantity; this.stockError.set(''); this.stockSuccess.set('');
  }
  protected saveStock(): void {
    const editor = this.stockEditor();
    if (!editor || this.busy() || !this.auth.user()) return;
    try {
      if (typeof this.stockInput !== 'number') throw new Error('Escribe el stock disponible.');
      const quantity = stockQuantity(this.stockInput);
      this.savingStock.set(true); this.stockError.set(''); this.stockSuccess.set('');
      this.api.updateStock(editor.productId, editor.variantId, quantity, editor.expected)
        .pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.savingStock.set(false))).subscribe({
          next: product => {
            this.products.update(products => products.map(p => p.id === product.id ? product : p));
            this.stockEditor.set(null); this.stockSuccess.set('Stock disponible actualizado.');
          },
          error: (error: HttpErrorResponse) => {
            this.stockError.set(error.error?.detail?.message || 'No se pudo guardar el stock. Actualiza y vuelve a intentarlo.');
            if (error.status === 409) {
              this.stockEditor.set(null);
              this.api.list().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
                next: products => this.products.set(products),
                error: () => this.stockError.update(message => message + ' No pudimos recargar el catálogo. Pulsa Actualizar.'),
              });
            }
            if (error.status === 401 || error.status === 403) this.showError(error);
          },
        });
    } catch (error) { this.stockError.set(error instanceof Error ? error.message : 'Revisa el stock.'); }
  }
  protected readonly uploading = signal(false);
  protected readonly loadingProducts = signal(false);
  protected readonly error = signal('');
  protected readonly success = signal('');
  protected readonly products = signal<Product[]>([]);
  protected draft = emptyProductDraft();
  protected readonly editingId = signal<number | null>(null);
  protected readonly formVersion = signal(0);
  private readonly formTitle = viewChild<ElementRef<HTMLHeadingElement>>('formTitle');
  private readonly injector = inject(Injector);
  protected busy(): boolean { return this.savingStock() || this.saving() || this.uploading() || this.loadingProducts(); }
  private resetEditor(): void {
    this.editingId.set(null); this.draft = emptyProductDraft(); this.formVersion.update((version) => version + 1);
  }
  private focusEditor(): void {
    afterNextRender(() => this.formTitle()?.nativeElement.focus(), { injector: this.injector });
  }
  protected editProduct(product: Product): void {
    if (this.busy()) return;
    this.draft = productToDraft(product); this.editingId.set(product.id);
    this.formVersion.update((version) => version + 1); this.error.set(''); this.success.set(''); this.focusEditor();
  }
  protected cancelEditing(): void {
    if (this.busy()) return;
    this.resetEditor(); this.error.set(''); this.success.set(''); this.focusEditor();
  }

  ngOnInit(): void { if (this.auth.user()) this.loadProducts(); }
  protected login(): void {
    if (this.loggingIn()) return;
    this.error.set(''); this.success.set(''); this.loggingIn.set(true);
    this.auth.login(this.loginEmail, this.loginPassword).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => {
      this.loggingIn.set(false); this.loginPassword = '';
    })).subscribe({ next: () => this.loadProducts(), error: (error) => this.showError(error) });
  }
  protected logout(): void {
    if (this.busy()) return;
    this.auth.logout(); this.products.set([]); this.resetEditor(); this.error.set(''); this.success.set('');
  }
  protected loadProducts(): void {
    if (!this.auth.user() || this.busy()) return;
    this.loadingProducts.set(true);
    this.api.list().pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.loadingProducts.set(false))).subscribe({
      next: (products) => this.products.set(products), error: (error) => this.showError(error),
    });
  }
  protected suggestSlug(): void {
    if (!this.draft.slug) this.draft.slug = this.draft.name.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 200);
  }
  protected galleryColors(): string[] { return [...new Set(this.draft.variants.map((variant) => variant.color.trim()).filter(Boolean))]; }
  protected addVariant(): void { if (this.draft.variants.length < 100) this.draft.variants.push({ sku: '', size: '', color: '', adjustment: '0.00', stock_quantity: 1 }); }
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
    if (!file || this.busy() || !this.auth.user()) return;
    if (file.size > 8 * 1024 * 1024) { this.error.set('La foto debe pesar como máximo 8 MiB.'); return; }
    this.error.set(''); this.success.set(''); this.uploading.set(true);
    this.api.upload(file).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.uploading.set(false))).subscribe({
      next: ({ url }) => accept(url), error: (error) => this.showError(error),
    });
  }
  protected saveProduct(): void {
    if (this.busy() || !this.auth.user()) return;
    this.error.set(''); this.success.set('');
    try {
      const editingId = this.editingId();
      const operation = editingId === null ? this.api.create(productRequest(this.draft)) : this.api.update(editingId, productUpdateRequest(this.draft));
      this.saving.set(true);
      operation.pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.saving.set(false))).subscribe({
        next: (product) => {
          this.products.update((products) => editingId === null ? [product, ...products] : products.map((entry) => entry.id === product.id ? product : entry));
          this.resetEditor(); this.success.set(`Producto «${product.name}» ${editingId === null ? 'creado' : 'actualizado'} como ${product.is_active ? 'activo' : 'borrador'}.`);
          this.focusEditor();
        },
        error: (error) => this.showError(error),
      });
    } catch (error) { this.showError(error); }
  }
  private showError(error: unknown): void {
    let message = 'No se pudo completar la operación. Inténtalo nuevamente.';
    if (error instanceof HttpErrorResponse) {
      if (error.status === 401 || error.status === 403) { this.products.set([]); this.resetEditor(); }
      if (error.status === 401) message = 'La sesión venció o los datos de acceso son incorrectos. Inicia sesión nuevamente.';
      else if (error.status === 403) message = 'Esta cuenta no tiene permisos de administración.';
      else if (typeof error.error?.detail === 'string') message = error.error.detail;
      else if (Array.isArray(error.error?.detail)) message = 'Revisa los campos del formulario y los límites indicados.';
      else if (error.status === 0) message = 'No se pudo conectar con la tienda. Comprueba tu conexión.';
    } else if (error instanceof Error) message = error.message;
    this.error.set(message);
  }
}
