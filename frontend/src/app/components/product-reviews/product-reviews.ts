import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, effect, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription, finalize } from 'rxjs';
import { ReviewPage, ReviewRead } from '../../models/review.model';
import { CustomerAuth } from '../../services/customer-auth.service';
import { ReviewService } from '../../services/review.service';
@Component({ selector: 'app-product-reviews', imports: [FormsModule, DatePipe, DecimalPipe], templateUrl: './product-reviews.html', styleUrl: './product-reviews.scss' })
export class ProductReviews {
  readonly productId = input.required<number>();
  protected readonly auth = inject(CustomerAuth);
  private readonly api = inject(ReviewService);
  protected readonly page = signal<ReviewPage | null>(null);
  protected readonly offset = signal(0);
  protected readonly loading = signal(false);
  protected readonly loadingMine = signal(false);
  protected readonly saving = signal(false);
  protected readonly error = signal('');
  protected readonly mineError = signal('');
  protected readonly saveError = signal('');
  protected readonly success = signal('');
  protected readonly mine = signal<ReviewRead | null>(null);
  protected readonly rating = signal<number | null>(null);
  protected readonly comment = signal('');
  protected readonly stars = [1, 2, 3, 4, 5];
  private readonly refresh = signal(0);
  private readonly ownRefresh = signal(0);
  private dirty = false;
  private contextProduct?: number;
  private draftOwner?: number;
  private saveRequest?: Subscription;
  constructor() {
    effect(() => {
      const id = this.productId(); const user = this.auth.user();
      this.saveRequest?.unsubscribe(); this.saving.set(false);
      if (id !== this.contextProduct || (user && user.id !== this.draftOwner)) {
        this.offset.set(0); this.rating.set(null); this.comment.set(''); this.mine.set(null);
        this.saveError.set(''); this.success.set(''); this.dirty = false;
      }
      this.contextProduct = id;
      if (user) this.draftOwner = user.id;
    });
    effect(onCleanup => {
      const id = this.productId(); const offset = this.offset(); this.refresh();
      this.loading.set(true); this.error.set(''); this.page.set(null);
      const request = this.api.list(id, offset).subscribe({
        next: page => { this.page.set(page); this.loading.set(false); },
        error: () => { this.error.set('No se pudieron cargar las opiniones.'); this.loading.set(false); },
      });
      onCleanup(() => request.unsubscribe());
    });
    effect(onCleanup => {
      const id = this.productId(); const user = this.auth.user(); this.ownRefresh();
      this.mineError.set(''); this.loadingMine.set(false);
      if (!user) return;
      this.loadingMine.set(true);
      const request = this.api.mine(id).subscribe({
        next: mine => { this.mine.set(mine); if (!this.dirty) { this.rating.set(mine?.rating ?? null); this.comment.set(mine?.comment ?? ''); } this.loadingMine.set(false); },
        error: () => { this.mineError.set('No se pudo consultar tu opinión. Vuelve a intentar antes de publicar.'); this.loadingMine.set(false); },
      });
      onCleanup(() => request.unsubscribe());
    });
    inject(DestroyRef).onDestroy(() => this.saveRequest?.unsubscribe());
  }
  protected retry(): void { this.refresh.update(value => value + 1); }
  protected retryMine(): void { this.ownRefresh.update(value => value + 1); }
  protected setRating(value: number): void { this.dirty = true; this.rating.set(value); }
  protected setComment(value: string): void { this.dirty = true; this.comment.set(value); }
  protected save(): void {
    const rating = this.rating();
    if (this.saving() || this.loadingMine() || this.mineError() || !this.auth.user() || !rating || !Number.isInteger(rating) || rating < 1 || rating > 5 || this.comment().trim().length > 2000) return;
    const id = this.productId(); const userId = this.auth.user()!.id;
    this.saving.set(true); this.saveError.set(''); this.success.set('');
    this.saveRequest = this.api.save(id, rating, this.comment()).pipe(finalize(() => this.saving.set(false))).subscribe({
      next: review => {
        if (this.productId() !== id || this.auth.user()?.id !== userId) return;
        this.dirty = false; this.mine.set(review); this.rating.set(review.rating); this.comment.set(review.comment ?? '');
        this.success.set('Tu opinión se guardó.'); this.offset.set(0); this.refresh.update(value => value + 1);
      },
      error: (error: HttpErrorResponse) => {
        if (this.productId() !== id || (this.auth.user() && this.auth.user()?.id !== userId)) return;
        this.saveError.set(error.status === 401 ? 'Tu sesión venció. Inicia sesión de nuevo.' : error.status === 422 ? 'Elige entre 1 y 5 estrellas y revisa la extensión del comentario.' : 'No se pudo guardar tu opinión. Conservamos tu comentario para que vuelvas a intentar.');
      },
    });
  }
}
