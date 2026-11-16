import { Component, input } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Product } from '../../models/product.model';
import { ProductReviews } from '../product-reviews/product-reviews';
import { ProductShowcase } from './product-showcase';

@Component({ selector: 'app-product-reviews', template: '' })
class ReviewsStub { readonly productId = input.required<number>(); }

const products: Product[] = [{
  id: 1, name: 'Artículo A', slug: 'articulo-a', is_active: true, price_cents: 1200,
  image_url: 'https://images.test/cover-a.webp',
  images: [
    { id: 1, url: 'https://images.test/detail-red.webp', alt: 'Detalle rojo', color: 'Rojo' },
    { id: 2, url: 'https://images.test/detail-blue.webp', alt: 'Detalle azul', color: 'Azul' },
    { id: 3, url: 'https://images.test/cover-a.webp', alt: 'Portada repetida', color: 'Rojo' },
  ],
  variants: [
    { id: 10, sku: 'RED', size: 'S', color: 'Rojo', price_adjustment_cents: 0 },
    { id: 11, sku: 'BLUE', size: 'M', color: 'Azul', price_adjustment_cents: 200 },
  ],
}, { id: 2, name: 'Artículo B', slug: 'articulo-b', is_active: true, price_cents: 1500, image_url: 'https://images.test/cover-b.webp', images: [], variants: [] }];

