import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of, Subject } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { AdminOrders } from './orders';
import { AdminOrder, OrdersApi } from './orders-api.service';
import { AdminAuth } from './auth.service';

const order: AdminOrder = { id: 12, user_id: null, customer_name: 'Cliente temporal', customer_phone: '0991234567', delivery_address: 'Dirección de prueba', status: 'pending', created_at: '2026-11-16T12:00:00Z', shipping_total_cents: 0, tax_total_cents: 0, subtotal_cents: 1500, total_cents: 1500, items: [] };
async function setup() {
  const response = new Subject<AdminOrder>();
  const auth = { user: signal<object | null>({ role: 'admin' }), logout: vi.fn(() => auth.user.set(null)) };
  const api = { list: vi.fn(() => of([order])), updateStatus: vi.fn(() => response) };
  TestBed.configureTestingModule({ imports: [AdminOrders], providers: [{ provide: AdminAuth, useValue: auth }, { provide: OrdersApi, useValue: api }] });
  const fixture = TestBed.createComponent(AdminOrders); fixture.detectChanges(); await fixture.whenStable();
  return { fixture, component: fixture.componentInstance, api, auth, response };
}
describe('Administrative order flow', () => {
  it('requires confirmation to cancel, prevents duplicate updates and uses the returned state', async () => {
    const { component, api, response } = await setup();
    component['select'](12); component['changeStatus']('shipped'); expect(api.updateStatus).not.toHaveBeenCalled();
    component['changeStatus']('cancelled'); expect(component['cancelling']()).toBe(true); expect(api.updateStatus).not.toHaveBeenCalled();
    component['changeStatus']('cancelled', true); component['changeStatus']('cancelled', true); component['refresh']();
    expect(api.updateStatus).toHaveBeenCalledTimes(1); expect(api.list).toHaveBeenCalledTimes(1);
    response.next({ ...order, status: 'cancelled' }); response.complete();
    expect(component['selected']()?.status).toBe('cancelled');
    component['changeStatus']('paid'); expect(api.updateStatus).toHaveBeenCalledTimes(1);
  });
  it('clears contact details on session expiry and does not render them for a logged-out user', async () => {
    const { component, response, auth, fixture } = await setup(); component['select'](12); component['changeStatus']('reserved');
    response.error(new HttpErrorResponse({ status: 401 })); fixture.detectChanges();
    expect(auth.logout).toHaveBeenCalled(); expect(component['orders']()).toEqual([]); expect(component['selected']()).toBeNull();
    expect(fixture.nativeElement.textContent).not.toContain(order.customer_phone);
  });
  it('filters orders locally and preserves contact details when an update fails', async () => {
    const { component, response } = await setup(); component['filter'].set('paid'); expect(component['filtered']()).toEqual([]);
    component['filter'].set(''); component['select'](12); component['changeStatus']('reserved');
    response.error(new HttpErrorResponse({ status: 409, error: { detail: 'El pedido cambió. Actualiza la lista.' } }));
    expect(component['selected']()?.status).toBe('pending'); expect(component['error']()).toContain('Actualiza'); expect(component['busy']()).toBe(false);
  });
  it('requires reservation before payment and exposes stock errors without losing the selected order', async () => {
    const { component, api, response } = await setup(); component['select'](12);
    component['changeStatus']('paid'); expect(api.updateStatus).not.toHaveBeenCalled();
    component['changeStatus']('reserved'); expect(api.updateStatus).toHaveBeenCalledWith(12, 'reserved');
    response.error(new HttpErrorResponse({ status: 409, error: { detail: { code: 'insufficient_stock', message: 'Stock insuficiente para talla M.' } } }));
    expect(component['error']()).toBe('Stock insuficiente para talla M.');
    expect(component['selected']()?.status).toBe('pending'); expect(api.list).toHaveBeenCalledTimes(2);
  });

});
