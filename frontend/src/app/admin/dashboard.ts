import { CommonModule } from '@angular/common';
import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { finalize } from 'rxjs';
import { AnalyticsApi, DashboardData } from './analytics-api.service';

@Component({ selector: 'app-admin-dashboard', imports: [CommonModule], templateUrl: './dashboard.html', styleUrl: './dashboard.scss' })
export class AdminDashboard implements OnInit {
  private readonly api = inject(AnalyticsApi);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly days = signal(30);
  protected readonly data = signal<DashboardData | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal('');
  protected readonly periods = [7, 30, 90];
  protected readonly maxEvents = computed(() => Math.max(1, ...this.data()?.interactions.map(i => i.events) ?? []));
  protected readonly labels: Record<string, string> = {
    product_view: 'Vista de producto', variant_select: 'Selección de talla o color', gallery_open: 'Apertura de fotos',
    reviews_open: 'Consulta de opiniones', add_to_cart: 'Agregar al carrito', checkout_start: 'Inicio del pedido',
    whatsapp_click: 'Continuar en WhatsApp', filter_apply: 'Uso de filtros',
  };
  ngOnInit(): void { this.load(); }
  protected selectPeriod(days: number): void { if (!this.loading()) { this.days.set(days); this.load(); } }
  protected load(): void {
    if (this.loading()) return;
    this.loading.set(true); this.error.set(''); this.data.set(null);
    this.api.dashboard(this.days()).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.loading.set(false))).subscribe({
      next: data => this.data.set(data),
      error: () => this.error.set('No pudimos cargar los indicadores. Vuelve a intentarlo.'),
    });
  }
}
