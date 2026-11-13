import { CurrencyPipe } from '@angular/common';
import { Component, computed, effect, ElementRef, input, model, output, signal, viewChild } from '@angular/core';
import { Product, ProductVariant } from '../../models/product.model';

@Component({
  selector: 'app-product-showcase',
  imports: [CurrencyPipe],
  templateUrl: './product-showcase.html',
  styleUrl: './product-showcase.scss',
})
export class ProductShowcase {
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
  protected readonly photoIndex = signal(0);
  protected readonly photoColor = computed(() => this.selectedVariant()?.color ?? this.product()?.variants[0]?.color ?? this.product()?.images?.[0]?.color ?? '');
  protected readonly photos = computed(() => {
    const product = this.product();
    if (!product) return [];
    const normalize = (color: string) => color.trim().toLocaleLowerCase();
    const color = normalize(this.photoColor());
    const primaryColor = normalize(product.variants[0]?.color ?? product.images?.[0]?.color ?? '');
    const gallery = (product.images ?? []).filter((image) => normalize(image.color) === color);
    const primary = product.image_url && color === primaryColor
      ? [{ url: product.image_url, alt: `${product.name} · Vista principal` }] : [];
    return [...primary, ...gallery].filter((image, index, images) => images.findIndex((entry) => entry.url === image.url) === index);
  });
  protected readonly currentPhoto = computed(() => this.photos()[this.photoIndex() % (this.photos().length || 1)]);
  private readonly photoDialog = viewChild.required<ElementRef<HTMLDialogElement>>('photoDialog');
  private readonly photoStage = viewChild<ElementRef<HTMLElement>>('photoStage');
  protected readonly price = computed(() => (this.product()?.price_cents ?? 0) + (this.selectedVariant()?.price_adjustment_cents ?? 0));
  protected readonly theme = computed(() => {
    const color = this.photoColor().trim().toLocaleLowerCase();
    if (/vino|rojo|burdeos/.test(color)) return 'wine';
    if (/blanco|marfil|rosa/.test(color)) return 'blush';
    return 'charcoal';
  });
  private gesture?: { x: number; y: number; pointerId: number };

  constructor() {
    effect(() => {
      this.selectedProductId();
      this.variantId.set(null);
    });
    effect(() => {
      this.product()?.id;
      this.photoColor();
      this.photoIndex.set(0);
    });
  }

  protected movePhoto(step: number): void {
    if (this.photos().length < 2) return;
    this.photoIndex.update((index) => Math.max(0, Math.min(index + step, this.photos().length - 1)));
  }

  protected openPhoto(): void {
    if (this.currentPhoto()) this.photoDialog().nativeElement.showModal();
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

  protected addToOrder(): void {
    const product = this.product();
    if (!product || (product.variants.length && !this.selectedVariant())) return;
    this.addProduct.emit({ product, variant: this.selectedVariant() });
  }

  protected startGesture(event: PointerEvent): void {
    if (!event.isPrimary || event.button !== 0 || (event.target as HTMLElement).closest('button, a')) return;
    this.gesture = { x: event.clientX, y: event.clientY, pointerId: event.pointerId };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  }

  protected finishGesture(event: PointerEvent): void {
    if (!this.gesture || this.gesture.pointerId !== event.pointerId) return;
    const dx = event.clientX - this.gesture.x;
    const dy = event.clientY - this.gesture.y;
    this.gesture = undefined;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.3) {
      this.movePhoto(dx < 0 ? 1 : -1);
    }
  }

  protected cancelGesture(): void {
    this.gesture = undefined;
  }
}
