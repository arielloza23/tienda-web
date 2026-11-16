import { Component, ElementRef, input, viewChild } from '@angular/core';

@Component({ selector: 'app-size-guide', templateUrl: './size-guide.html', styleUrl: './size-guide.scss' })
export class SizeGuide {
  readonly productName = input.required<string>();
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
