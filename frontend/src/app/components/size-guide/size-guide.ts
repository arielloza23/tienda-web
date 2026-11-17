import { Component, computed, ElementRef, input, viewChild } from '@angular/core';

import { ProductVariant } from '../../models/product.model';

@Component({ selector: 'app-size-guide', templateUrl: './size-guide.html', styleUrl: './size-guide.scss' })
export class SizeGuide {
  readonly productName = input.required<string>();
  readonly variants = input<ProductVariant[]>([]);
  protected readonly measuredVariants = computed(() => this.variants().filter(v => [v.bust_cm, v.waist_cm, v.hip_cm].some(n => typeof n === 'number' && n > 0)));
  protected measurement(value: number | null | undefined): string { return typeof value === 'number' && value > 0 ? new Intl.NumberFormat('es-EC', { maximumFractionDigits: 1 }).format(value) : 'Sin dato'; }
  private readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('guide');
  private trigger?: HTMLButtonElement;

  protected open(event: Event): void {
    this.trigger = event.currentTarget as HTMLButtonElement;
    this.dialog().nativeElement.showModal();
  }

  protected close(): void { this.dialog().nativeElement.close(); this.restoreFocus(); }
  protected restoreFocus(): void {
    if (this.dialog().nativeElement.open) return;
    this.trigger?.focus({ preventScroll: true });
    this.trigger = undefined;
  }
  protected backdrop(event: MouseEvent): void {
    if (event.target !== event.currentTarget) return;
    const rect = this.dialog().nativeElement.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) this.close();
  }
}