describe('Product showcase covers and photo gallery', () => {
  let fixture: ComponentFixture<ProductShowcase>;
  let host: HTMLElement;
  const cover = () => host.querySelector<HTMLImageElement>('.showcase-photo img')!;
  const dialog = () => host.querySelector<HTMLDialogElement>('.photo-dialog')!;
  const click = (selector: string) => { host.querySelector<HTMLButtonElement>(selector)!.click(); fixture.detectChanges(); };
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [ProductShowcase] });
    TestBed.overrideComponent(ProductShowcase, { remove: { imports: [ProductReviews] }, add: { imports: [ReviewsStub] } });
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
    HTMLElement.prototype.scrollIntoView = vi.fn();
    HTMLElement.prototype.setPointerCapture = vi.fn();
    fixture = TestBed.createComponent(ProductShowcase);
    fixture.componentRef.setInput('products', products);
    fixture.detectChanges();
    host = fixture.nativeElement;
    dialog().showModal = vi.fn(() => dialog().setAttribute('open', ''));
    dialog().close = vi.fn(() => dialog().removeAttribute('open'));
    const reviewsDialog = host.querySelector<HTMLDialogElement>('.reviews-dialog')!;
    reviewsDialog.showModal = vi.fn(() => reviewsDialog.setAttribute('open', ''));
    reviewsDialog.close = vi.fn(() => reviewsDialog.removeAttribute('open'));
  });

  afterEach(() => { fixture.destroy(); vi.unstubAllGlobals(); });

  it('loads reviews only in the popup, using the selected product and a stable snapshot', () => {
    expect(host.querySelector('app-product-reviews')).toBeNull();
    click('.showcase-reviews');
    const reviewsDialog = host.querySelector<HTMLDialogElement>('.reviews-dialog')!;
    expect(reviewsDialog.open).toBe(true);
    expect(host.querySelector('#reviews-dialog-title')!.textContent).toContain(products[0].name);
    const reviews = () => fixture.debugElement.queryAll(node => node.componentInstance instanceof ReviewsStub).map(node => node.componentInstance as ReviewsStub);
    expect(reviews()[0].productId()).toBe(1);
    fixture.componentRef.setInput('selectedProductId', 2); fixture.detectChanges();
    expect(reviews()[0].productId()).toBe(1);
    click('.reviews-dialog-close');
    expect(host.querySelector('app-product-reviews')).toBeNull();
    click('.showcase-reviews');
    expect(reviews()[0].productId()).toBe(2);
    expect(host.querySelector('#reviews-dialog-title')!.textContent).toContain(products[1].name);
  });

  it('closes reviews on Escape, restores focus, and unmounts the review form', () => {
    const trigger = host.querySelector<HTMLButtonElement>('.showcase-reviews')!;
    trigger.focus(); click('.showcase-reviews');
    const reviewsDialog = host.querySelector<HTMLDialogElement>('.reviews-dialog')!;
    const cancel = new Event('cancel', { cancelable: true });
    reviewsDialog.dispatchEvent(cancel); fixture.detectChanges();
    expect(cancel.defaultPrevented).toBe(true);
    expect(reviewsDialog.open).toBe(false);
    expect(host.querySelector('app-product-reviews')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('keeps reviews open for dialog padding and content clicks, closing only outside its bounds', () => {
    click('.showcase-reviews');
    const reviewsDialog = host.querySelector<HTMLDialogElement>('.reviews-dialog')!;
    vi.spyOn(reviewsDialog, 'getBoundingClientRect').mockReturnValue({ left: 20, right: 500, top: 20, bottom: 600 } as DOMRect);
    reviewsDialog.dispatchEvent(new MouseEvent('click', { clientX: 30, clientY: 30, bubbles: true }));
    host.querySelector('#reviews-dialog-title')!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    fixture.detectChanges(); expect(reviewsDialog.open).toBe(true);
    reviewsDialog.dispatchEvent(new MouseEvent('click', { clientX: 5, clientY: 5, bubbles: true }));
    fixture.detectChanges(); expect(reviewsDialog.open).toBe(false);
  });

  it('places one horizontal purchase guide below the carousel layout and before product navigation', () => {
    const guide = host.querySelector('#how-it-works')!;
    expect(host.querySelectorAll('#how-it-works')).toHaveLength(1);
    expect(host.querySelector('.showcase-details #how-it-works')).toBeNull();
    expect(guide.previousElementSibling!.classList.contains('showcase-layout')).toBe(true);
    expect(guide.nextElementSibling!.classList.contains('product-navigation')).toBe(true);
    expect(guide.querySelectorAll('li svg')).toHaveLength(3);
  });

  it('keeps one product outside the album even when it has multiple photos', () => {
    fixture.componentRef.setInput('products', [products[0]]); fixture.detectChanges();
    expect(host.querySelector('.stage-arrow')).toBeNull();
    click('.photo-open'); click('.photo-dialog-controls button:last-child');
    expect(dialog().querySelector('img')!.alt).toBe('Detalle rojo');
    expect(cover().src).toBe(products[0].image_url);
  });

  it('navigates products with stage arrows and keyboard while showing only their covers', () => {
    expect(cover().src).toBe(products[0].image_url);
    expect(host.querySelector('.photo-thumbnails')).toBeNull();
    expect(host.querySelector<HTMLButtonElement>('.stage-arrow-prev')!.disabled).toBe(true);
    click('.stage-arrow-next');
    expect(cover().src).toBe(products[1].image_url);
    expect(host.querySelector<HTMLButtonElement>('.stage-arrow-next')!.disabled).toBe(true);
    host.querySelector('.showcase-stage')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true }));
    fixture.detectChanges();
    expect(cover().src).toBe(products[0].image_url);
  });

  it('keeps the cover fixed when selecting another color and preserves the selected variant for orders', () => {
    const added = vi.fn(); fixture.componentInstance.addProduct.subscribe(added);
    click('.showcase-sizes button:nth-of-type(2)');
    expect(cover().src).toBe(products[0].image_url);
    click('.showcase-add');
    expect(added).toHaveBeenCalledWith({ product: products[0], variant: products[0].variants[1] });
  });

  it('clears the variant when the catalog changes and blocks adding a stale selection', () => {
    const added = vi.fn();
    fixture.componentInstance.addProduct.subscribe(added);
    click('.showcase-sizes button:nth-of-type(2)');
    expect(host.querySelector('.showcase-price')!.textContent).toContain('14.00');
    fixture.componentRef.setInput('products', [{ ...products[0], variants: [products[0].variants[0]] }]);
    fixture.detectChanges();
    expect(host.querySelector<HTMLButtonElement>('.showcase-add')!.disabled).toBe(true);
    expect(host.querySelector('.showcase-price')!.textContent).toContain('12.00');
    click('.showcase-add');
    expect(added).not.toHaveBeenCalled();
  });

  it('distinguishes the same size in different colors without inventing missing attributes', () => {
    fixture.componentRef.setInput('products', [{ ...products[0], variants: [
      products[0].variants[0], { ...products[0].variants[1], size: 'S' },
      { id: 12, sku: 'REF-12', size: ' ', color: null, price_adjustment_cents: 0 },
    ] }]); fixture.detectChanges();
    const buttons = Array.from(host.querySelectorAll<HTMLButtonElement>('.showcase-sizes button'));
    expect(buttons.map(b => b.getAttribute('aria-label'))).toEqual([
      'Talla S, Rojo', 'Talla S, Azul', 'Talla no especificada, Color no especificado, REF-12',
    ]);
    click('.showcase-sizes button:nth-of-type(2)');
    expect(buttons[2].textContent).toContain('Referencia: REF-12');
    expect(buttons[0].getAttribute('aria-pressed')).toBe('false');
    expect(buttons[1].getAttribute('aria-pressed')).toBe('true');
  });

  it('opens all product photos on cover click, navigates photos only in the dialog, and resets on reopening', () => {
    click('.photo-open'); expect(dialog().open).toBe(true);
    expect(dialog().querySelector('img')!.src).toBe(products[0].image_url);
    expect(dialog().textContent).toContain('Foto 1 de 3');
    click('.photo-dialog-controls button:last-child');
    expect(dialog().querySelector('img')!.alt).toBe('Detalle rojo');
    click('.photo-dialog-controls button:last-child');
    expect(dialog().querySelector('img')!.alt).toBe('Detalle azul');
    expect(cover().src).toBe(products[0].image_url);
    click('.photo-dialog-close'); click('.photo-open');
    expect(dialog().querySelector('img')!.src).toBe(products[0].image_url);
  });

  it('keeps the album open after tapping a photo and closes only on the backdrop', () => {
    click('.photo-open');
    const image = dialog().querySelector('img')!;
    image.setPointerCapture = vi.fn();
    dialog().setPointerCapture = vi.fn();
    const down = new Event('pointerdown', { bubbles: true });
    Object.assign(down, { isPrimary: true, button: 0, clientX: 100, clientY: 100, pointerId: 9 });
    image.dispatchEvent(down);
    expect(image.setPointerCapture).toHaveBeenCalledWith(9);
    expect(dialog().setPointerCapture).not.toHaveBeenCalled();
    image.click(); fixture.detectChanges();
    expect(dialog().open).toBe(true);
    dialog().querySelector('p')!.click(); fixture.detectChanges();
    expect(dialog().open).toBe(true);
    dialog().click(); fixture.detectChanges();
    expect(dialog().open).toBe(false);
  });

  it('swipes between products on the image without opening the dialog from the trailing click', () => {
    const button = host.querySelector('.photo-open')!;
    for (const [type, x] of [['pointerdown', 200], ['pointerup', 80]] as const) {
      const event = new Event(type, { bubbles: true });
      Object.assign(event, { isPrimary: true, button: 0, clientX: x, clientY: 100, pointerId: 1 });
      button.dispatchEvent(event);
    }
    fixture.detectChanges(); click('.photo-open');
    expect(cover().src).toBe(products[1].image_url);
    expect(dialog().open).toBe(false);
  });

  it('falls back to the first gallery image when a product has no cover and keeps missing images safe', () => {
    fixture.componentRef.setInput('products', [{ ...products[0], image_url: null }]); fixture.detectChanges();
    expect(cover().alt).toBe('Detalle rojo');
    fixture.componentRef.setInput('products', [{ ...products[0], image_url: null, images: [] }]); fixture.detectChanges();
    expect(host.querySelector('.photo-open')).toBeNull();
    expect(host.textContent).toContain('Este producto todavía no tiene fotos.');
  });
});
