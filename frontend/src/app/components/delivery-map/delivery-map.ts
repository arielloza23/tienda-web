import {
  afterNextRender,
  Component,
  DestroyRef,
  effect,
  ElementRef,
  inject,
  input,
  output,
  signal,
  viewChild,
  ViewEncapsulation,
} from '@angular/core';
import * as L from 'leaflet';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { catchError, of, Subject, switchMap, timer, timeout } from 'rxjs';
import { DELIVERY_CITIES } from './delivery-cities';

interface AddressResult {
  features: Array<{ properties: {
    street?: string; housenumber?: string; name?: string;
    district?: string; city?: string; county?: string; state?: string; country?: string;
  } }>;
}

export interface DeliveryLocation {
  latitude: number;
  longitude: number;
}

/** Centro inicial del mapa: Quito. */
const DEFAULT_CENTER: L.LatLngTuple = [-0.1807, -78.4678];
const DEFAULT_ZOOM = 12;
const LOCATED_ZOOM = 17;

@Component({
  selector: 'app-delivery-map',
  templateUrl: './delivery-map.html',
  styleUrl: './delivery-map.scss',
  // Leaflet crea el pin fuera de la vista de Angular; los estilos van con prefijo .delivery-map.
  encapsulation: ViewEncapsulation.None,
})
export class DeliveryMap {
  readonly location = input<DeliveryLocation | null>(null);
  readonly locationChange = output<DeliveryLocation | null>();
  readonly addressChange = output<string>();
  readonly addressLoadingChange = output<boolean>();
  protected readonly cities = DELIVERY_CITIES;
  protected readonly selectedCity = signal('');
  protected readonly isLookingUpAddress = signal(false);
  protected readonly addressError = signal<string | null>(null);
  private readonly http = inject(HttpClient);
  private readonly addressRequests = new Subject<DeliveryLocation | null>();

  protected readonly isLocating = signal(false);
  protected readonly geolocationError = signal<string | null>(null);

  private readonly container = viewChild.required<ElementRef<HTMLDivElement>>('mapCanvas');
  private readonly mapReady = signal(false);
  private map?: L.Map;
  private marker?: L.Marker;
  private resizeObserver?: ResizeObserver;

  private readonly pinIcon = L.divIcon({
    className: 'delivery-map-pin',
    html: '<span></span>',
    iconSize: [30, 30],
    // La gota está girada 45°: su punta queda ~21 px bajo el centro (15 + 21 = 36).
    iconAnchor: [15, 36],
  });

  constructor() {
    afterNextRender(() => this.initMap());

    // Cancel stale results immediately; wait until the customer stops moving the pin.
    this.addressRequests.pipe(
      switchMap((location) => location
        ? timer(800).pipe(switchMap(() => this.http.get<AddressResult>(
            'https://photon.komoot.io/reverse',
            { params: { lat: location.latitude, lon: location.longitude, limit: 1 } },
          ).pipe(timeout(10000), catchError(() => of(null)))))
        : of(null)),
      takeUntilDestroyed(),
    ).subscribe((result) => {
      this.setAddressLoading(false);
      const address = result?.features?.[0]?.properties;
      if (!address) {
        if (this.location()) this.addressError.set('No pudimos encontrar la dirección. Escríbela debajo del mapa.');
        return;
      }
      const city = address.city ?? address.county;
      const knownCity = this.cities.find((entry) => entry.name === city);
      if (knownCity) this.selectedCity.set(knownCity.name);
      const street = [address.street, address.housenumber].filter(Boolean).join(' ');
      const parts = [street || address.name, address.district, city, address.state, address.country];
      const text = [...new Set(parts.filter(Boolean))].join(', ').slice(0, 500);
      if (!text) {
        this.addressError.set('No encontramos una dirección. Escríbela debajo del mapa.');
        return;
      }
      this.addressChange.emit(text);
    });

    // Mantiene el pin sincronizado con el valor que recibe del formulario.
    effect(() => {
      const location = this.location();
      if (this.mapReady()) {
        this.syncMarker(location);
      }
    });

    inject(DestroyRef).onDestroy(() => {
      this.resizeObserver?.disconnect();
      this.map?.remove();
    });
  }

