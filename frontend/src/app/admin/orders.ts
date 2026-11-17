import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, DestroyRef, effect, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { finalize } from 'rxjs';
import { AdminAuth } from './auth.service';
import { AdminOrder, OrderStatus, OrdersApi, ORDER_LABELS, ORDER_TRANSITIONS } from './orders-api.service';

@Component({ selector: 'app-admin-orders', imports: [CommonModule, FormsModule], templateUrl: './orders.html', styleUrl: './orders.scss' })
export class AdminOrders implements OnInit {
  private readonly api = inject(OrdersApi);
  private readonly auth = inject(AdminAuth);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly orders = signal<AdminOrder[]>([]);
  protected readonly selectedId = signal<number | null>(null);
  protected readonly selected = computed(() => this.orders().find((order) => order.id === this.selectedId()) ?? null);
  protected readonly filter = signal<OrderStatus | ''>('');
  protected readonly filtered = computed(() => this.orders().filter((order) => !this.filter() || order.status === this.filter()));
  protected readonly loading = signal(false);
  protected readonly updating = signal(false);
  protected readonly busy = computed(() => this.loading() || this.updating());
  protected readonly error = signal('');
  protected readonly success = signal('');
  protected readonly cancelling = signal(false);
  protected readonly labels = ORDER_LABELS;
  protected readonly statuses = Object.keys(ORDER_LABELS) as OrderStatus[];
  protected readonly actions: Record<OrderStatus, string> = { pending: '', paid: 'Marcar como pagado', shipped: 'Marcar como enviado', delivered: 'Marcar como entregado', cancelled: 'Cancelar pedido' };
  constructor() {
    effect(() => { if (!this.auth.user()) { this.orders.set([]); this.selectedId.set(null); this.cancelling.set(false); } });
  }
  ngOnInit(): void { this.refresh(); }
  protected transitions(order: AdminOrder): OrderStatus[] { return ORDER_TRANSITIONS[order.status]; }
  protected refresh(): void {
    if (!this.auth.user() || this.busy()) return;
    this.loading.set(true); this.error.set(''); this.success.set(''); this.cancelling.set(false);
    this.api.list().pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.loading.set(false))).subscribe({
      next: (orders) => { if (this.auth.user()) { this.orders.set(orders); if (!orders.some((order) => order.id === this.selectedId())) this.selectedId.set(null); } },
      error: (error) => this.showError(error),
    });
  }
  protected select(id: number): void {
    if (this.busy()) return;
    this.selectedId.set(id); this.cancelling.set(false); this.error.set(''); this.success.set('');
  }
  protected changeStatus(status: OrderStatus, confirmed = false): void {
    const order = this.selected();
    if (!order || !this.auth.user() || this.busy() || !this.transitions(order).includes(status)) return;
    if (status === 'cancelled' && !confirmed) { this.cancelling.set(true); return; }
    this.updating.set(true); this.error.set(''); this.success.set(''); this.cancelling.set(false);
    this.api.updateStatus(order.id, status).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.updating.set(false))).subscribe({
      next: (updated) => {
        if (!this.auth.user()) return;
        this.orders.update((orders) => orders.map((item) => item.id === updated.id ? updated : item));
        this.success.set(`Pedido #${updated.id}: ${this.labels[updated.status]}.`);
      }, error: (error) => this.showError(error),
    });
  }
  private showError(error: unknown): void {
    let message = 'No se pudo completar la operación. Inténtalo nuevamente.';
    if (error instanceof HttpErrorResponse) {
      if (error.status === 401 || error.status === 403) {
        this.orders.set([]); this.selectedId.set(null); this.auth.logout();
        message = 'Tu sesión venció o no tiene permisos. Inicia sesión nuevamente.';
      } else if (typeof error.error?.detail === 'string') message = error.error.detail;
      else if (error.status === 0) message = 'No se pudo conectar. Comprueba tu conexión.';
    }
    this.error.set(message);
  }
}
