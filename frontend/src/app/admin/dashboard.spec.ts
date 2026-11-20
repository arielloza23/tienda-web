import { TestBed } from '@angular/core/testing';
import { Subject } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { AdminDashboard } from './dashboard';
import { AnalyticsApi, DashboardData } from './analytics-api.service';

const sample: DashboardData = {
  days: 30, generated_at: '2026-11-20T15:00:00Z', period_start: '2026-10-22T05:00:00Z', period_end: '2026-11-20T15:00:00Z', timezone: 'America/Guayaquil', measurement_started_at: null,
  users: { customers: 3, active_customers: 2, inactive_customers: 1, administrators: 1 },
  orders: { total: 2, reserved: 1, paid: 0, cancelled: 0, unattributed: 2 }, interactions: [], most_commented: [], top_rated: [],
  products: [{ product_id: 1, product_name: 'Producto sin visitas', view_sessions: 0, cart_sessions: 0, checkout_sessions: 0, order_sessions: 0, paid_sessions: 0, order_conversion: null, payment_conversion: null }],
};
async function setup() {
  const requests: Subject<DashboardData>[] = [];
  const api = { dashboard: vi.fn(() => { const result = new Subject<DashboardData>(); requests.push(result); return result; }) };
  TestBed.configureTestingModule({ imports: [AdminDashboard], providers: [{ provide: AnalyticsApi, useValue: api }] });
  const fixture = TestBed.createComponent(AdminDashboard); fixture.detectChanges();
  return { fixture, api, requests, component: fixture.componentInstance };
}
describe('Admin indicators', () => {
  it('distinguishes unknown conversion from zero and labels totals and historical limitations', async () => {
    const { fixture, requests } = await setup(); requests[0].next(sample); requests[0].complete(); fixture.detectChanges();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Sin datos'); expect(text).toContain('Clientes registrados'); expect(text).toContain('Total acumulado');
    expect(text).toContain('no hay interacciones'); expect(text).toContain('Reservar o abrir WhatsApp no cuenta como pago');
    expect(fixture.nativeElement.querySelectorAll('tbody td').length).toBe(7);
  });
  it('clears stale numbers while changing period and allows retry after failure', async () => {
    const { fixture, component, api, requests } = await setup(); requests[0].next(sample); requests[0].complete(); fixture.detectChanges();
    component['selectPeriod'](7); fixture.detectChanges(); expect(api.dashboard).toHaveBeenLastCalledWith(7);
    expect(fixture.nativeElement.textContent).not.toContain('Producto sin visitas');
    component['load'](); expect(api.dashboard).toHaveBeenCalledTimes(2);
    requests[1].error(new Error('network')); fixture.detectChanges(); expect(fixture.nativeElement.querySelector('[role=alert]')).toBeTruthy();
    component['load'](); requests[2].next({ ...sample, days: 7 }); requests[2].complete(); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role=alert]')).toBeNull();
  });
});
