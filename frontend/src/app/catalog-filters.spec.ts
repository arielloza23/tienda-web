import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';
import { Storefront } from './storefront';
import { Product } from './models/product.model';
const product: Product = { id: 1, name: 'Conjunto', slug: 'conjunto', price_cents: 1000, is_active: true, variants: [
  { id: 1, sku: 'red-s', size: 'S', color: 'Rojo', price_adjustment_cents: 0 },
  { id: 2, sku: 'black-m', size: 'M', color: 'Negro', price_adjustment_cents: 500 },
  { id: 3, sku: 'red-m', size: 'M', color: 'Rojo', price_adjustment_cents: 1000 },
] };
const basic: Product = { ...product, id: 2, name: 'Sin opciones', price_cents: 1200, variants: [] };
describe('Catalog filters and effective variant prices', () => {
  let app: any;
  beforeEach(() => {
    localStorage.clear(); sessionStorage.clear();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideRouter([])] });
    app = TestBed.createComponent(Storefront).componentInstance;
    app.products.set([product, basic]);
  });
  it('requires size, color and budget to match the same variant', () => {
    app.activeSize.set('M'); app.activeColor.set('Rojo'); app.setMaximumPrice(15);
    expect(app.visibleProducts()).toEqual([]);
    app.setMaximumPrice(20);
    expect(app.visibleProducts()).toEqual([product]);
    expect(app.catalogPrice(product)).toBe(2000);
    expect(app.catalogHasPriceRange(product)).toBe(false);
  });
  it('uses effective variant prices with inclusive cent boundaries', () => {
    app.products.set([{ ...product, price_cents: 804, variants: [{ ...product.variants[0], price_adjustment_cents: 1 }] }]);
    app.setMaximumPrice(8.04); expect(app.visibleProducts()).toEqual([]);
    app.setMaximumPrice(8.05); expect(app.visibleProducts().length).toBe(1);
    expect(app.catalogPrice(app.visibleProducts()[0])).toBe(805);
  });
  it('includes products without variants only when size and color are unrestricted', () => {
    app.setMaximumPrice(12); expect(app.visibleProducts()).toEqual([product, basic]);
    app.activeSize.set('M'); expect(app.visibleProducts()).toEqual([]);
    app.setMaximumPrice(null); app.activeSize.set('Todas'); app.activeColor.set('Negro');
    expect(app.visibleProducts()).toEqual([product]);
  });
  it('sorts by minimum matching price without mutating the original collection', () => {
    app.activeSize.set('M');
    const cheapM = { ...basic, id: 3, variants: [{ ...product.variants[1], price_adjustment_cents: 0 }] };
    app.products.set([product, cheapM]);
    app.catalogSort.set('price-asc'); expect(app.visibleProducts().map((p: Product) => p.id)).toEqual([3, 1]);
    app.catalogSort.set('price-desc'); expect(app.visibleProducts().map((p: Product) => p.id)).toEqual([1, 3]);
    expect(app.products()).toEqual([product, cheapM]);
  });
  it('labels price ranges and resets all filters', () => {
    expect(app.catalogPrice(product)).toBe(1000); expect(app.catalogHasPriceRange(product)).toBe(true);
    app.activeSize.set('M'); app.activeColor.set('Negro'); app.setMaximumPrice(16); app.catalogSort.set('price-desc');
    app.clearCatalogFilters();
    expect(app.hasCatalogFilters()).toBe(false); expect(app.catalogSort()).toBe('featured');
    expect(app.visibleProducts()).toEqual([product, basic]);
  });
});


describe('Sold-out catalog visibility', () => {
  it('hides exhausted products and sizes from the showcase and catalog filters, then restores replenished stock', () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideRouter([])] });
    const app = TestBed.createComponent(Storefront).componentInstance as any;
    const soldOut = { ...product, variants: product.variants.map(v => ({ ...v, stock_quantity: 0 })) };
    const mixed = { ...product, id: 3, variants: [
      { ...product.variants[0], stock_quantity: 0 }, { ...product.variants[1], stock_quantity: 1 },
    ] };
    app.products.set([soldOut, { ...basic, stock_quantity: 0 }, mixed]);
    expect(app.availableProducts().map((p: Product) => p.id)).toEqual([3]);
    expect(app.availableProducts()[0].variants.map((v: { id: number }) => v.id)).toEqual([2]);
    expect(app.visibleProducts()).toEqual(app.availableProducts());
    expect(app.availableSizes()).toEqual(['Todas', 'M']);
    expect(app.availableColors()).toEqual(['Todos', 'Negro']);
    expect(mixed.variants).toHaveLength(2);
    app.products.set([{ ...basic, stock_quantity: 1 }]);
    expect(app.availableProducts()).toEqual([{ ...basic, stock_quantity: 1 }]);
    app.products.set([{ ...basic, stock_quantity: 0 }]);
    expect(app.availableProducts()).toEqual([]);
    expect(app.visibleProducts()).toEqual([]);
  });
});
