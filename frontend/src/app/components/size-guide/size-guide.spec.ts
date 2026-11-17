import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';
import { SizeGuide } from './size-guide';
describe('Garment measurement guide', () => {
  it('shows real variant measurements, unknown cells and a separate body measuring guide', () => {
    const fixture = TestBed.createComponent(SizeGuide); fixture.componentRef.setInput('productName', 'Body');
    fixture.componentRef.setInput('variants', [{ id: 1, sku: 'BODY-M', size: 'M', color: 'Negro', bust_cm: 88.5, waist_cm: null, hip_cm: 94, price_adjustment_cents: 0 }]);
    fixture.detectChanges(); const text = fixture.nativeElement.textContent;
    expect(text).toContain('88,5'); expect(text).toContain('Sin dato'); expect(text).toContain('no del cuerpo'); expect(text).toContain('medidas corporales');
  });
  it('does not invent a size chart when no measurements are published', () => {
    const fixture = TestBed.createComponent(SizeGuide); fixture.componentRef.setInput('productName', 'Body'); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('table')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('todavía no está publicada');
  });
});
