import { CurrencyPipe } from '@angular/common';
import { Component, computed, DestroyRef, effect, ElementRef, inject, input, model, output, signal, viewChild } from '@angular/core';
import { AnalyticsService } from '../../services/analytics.service';
import { ProductOptions } from '../product-options/product-options';
import { ProductReviews } from '../product-reviews/product-reviews';
import { availableQuantity, Product, ProductVariant } from '../../models/product.model';

@Component({
  selector: 'app-product-showcase',
  imports: [CurrencyPipe, ProductReviews, ProductOptions],
  templateUrl: './product-showcase.html',
  styleUrl: './product-showcase.scss',
})
export class ProductShowcase {
  private readonly analytics = inject(AnalyticsService);
  private lastViewedProduct?: number;
  readonly products = input.required<Product[]>();
  readonly selectedProductId = model<number | null>(null);
  readonly addProduct = output<{ product: Product; variant: ProductVariant | null }>();
  protected readonly index = computed(() => Math.max(0, this.products().findIndex((product) => product.id === this.selectedProductId())));
  protected readonly variantId = signal<number | null>(null);
  protected readonly direction = signal('next');
  protected readonly product = computed(() => this.products()[this.index() % (this.products().length || 1)]);
  protected readonly previousProduct = computed(() => this.products()[this.index() - 1]);
  protected readonly nextProduct = computed(() => this.products()[this.index() + 1]);
  protected readonly selectedVariant = computed(() => this.product()?.variants.find((variant) => variant.id === this.variantId()) ?? null);
  protected readonly available = computed(() => this.product() ? availableQuantity(this.product()!, this.selectedVariant()) : 0);
  protected readonly photoIndex = signal(0);
  protected readonly photoColor = computed(() => this.selectedVariant()?.color ?? this.product()?.variants[0]?.color ?? this.product()?.images?.[0]?.color ?? '');
  protected readonly cover = computed(() => {
    const product = this.product();
    if (!product) return undefined;
    return product.image_url ? { url: product.image_url, alt: `${product.name} · Vista principal`, color: '' } : product.images?.[0];
  });
  protected readonly photos = computed(() => {
    const cover = this.cover();
    return [...(cover ? [cover] : []), ...(this.product()?.images ?? [])]
      .filter((image, index, images) => images.findIndex((entry) => entry.url === image.url) === index);
  });
  protected readonly currentPhoto = computed(() => this.photos()[this.photoIndex() % (this.photos().length || 1)]);
  private readonly photoDialog = viewChild.required<ElementRef<HTMLDialogElement>>('photoDialog');
  private readonly reviewsDialog = viewChild.required<ElementRef<HTMLDialogElement>>('reviewsDialog');
  protected readonly reviewsProduct = signal<{ id: number; name: string } | null>(null);
  private reviewsTrigger?: HTMLElement;
  private readonly photoStage = viewChild<ElementRef<HTMLElement>>('photoStage');
  protected readonly price = computed(() => (this.product()?.price_cents ?? 0) + (this.selectedVariant()?.price_adjustment_cents ?? 0));
  protected readonly theme = computed(() => {
    const color = this.photoColor().trim().toLocaleLowerCase();
    if (/vino|rojo|burdeos/.test(color)) return 'wine';
    if (/blanco|marfil|rosa/.test(color)) return 'blush';
    return 'charcoal';
  });
  private gesture?: { x: number; y: number; pointerId: number };
  private suppressClickUntil = 0;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.analytics.setFeaturedProduct(undefined));
    effect(() => {
      this.selectedProductId();
      this.products();
      this.variantId.set(null);
    });
    effect(() => {
      const productId = this.product()?.id;
      this.photoIndex.set(0);
      if (productId && productId !== this.lastViewedProduct) {
        this.analytics.track('product_view', productId);
      }
      if (!productId) this.analytics.setFeaturedProduct(undefined);
      this.lastViewedProduct = productId;
    });
  }

  protected scrollCatalog(event: Event): void {
    event.preventDefault();
    document.getElementById('catalog')?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
  }

  protected openReviews(event: Event): void {
    const product = this.product();
    if (!product) return;
    this.reviewsTrigger = event.currentTarget as HTMLElement;
    this.reviewsProduct.set({ id: product.id, name: product.name });
    this.reviewsDialog().nativeElement.showModal();
    this.analytics.track('reviews_open', product.id);
  }

  protected closeReviews(): void {
    const dialog = this.reviewsDialog().nativeElement;
    if (dialog.open) dialog.close();
    this.finishReviewsClose();
  }

  protected finishReviewsClose(): void {
    if (this.reviewsDialog().nativeElement.open || !this.reviewsProduct()) return;
    this.reviewsProduct.set(null);
    this.reviewsTrigger?.focus({ preventScroll: true });
    this.reviewsTrigger = undefined;
  }

  protected onReviewsBackdrop(event: MouseEvent): void {
    if (event.target !== event.currentTarget) return;
    const rect = this.reviewsDialog().nativeElement.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) this.closeReviews();
  }

  protected movePhoto(step: number): void {
    if (this.photos().length < 2) return;
    this.photoIndex.update((index) => Math.max(0, Math.min(index + step, this.photos().length - 1)));
  }

  protected openPhoto(): void {
    if (performance.now() < this.suppressClickUntil) return;
    this.photoIndex.set(0);
    if (this.cover()) {
      this.photoDialog().nativeElement.showModal();
      this.analytics.track('gallery_open', this.product()?.id);
    }
  }

  protected onDialogClick(event: MouseEvent): void {
    if (performance.now() >= this.suppressClickUntil && event.target === event.currentTarget) this.closePhoto();
  }

  protected closePhoto(): void {
    this.photoDialog().nativeElement.close();
  }

  protected move(step: number): void {
    const index = this.index() + step;
    if (index < 0 || index >= this.products().length) return;
    this.goTo(index);
    const stage = this.photoStage()?.nativeElement;
    stage?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'center' });
    stage?.focus({ preventScroll: true });
  }

  protected goTo(index: number): void {
    if (index === this.index() || index < 0 || index >= this.products().length) return;
    this.direction.set(index > this.index() ? 'next' : 'previous');
    this.selectedProductId.set(this.products()[index].id);
    this.variantId.set(null);
  }

  protected selectVariant(id: number): void {
    this.variantId.set(id);
    const product = this.product();
    if (product?.variants.some(variant => variant.id === id)) this.analytics.track('variant_select', product.id, id);
  }

  protected addToOrder(): void {
    const product = this.product();
    if (!product || this.available() === 0 || (product.variants.length && !this.selectedVariant())) return;
    this.addProduct.emit({ product, variant: this.selectedVariant() });
  }

  protected startGesture(event: PointerEvent): void {
    const target = event.target as HTMLElement;
    if (!event.isPrimary || event.button !== 0 || (target.closest('button, a') && !target.closest('.photo-open'))) return;
    this.suppressClickUntil = 0;
    this.gesture = { x: event.clientX, y: event.clientY, pointerId: event.pointerId };
    const capture = (target.closest('.photo-open') ?? target) as HTMLElement;
    capture.setPointerCapture(event.pointerId);
  }

  protected finishGesture(event: PointerEvent, gallery = false): void {
    if (!this.gesture || this.gesture.pointerId !== event.pointerId) return;
    const dx = event.clientX - this.gesture.x;
    const dy = event.clientY - this.gesture.y;
    this.gesture = undefined;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.3) {
      this.suppressClickUntil = performance.now() + 500;
      if (gallery) this.movePhoto(dx < 0 ? 1 : -1);
      else this.move(dx < 0 ? 1 : -1);
    }
  }

  protected cancelGesture(): void {
    this.gesture = undefined;
  }
}
