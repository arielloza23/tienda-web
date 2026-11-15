import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { NgForm } from '@angular/forms';
import { By } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { Subject, of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { Product } from '../models/product.model';
import { Admin } from './admin';
import { AdminApi } from './admin-api.service';
import { AdminAuth } from './auth.service';

const product: Product = { id: 7, name: 'Body', slug: 'body-vino', price_cents: 1550, is_active: false,
  variants: [{ id: 23, sku: 'BODY-M', size: 'M', color: 'Vino', price_adjustment_cents: 200 }],
  images: [{ id: 8, url: 'https://cdn.example/front.webp', alt: 'Vista frontal', color: 'Vino' }] };

describe('Admin editing', () => {
  async function setup() {
    const response = new Subject<Product>();
    const api = { list: vi.fn(() => of([product])), update: vi.fn(() => response), create: vi.fn() };
    const auth = { user: signal({ email: 'admin@example.com', full_name: 'Admin' }), logout: vi.fn() };
    TestBed.configureTestingModule({ imports: [Admin], providers: [provideRouter([]), { provide: AdminApi, useValue: api }, { provide: AdminAuth, useValue: auth }] });
    const fixture = TestBed.createComponent(Admin); fixture.detectChanges(); await fixture.whenStable();
    return { fixture, editor: fixture.componentInstance, response, api };
  }
  it('retains edited values on errors, locks busy actions and updates the existing row after success', async () => {
    const { fixture, editor, response, api } = await setup();
    editor['editProduct'](product); fixture.detectChanges(); await fixture.whenStable();
    editor['draft'].name = 'Body editado'; editor['saveProduct']();
    expect(api.update).toHaveBeenCalledWith(7, expect.objectContaining({ name: 'Body editado', variants: [expect.objectContaining({ id: 23 })] }));
    editor['cancelEditing'](); expect(editor['editingId']()).toBe(7);
    response.error(new HttpErrorResponse({ status: 409, error: { detail: 'SKU ocupado' } }));
    expect(editor['draft'].name).toBe('Body editado'); expect(editor['editingId']()).toBe(7);
    expect(editor['error']()).toBe('SKU ocupado');
    const retry = new Subject<Product>(); api.update.mockReturnValue(retry); editor['saveProduct']();
    retry.next({ ...product, name: 'Body editado' }); retry.complete();
    expect(editor['products']()).toHaveLength(1); expect(editor['products']()[0].name).toBe('Body editado');
    expect(editor['editingId']()).toBeNull(); expect(editor['draft'].name).toBe(''); expect(editor['success']()).toContain('actualizado');
  });
  it('cancels with a fresh pristine form and never mutates catalog objects', async () => {
    const { fixture, editor } = await setup(); editor['editProduct'](product);
    fixture.detectChanges(); await fixture.whenStable();
    editor['draft'].variants[0].sku = 'EDITED';
    const form = fixture.debugElement.query(By.directive(NgForm)).injector.get(NgForm);
    form.control.markAsDirty(); form.control.markAllAsTouched();
    editor['cancelEditing'](); fixture.detectChanges(); await fixture.whenStable();
    const newForm = fixture.debugElement.query(By.directive(NgForm)).injector.get(NgForm);
    expect(newForm).not.toBe(form); expect(newForm.pristine).toBe(true); expect(newForm.untouched).toBe(true);
    expect(editor['editingId']()).toBeNull(); expect(product.variants[0].sku).toBe('BODY-M');
  });
});
