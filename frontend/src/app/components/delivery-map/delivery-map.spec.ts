import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DeliveryMap } from './delivery-map';

describe('DeliveryMap checkout lock', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('ignores pending geolocation while the order is being submitted', () => {
    let resolveLocation: PositionCallback | undefined;
    vi.stubGlobal('navigator', { geolocation: {
      getCurrentPosition: vi.fn((success: PositionCallback) => { resolveLocation = success; }),
    } });
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    const fixture = TestBed.createComponent(DeliveryMap);
    const component = fixture.componentInstance;
    // Sin mapas ni red reales: comprobar el resultado asíncrono pendiente.
    vi.spyOn(component as any, 'initMap').mockImplementation(() => {});
    fixture.detectChanges();
    const onLocation = vi.fn();
    component.locationChange.subscribe(onLocation);
    (component as any).useCurrentLocation();
    expect(resolveLocation).toBeDefined();
    fixture.componentRef.setInput('disabled', true);
    fixture.detectChanges();
    resolveLocation!({ coords: { latitude: -0.18, longitude: -78.46 } } as GeolocationPosition);
    expect(onLocation).not.toHaveBeenCalled();
    expect((component as any).isLocating()).toBe(false);
    fixture.destroy();
  });
});
