import { CommonModule, CurrencyPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, DestroyRef, ElementRef, inject, OnInit, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import type { DeliveryLocation } from './components/delivery-map/delivery-map';
import { DeliveryMap } from './components/delivery-map/delivery-map';
import { ProductShowcase } from './components/product-showcase/product-showcase';
import { availableQuantity, CartItem, Product, ProductVariant } from './models/product.model';
import { OrderCreateRequest } from './models/order.model';
import { CartService } from './services/cart.service';
import { OrderReceiptService, SavedReceipt } from './services/order-receipt.service';
import { OrderService } from './services/order.service';
import { ProductService } from './services/product.service';
import { CustomerAccount } from './components/customer-account/customer-account';
import { CustomerAuth } from './services/customer-auth.service';
import { STORE_CONFIG } from './store-config';

@Component({
  imports: [CommonModule, CurrencyPipe, FormsModule, RouterLink, DeliveryMap, ProductShowcase, CustomerAccount],
  selector: 'app-storefront',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class Storefront implements OnInit {
  protected readonly customerAuth = inject(CustomerAuth);
  private feedbackTimeout?: ReturnType<typeof setTimeout>;
  private readonly productService = inject(ProductService);
  private readonly orderService = inject(OrderService);
  private readonly cartService = inject(CartService);
  private readonly receiptService = inject(OrderReceiptService);
  protected readonly lastReceipt = this.receiptService.latest;
  protected readonly refreshingPrices = signal(false);
  protected readonly priceRefreshFailed = signal(false);
  protected readonly priceChanges = signal<string[]>([]);
  private readonly whatsappPhone = STORE_CONFIG.whatsappPhone.replace(/\D/g, '');
  private readonly fallbackProductImage =
    'https://images.pexels.com/photos/33114806/pexels-photo-33114806.jpeg?auto=compress&cs=tinysrgb&w=900';

  protected readonly products = signal<Product[]>([]);
  // Keep the full catalog for cart reconciliation; only offer available sizes in the store.
  protected readonly availableProducts = computed(() => this.products().flatMap(product => {
    if (!product.is_active) return [];
    if (!product.variants.length) return availableQuantity(product) > 0 ? [product] : [];
    const variants = product.variants.filter(variant => availableQuantity(product, variant) > 0);
    return variants.length ? [{ ...product, variants }] : [];
  }));
  protected readonly activeColor = signal('Todos');
  protected readonly featuredProductId = signal<number | null>(null);
  protected readonly cartOpen = signal(false);
  private readonly cartDialog = viewChild.required<ElementRef<HTMLDialogElement>>('cartDialog');
  protected readonly cartFeedback = signal('');
  protected readonly availableColors = computed(() => ['Todos', ...new Set(
    this.availableProducts().flatMap((product) => product.variants.map((variant) => variant.color?.trim()).filter((color): color is string => !!color)),
  )]);
  protected readonly activeSize = signal('Todas');
  protected readonly maximumPrice = signal<number | null>(null);
  protected readonly catalogSort = signal('featured');
  protected readonly availableSizes = computed(() => ['Todas', ...new Set(
    this.availableProducts().flatMap(product => product.variants.map(variant => variant.size?.trim()).filter((size): size is string => !!size)),
  )]);
  protected readonly hasCatalogFilters = computed(() => this.activeColor() !== 'Todos'
    || this.activeSize() !== 'Todas' || this.maximumPrice() !== null);
  protected readonly visibleProducts = computed(() => {
    const products = this.availableProducts().filter(product => this.matchingPrices(product).length > 0);
    const direction = this.catalogSort() === 'price-asc' ? 1 : this.catalogSort() === 'price-desc' ? -1 : 0;
    return direction ? products.sort((a, b) => direction * (this.catalogPrice(a) - this.catalogPrice(b))) : products;
  });

  protected setMaximumPrice(value: number | null): void {
    this.maximumPrice.set(typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null);
  }

  protected clearCatalogFilters(): void {
    this.activeColor.set('Todos');
    this.activeSize.set('Todas');
    this.maximumPrice.set(null);
    this.catalogSort.set('featured');
  }

  private matchingPrices(product: Product): number[] {
    const color = this.activeColor();
    const size = this.activeSize();
    const maximum = this.maximumPrice();
    const maximumCents = maximum === null ? Infinity : Math.round(maximum * 100);
    const prices = product.variants.length
      ? product.variants.filter(variant => (color === 'Todos' || variant.color?.trim() === color)
        && (size === 'Todas' || variant.size?.trim() === size))
        .map(variant => product.price_cents + variant.price_adjustment_cents)
      : color === 'Todos' && size === 'Todas' ? [product.price_cents] : [];
    return prices.filter(price => price <= maximumCents);
  }

  protected catalogPrice(product: Product): number {
    return Math.min(...this.matchingPrices(product));
  }

  protected catalogHasPriceRange(product: Product): boolean {
    return new Set(this.matchingPrices(product)).size > 1;
  }

  protected readonly cart = this.cartService.items;
  protected readonly cartNotice = this.cartService.notice;
  protected readonly isLoading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly customerName = signal('');
  protected readonly customerPhone = signal('');
  protected readonly deliveryAddress = signal('');
  protected readonly deliveryLocation = signal<DeliveryLocation | null>(null);
  protected readonly isLookingUpAddress = signal(false);
  protected readonly isSubmittingOrder = signal(false);
  protected readonly checkoutError = signal<string | null>(null);
  protected readonly orderConfirmation = signal<SavedReceipt | null>(null);
  protected readonly whatsappFollowupUrl = signal<string | null>(null);

  protected readonly cartCount = this.cartService.count;
  protected readonly cartSubtotalCents = this.cartService.subtotalCents;
  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.feedbackTimeout));
  }
  ngOnInit(): void {
    this.loadProducts();
  }

  protected loadProducts(): void {
    this.isLoading.set(true);
    this.error.set(null);

    this.productService.getProducts().subscribe({
      next: (products) => {
        this.products.set(products);
        this.cartService.reconcile(products);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
        this.error.set('No se pudieron cargar los productos en este momento.');
      },
    });
  }

  protected productImage(product: Product): string {
    return product.image_url || this.fallbackProductImage;
  }

  protected cartItemImage(item: CartItem): string {
    const color = item.variant?.color?.trim().toLocaleLowerCase();
    const images = item.product.images ?? [];
    const matchingImage = color
      ? images.find((image) => image.color?.trim().toLocaleLowerCase() === color && image.url?.trim())
      : undefined;
    return matchingImage?.url.trim() || item.product.image_url?.trim()
      || images.find((image) => image.url?.trim())?.url.trim() || this.fallbackProductImage;
  }

  protected cartItemDescription(item: CartItem): string {
    return [item.product.name,
      item.variant?.color?.trim() ? `color ${item.variant.color.trim()}` : '',
      item.variant?.size?.trim() ? `talla ${item.variant.size.trim()}` : '',
      item.variant && !item.variant.color?.trim() && !item.variant.size?.trim() ? item.variant.sku : '',
    ].filter(Boolean).join(', ');
  }

  protected scrollToSection(event: Event, id: string): void {
    event.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
  }

  protected showProduct(product: Product): void {
    this.featuredProductId.set(product.id);
    document.getElementById('top')?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
    document.querySelector<HTMLElement>('.showcase-stage')?.focus({ preventScroll: true });
  }

  protected openCart(): void {
    this.cartDialog().nativeElement.showModal();
    this.cartOpen.set(true);
  }

  protected closeCart(): void {
    this.cartDialog().nativeElement.close();
    this.cartOpen.set(false);
  }

  protected dismissCartBackdrop(event: MouseEvent): void {
    const dialog = this.cartDialog().nativeElement;
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) this.closeCart();
  }

  protected addToCart(product: Product, variant: ProductVariant | null = null): void {
    if (this.orderConfirmation()) this.startNewOrder();
    if (this.isSubmittingOrder()) return;
    if (!this.cartService.add(product, variant)) {
      this.cartFeedback.set(this.cartNotice());
      return;
    }
    clearTimeout(this.feedbackTimeout);
    this.cartFeedback.set(`${product.name}${variant?.size ? ', talla ' + variant.size : ''} añadido. ${this.cartCount()} ${this.cartCount() === 1 ? 'unidad' : 'unidades'} en tu pedido.`);
    this.feedbackTimeout = setTimeout(() => this.cartFeedback.set(''), 3500);
  }

  protected quantityLimit(item: CartItem): number { return availableQuantity(item.product, item.variant); }

  protected increaseQuantity(item: CartItem): void {
    if (!this.isSubmittingOrder()) this.cartService.add(item.product, item.variant);
  }

  protected decreaseQuantity(item: CartItem): void {
    if (!this.isSubmittingOrder()) this.cartService.decrease(item);
  }

  protected removeFromCart(item: CartItem): void {
    if (!this.isSubmittingOrder()) this.cartService.remove(item);
  }

  protected clearCart(): void {
    if (this.isSubmittingOrder()) return;
    this.cartService.clear();
    this.checkoutError.set(null);
  }

  protected placeOrder(): void {
    if (this.cart().length === 0 || this.isSubmittingOrder()) {
      return;
    }

    if (this.isLookingUpAddress() || this.refreshingPrices()) return;
    if (!this.deliveryLocation()) {
      this.checkoutError.set('Marca en el mapa dónde quieres recibir tu pedido.');
      return;
    }

    const location = this.deliveryLocation();
    const request: OrderCreateRequest = {
      customer_name: this.customerName().trim(),
      customer_phone: this.customerPhone().trim(),
      delivery_address: this.deliveryAddress().trim(),
      ...(location && {
        delivery_latitude: location.latitude,
        delivery_longitude: location.longitude,
      }),
      items: this.cart().map((item) => ({
        product_id: item.product.id,
        variant_id: item.variant?.id,
        quantity: item.quantity,
        expected_unit_price_cents: this.unitPriceCents(item),
      })),
    };

    this.checkoutError.set(null);
    this.isSubmittingOrder.set(true);

    this.orderService.createOrder(request).subscribe({
      next: (order) => {
        const whatsappUrl = this.buildWhatsAppFollowup(order);
        this.whatsappFollowupUrl.set(whatsappUrl);
        this.receiptService.save(order);
        this.orderConfirmation.set(this.lastReceipt());
        this.priceChanges.set([]);
        this.cartService.clear();
        this.cartNotice.set('');
        this.isSubmittingOrder.set(false);
      },
      error: (error: HttpErrorResponse) => {
        if (error.status === 409 && error.error?.detail?.code === 'price_changed') {
          const detail = error.error.detail;
          this.priceChanges.set((Array.isArray(detail.items) ? detail.items : []).map((change: { product_id: number; variant_id: number | null; expected_unit_price_cents: number; current_unit_price_cents: number }) => {
            const item = this.cart().find(i => i.product.id === change.product_id && (i.variant?.id ?? null) === (change.variant_id ?? null));
            return `${item ? this.cartItemDescription(item) : 'Producto'}: antes ${this.formatPrice(change.expected_unit_price_cents)}, ahora ${this.formatPrice(change.current_unit_price_cents)} por unidad.`;
          }));
          this.checkoutError.set('Los precios cambiaron. Actualizamos tu pedido; revisa los importes y vuelve a confirmar para aceptarlos.');
          this.refreshOrderPrices();
        } else if (error.status === 409 && error.error?.detail?.code === 'insufficient_stock') {
          this.checkoutError.set(error.error.detail.message || 'La disponibilidad cambió. Revisa las cantidades antes de volver a confirmar.');
          this.refreshOrderPrices();
        } else this.checkoutError.set(this.checkoutErrorMessage(error));
        this.isSubmittingOrder.set(false);
      },
    });
  }

  private refreshOrderPrices(): void {
    this.refreshingPrices.set(true);
    this.priceRefreshFailed.set(false);
    this.productService.getProducts().subscribe({
      next: products => { this.products.set(products); this.cartService.reconcile(products); this.refreshingPrices.set(false); },
      error: () => { this.priceRefreshFailed.set(true); this.checkoutError.set('No pudimos actualizar los precios. Reintenta la actualización antes de confirmar.'); },
    });
  }

  protected retryPrices(): void { this.refreshOrderPrices(); }
  protected viewLastReceipt(): void {
    const receipt = this.receiptService.current();
    if (!receipt) return;
    this.orderConfirmation.set(receipt);
    this.whatsappFollowupUrl.set(this.buildWhatsAppFollowup(receipt));
    this.openCart();
  }
  protected forgetReceipt(): void {
    this.receiptService.forget();
    this.orderConfirmation.set(null);
    this.whatsappFollowupUrl.set(null);
  }

  protected startNewOrder(): void {
    this.orderConfirmation.set(null);
    this.customerName.set('');
    this.customerPhone.set('');
    this.deliveryAddress.set('');
    this.deliveryLocation.set(null);
    this.checkoutError.set(null);
    this.whatsappFollowupUrl.set(null);
  }

  private buildWhatsAppFollowup(order: SavedReceipt): string | null {
    if (!this.whatsappPhone) return null;
    const lines = order.items.map((item, index) => `${index + 1}. ${item.product_name}${item.variant_label ? ` (${item.variant_label})` : ''} x ${item.quantity}: ${this.formatPrice(item.total_price_cents)}`);
    const message = [`Hola, registré el pedido #${order.id} y quiero coordinar mi pedido.`, '', ...lines,
      `Subtotal de productos: ${this.formatPrice(order.subtotal_cents)}`,
      'Envío y pago: por coordinar por WhatsApp.'].join('\n');
    return `https://wa.me/${this.whatsappPhone}?text=${encodeURIComponent(message)}`;
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

  private checkoutErrorMessage(error: HttpErrorResponse): string {
    const detail: unknown = error.error?.detail;
    if (typeof detail === 'string') {
      return detail;
    }

    if (Array.isArray(detail)) {
      const fieldMessages: Record<string, string> = {
        customer_name: 'Escribe tu nombre y apellido.',
        customer_phone: 'Ingresa un teléfono de contacto válido.',
        delivery_address: 'Ingresa una dirección de entrega completa.',
        delivery_latitude: 'El punto marcado en el mapa no es válido. Vuelve a marcarlo.',
        delivery_longitude: 'El punto marcado en el mapa no es válido. Vuelve a marcarlo.',
        items: 'El pedido debe incluir al menos un producto.',
        product_id: 'Uno de los productos ya no está disponible.',
        variant_id: 'La talla seleccionada ya no está disponible.',
        quantity: 'Revisa la cantidad seleccionada.',
      };
      const messages = detail
        .map((entry) => {
          if (typeof entry !== 'object' || entry === null) {
            return null;
          }
          const validation = entry as { loc?: unknown[]; msg?: unknown };
          const field = validation.loc
            ?.filter((part): part is string => typeof part === 'string')
            .pop();
          return fieldMessages[field ?? ''] ??
            (typeof validation.msg === 'string' ? validation.msg : null);
        })
        .filter((message): message is string => message !== null);

      if (messages.length > 0) {
        return [...new Set(messages)].join(' ');
      }
    }

    return 'No se pudo registrar el pedido. Revisa los datos e inténtalo otra vez.';
  }

  private formatPrice(priceCents: number): string {
    return new Intl.NumberFormat('es-EC', { style: 'currency', currency: 'USD' }).format(
      priceCents / 100,
    );
  }

}
