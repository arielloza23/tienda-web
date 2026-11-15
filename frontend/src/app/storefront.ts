import { CommonModule, CurrencyPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, DestroyRef, ElementRef, inject, OnInit, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import type { DeliveryLocation } from './components/delivery-map/delivery-map';
import { DeliveryMap } from './components/delivery-map/delivery-map';
import { ProductShowcase } from './components/product-showcase/product-showcase';
import { CartItem, Product, ProductVariant } from './models/product.model';
import { OrderCreateRequest, OrderReceipt } from './models/order.model';
import { CartService } from './services/cart.service';
import { OrderService } from './services/order.service';
import { ProductService } from './services/product.service';
import { STORE_CONFIG } from './store-config';

@Component({
  imports: [CommonModule, CurrencyPipe, FormsModule, RouterLink, DeliveryMap, ProductShowcase],
  selector: 'app-storefront',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class Storefront implements OnInit {
  private feedbackTimeout?: ReturnType<typeof setTimeout>;
  private readonly productService = inject(ProductService);
  private readonly orderService = inject(OrderService);
  private readonly cartService = inject(CartService);
  private readonly whatsappPhone = STORE_CONFIG.whatsappPhone.replace(/\D/g, '');
  private readonly fallbackProductImage =
    'https://images.pexels.com/photos/33114806/pexels-photo-33114806.jpeg?auto=compress&cs=tinysrgb&w=900';

  protected readonly products = signal<Product[]>([]);
  protected readonly activeColor = signal('Todos');
  protected readonly featuredProductId = signal<number | null>(null);
  protected readonly cartOpen = signal(false);
  private readonly cartDialog = viewChild.required<ElementRef<HTMLDialogElement>>('cartDialog');
  protected readonly cartFeedback = signal('');
  protected readonly availableColors = computed(() => ['Todos', ...new Set(
    this.products().flatMap((product) => product.variants.map((variant) => variant.color?.trim()).filter((color): color is string => !!color)),
  )]);
  protected readonly visibleProducts = computed(() => this.activeColor() === 'Todos'
    ? this.products()
    : this.products().filter((product) => product.variants.some((variant) => variant.color?.trim() === this.activeColor())));
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
  protected readonly orderConfirmation = signal<OrderReceipt | null>(null);
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

    if (this.isLookingUpAddress()) return;
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
      })),
    };

    this.checkoutError.set(null);
    this.isSubmittingOrder.set(true);
    const whatsappWindow = this.whatsappPhone ? window.open('about:blank', '_blank') : null;
    if (whatsappWindow) {
      whatsappWindow.opener = null;
    }

    this.orderService.createOrder(request).subscribe({
      next: (order) => {
        const whatsappUrl = this.buildWhatsAppFollowup(order);
        this.whatsappFollowupUrl.set(whatsappUrl);
        if (whatsappWindow && whatsappUrl) {
          whatsappWindow.location.href = whatsappUrl;
        }
        this.orderConfirmation.set(order);
        this.cartService.clear();
        this.cartNotice.set('');
        this.isSubmittingOrder.set(false);
      },
      error: (error: HttpErrorResponse) => {
        whatsappWindow?.close();
        this.checkoutError.set(this.checkoutErrorMessage(error));
        this.isSubmittingOrder.set(false);
      },
    });
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

  private buildWhatsAppFollowup(order: OrderReceipt): string | null {
    if (!this.whatsappPhone) {
      return null;
    }

    const lines = order.items.map((item, index) => {
      const variant = item.variant_label ? ` (${item.variant_label})` : '';
      return `${index + 1}. ${item.product_name}${variant} x ${item.quantity}: ${this.formatPrice(item.total_price_cents)}`;
    });
    const message = [
      `Hola, registré el pedido #${order.id} y quiero coordinar el seguimiento.`,
      `Nombre: ${order.customer_name ?? ''}`,
      `Teléfono: ${order.customer_phone ?? ''}`,
      `Dirección: ${order.delivery_address ?? ''}`,
      ...(order.delivery_latitude !== null && order.delivery_longitude !== null
        ? [
            `Ubicación: https://www.google.com/maps?q=${order.delivery_latitude},${order.delivery_longitude}`,
          ]
        : []),
      '',
      ...lines,
      `Total: ${this.formatPrice(order.total_cents)}`,
    ].join('\n');

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