  protected useCurrentLocation(): void {
    if (!('geolocation' in navigator)) {
      this.geolocationError.set('Tu navegador no permite obtener la ubicación.');
      return;
    }

    this.isLocating.set(true);
    this.geolocationError.set(null);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        this.isLocating.set(false);
        const latLng = L.latLng(position.coords.latitude, position.coords.longitude);
        this.map?.setView(latLng, LOCATED_ZOOM);
        this.emitLocation(latLng);
      },
      (error) => {
        this.isLocating.set(false);
        this.geolocationError.set(
          error.code === error.PERMISSION_DENIED
            ? 'No diste permiso para usar tu ubicación. Marca el punto tocando el mapa.'
            : 'No pudimos obtener tu ubicación. Marca el punto tocando el mapa.',
        );
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  protected markMapCenter(): void {
    if (this.map) {
      this.emitLocation(this.map.getCenter());
    }
  }

  protected clearLocation(): void {
    this.addressRequests.next(null);
    this.setAddressLoading(false);
    this.addressError.set(null);
    this.addressChange.emit('');
    this.locationChange.emit(null);
  }

  protected selectCity(name: string): void {
    const city = this.cities.find((entry) => entry.name === name);
    this.selectedCity.set(name);
    this.clearLocation();
    if (city) {
      this.map?.setView([city.latitude, city.longitude], DEFAULT_ZOOM);
      this.addressChange.emit(`${city.name}, Ecuador`);
    }
  }

  private setAddressLoading(loading: boolean): void {
    this.isLookingUpAddress.set(loading);
    this.addressLoadingChange.emit(loading);
  }

  private initMap(): void {
    const initial = this.location();
    this.map = L.map(this.container().nativeElement, {
      center: initial ? [initial.latitude, initial.longitude] : DEFAULT_CENTER,
      zoom: initial ? LOCATED_ZOOM : DEFAULT_ZOOM,
      zoomControl: false,
      scrollWheelZoom: true,
    });

    L.control.zoom({ position: 'bottomright', zoomInTitle: 'Acercar', zoomOutTitle: 'Alejar' }).addTo(this.map);

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(this.map);

    this.map.on('click', (event: L.LeafletMouseEvent) => this.emitLocation(event.latlng));

    // El carrito puede mostrarse u ocultarse; Leaflet necesita recalcular su tamaño.
    this.resizeObserver = new ResizeObserver(() => this.map?.invalidateSize());
    this.resizeObserver.observe(this.container().nativeElement);

    this.mapReady.set(true);
  }

  private syncMarker(location: DeliveryLocation | null): void {
    if (!this.map) {
      return;
    }
    if (!location) {
      this.marker?.remove();
      this.marker = undefined;
      return;
    }

    const latLng = L.latLng(location.latitude, location.longitude);
    if (this.marker) {
      this.marker.setLatLng(latLng);
      return;
    }

    this.marker = L.marker(latLng, {
      icon: this.pinIcon,
      draggable: true,
      keyboard: true,
      title: 'Punto de entrega',
      alt: 'Punto de entrega',
    }).addTo(this.map);
    this.marker.on('dragend', () => {
      if (this.marker) {
        this.emitLocation(this.marker.getLatLng());
      }
    });
  }

  private emitLocation(latLng: L.LatLng): void {
    const wrapped = latLng.wrap();
    this.geolocationError.set(null);
    this.locationChange.emit({
      latitude: Number(wrapped.lat.toFixed(6)),
      longitude: Number(wrapped.lng.toFixed(6)),
    });
    this.addressChange.emit('');
    this.addressError.set(null);
    this.setAddressLoading(true);
    this.addressRequests.next({ latitude: wrapped.lat, longitude: wrapped.lng });
  }
}
