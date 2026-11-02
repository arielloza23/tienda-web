import { CommonModule, CurrencyPipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';

import { CartItem, Product, ProductVariant } from './models/product.model';
import { ProductService } from './services/product.service';
import { STORE_CONFIG } from './store-config';

@Component({
  imports: [CommonModule, CurrencyPipe],
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App implements OnInit {
  private readonly productService = inject(ProductService);
  private readonly whatsappPhone = STORE_CONFIG.whatsappPhone.replace(/\D/g, '');
  private readonly productImages: Record<string, string> = {
    'top-corse-encaje-negro':
      'https://images.pexels.com/photos/33114806/pexels-photo-33114806.jpeg?auto=compress&cs=tinysrgb&w=900',
    'top-corse-encaje-vino':
      'https://images.pexels.com/photos/29474759/pexels-photo-29474759.jpeg?auto=compress&cs=tinysrgb&w=900',
    'conjunto-floral-encaje-negro':
      'https://images.unsplash.com/photo-1652859921634-d30457cb9695?auto=format&fit=crop&w=1200&q=85',
    'conjunto-floral-encaje-vino':
      'https://images.pexels.com/photos/838787/pexels-photo-838787.jpeg?auto=compress&cs=tinysrgb&w=900',
  };

  protected readonly products = signal<Product[]>([]);
  protected readonly cart = signal<CartItem[]>([]);
  protected readonly isLoading = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly totalProducts = computed(() => this.products().length);
  protected readonly cartCount = computed(() =>
    this.cart().reduce((count, item) => count + item.quantity, 0),
  );
  protected readonly cartSubtotalCents = computed(() =>
    this.cart().reduce((total, item) => total + this.unitPriceCents(item) * item.quantity, 0),
  );
  protected readonly canSendOrder = computed(
    () => this.cart().length > 0 && this.whatsappPhone.length > 0,
  );

  ngOnInit(): void {
    this.loadProducts();
  }

  protected loadProducts(): void {
    this.isLoading.set(true);
    this.error.set(null);

    this.productService.getProducts().subscribe({
      next: (products) => {
        this.products.set(products);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
        this.error.set('No se pudieron cargar los productos en este momento.');
      },
    });
  }

  protected productImage(product: Product): string {
    return (
      this.productImages[product.slug] ??
      'https://images.pexels.com/photos/33114806/pexels-photo-33114806.jpeg?auto=compress&cs=tinysrgb&w=900'
    );
  }

  protected addToCart(product: Product, variant: ProductVariant | null = null): void {
    this.cart.update((items) => {
      const existing = items.find((item) => this.isSameCartLine(item, product, variant));
      if (existing) {
        return items.map((item) =>
          this.isSameCartLine(item, product, variant)
            ? { ...item, quantity: item.quantity + 1 }
            : item,
        );
      }

      return [...items, { product, variant, quantity: 1 }];
    });
  }

  protected increaseQuantity(itemToChange: CartItem): void {
    this.cart.update((items) =>
      items.map((item) =>
        this.isSameCartLine(item, itemToChange.product, itemToChange.variant)
          ? { ...item, quantity: item.quantity + 1 }
          : item,
      ),
    );
  }

  protected decreaseQuantity(itemToChange: CartItem): void {
    this.cart.update((items) =>
      items.flatMap((item) => {
        if (!this.isSameCartLine(item, itemToChange.product, itemToChange.variant)) {
          return [item];
        }
        return item.quantity > 1 ? [{ ...item, quantity: item.quantity - 1 }] : [];
      }),
    );
  }

  protected removeFromCart(itemToRemove: CartItem): void {
    this.cart.update((items) =>
      items.filter(
        (item) => !this.isSameCartLine(item, itemToRemove.product, itemToRemove.variant),
      ),
    );
  }

  protected clearCart(): void {
    this.cart.set([]);
  }

  protected cartItemKey(item: CartItem): string {
    return `${item.product.id}:${item.variant?.id ?? 'base'}`;
  }

  protected variantLabel(variant: ProductVariant): string {
    return [variant.color, variant.size].filter(Boolean).join(' / ') || variant.sku;
  }

  protected unitPriceCents(item: CartItem): number {
    return item.product.price_cents + (item.variant?.price_adjustment_cents ?? 0);
  }

  protected sendOrderToWhatsApp(): void {
    const items = this.cart();
    if (!this.whatsappPhone || items.length === 0) {
      return;
    }

    const lines = items.map((item, index) => {
      const variant = item.variant ? ` (${this.variantLabel(item.variant)})` : '';
      const lineTotal = this.formatPrice(this.unitPriceCents(item) * item.quantity);
      return `${index + 1}. ${item.product.name}${variant} x ${item.quantity}: ${lineTotal}`;
    });
    const message = [
      'Hola, quiero realizar este pedido:',
      ...lines,
      `Total: ${this.formatPrice(this.cartSubtotalCents())}`,
    ].join('\n');

    window.open(
      `https://wa.me/${this.whatsappPhone}?text=${encodeURIComponent(message)}`,
      '_blank',
      'noopener,noreferrer',
    );
  }

  private isSameCartLine(
    item: CartItem,
    product: Product,
    variant: ProductVariant | null,
  ): boolean {
    return item.product.id === product.id && item.variant?.id === variant?.id;
  }

  private formatPrice(priceCents: number): string {
    return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'USD' }).format(
      priceCents / 100,
    );
  }
}
